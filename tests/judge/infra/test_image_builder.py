"""Task image builder against a real Docker daemon (marker: docker).

The key property: an image warmed up with the teacher's solution must judge the student's
code, never the cached solution.
"""

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import docker
import pytest
from docker.errors import ImageNotFound

from judge.core.events import RunEvent
from judge.core.limits import time_limit_s
from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.profile import RunnerProfile
from judge.core.verdict import Judgement, RunOutcome, Verdict, decide_verdict
from judge.infra.image_builder import (
    BuildFailed,
    BuildResult,
    build_task_image,
    task_image_tag,
)
from judge.infra.sandbox import NodeSettings, Sandbox, SandboxLimits
from judge.packaging.task_package import TaskPackage, read_task_package
from judge.packaging.zip_validator import ArchiveFile
from judge.parsers import make_parser

pytestmark = pytest.mark.docker

REPO_ROOT = Path(__file__).resolve().parents[3]
DART_FIXTURES = REPO_ROOT / "tests" / "judge" / "parsers" / "fixtures" / "dart_json"
FLUTTER_FIXTURES = Path(__file__).parent / "fixtures" / "flutter_counter"
NODE = NodeSettings(cpu_shares=512, max_output_bytes=512 * 1024)

DART_MANIFEST = Manifest(
    (
        ManifestTest("Savat boʻsh boʻlsa jami 0 ga teng", 1, Visibility.PUBLIC),
        ManifestTest("Mahsulot qoʻshilganda jami ortadi", 1, Visibility.PUBLIC),
        ManifestTest("Chegirma 10% chegirma qoʻllanadi", 1, Visibility.HIDDEN),
        ManifestTest("Chegirma 0% chegirmada narx oʻzgarmaydi", 1, Visibility.HIDDEN),
    )
)


def load_profile(slug: str) -> RunnerProfile:
    data = json.loads((REPO_ROOT / "profiles" / slug / "profile.json").read_text())
    return RunnerProfile.from_json_data(data)


def files_under(folder: Path, prefix: str = "") -> list[ArchiveFile]:
    return [
        ArchiveFile(prefix + path.relative_to(folder).as_posix(), path.read_bytes())
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    ]


def lib_of(solutions: Path, name: str) -> list[ArchiveFile]:
    return files_under(solutions / name / "lib", prefix="lib/")


def dart_package(solution: str, pubspec: bytes | None = None) -> TaskPackage:
    project = [
        file
        for file in files_under(DART_FIXTURES / "project")
        if file.path != "test/_ohw_all_test.dart"  # the builder generates its own
    ]
    if pubspec is not None:
        project = [f for f in project if f.path != "pubspec.yaml"]
        project.append(ArchiveFile("pubspec.yaml", pubspec))
    solution_files = files_under(DART_FIXTURES / "solutions" / solution / "lib", "solution/lib/")
    return read_task_package([*project, *solution_files])


def flutter_package() -> TaskPackage:
    return read_task_package(
        [
            *files_under(FLUTTER_FIXTURES / "package"),
            *files_under(FLUTTER_FIXTURES / "solutions" / "pass" / "lib", "solution/lib/"),
        ]
    )


def judge(
    client: docker.DockerClient,
    result: BuildResult,
    profile: RunnerProfile,
    lib: list[ArchiveFile],
) -> Judgement:
    """A minimal runner: the student's lib/ in the task image, tests, verdict."""
    parser = make_parser(profile.parser)
    events: list[RunEvent] = []

    def on_line(line: str) -> bool:
        event = parser.feed(line)
        if event is not None:
            events.append(event)
        return False

    limits = SandboxLimits.for_profile(profile, NODE)
    with Sandbox(client, result.image_tag, profile.test_command, limits) as sandbox:
        sandbox.put_files(lib)
        run = sandbox.run(result.time_limit_s, on_line=on_line)
    outcome = RunOutcome(tuple(events), run.timed_out, run.oom_killed, parser.compile_error)
    return decide_verdict(result.manifest, outcome)


@pytest.fixture
def image_ids(docker_client: docker.DockerClient) -> Iterator[set[str]]:
    """Image ids before and after a test: a failed build must leave nothing behind."""
    before = {image.id for image in docker_client.images.list(all=True)}
    yield before


def build(
    client: docker.DockerClient, package: TaskPackage, slug: str, base_image: str, name: str
) -> BuildResult:
    tag = task_image_tag(0, f"test{name}".ljust(12, "0"))
    return build_task_image(
        client, package, load_profile(slug), NODE, base_image=base_image, tag=tag
    )


def remove(client: docker.DockerClient, tag: str) -> None:
    with contextlib.suppress(ImageNotFound):
        client.images.remove(tag, force=True)


@pytest.fixture(scope="module")
def dart_task(docker_client: docker.DockerClient, dart_base_image: str) -> Iterator[BuildResult]:
    result = build(docker_client, dart_package("pass"), "dart", dart_base_image, "dartpass")
    yield result
    remove(docker_client, result.image_tag)


def test_task_image_tag_is_deterministic() -> None:
    assert task_image_tag(42, "0123456789abcdef" * 4) == "ohw-task:42-0123456789ab"


def test_dart_task_builds_with_manifest_and_time_limit(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    assert dart_task.manifest == DART_MANIFEST
    assert dart_task.solution_wall_ms > 0
    assert dart_task.time_limit_s == time_limit_s(dart_task.solution_wall_ms, 20, 120)
    assert docker_client.images.get(dart_task.image_tag)
    assert "$ dart pub get" in dart_task.log


def test_image_keeps_tests_and_cache_but_not_the_solution(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    script = (
        "test ! -e lib && test -d .dart_tool && test -f test/_ohw_all_test.dart "
        "&& test -f test/hidden/02_discount_test.dart && echo ok"
    )
    limits = SandboxLimits.for_profile(load_profile("dart"), NODE)
    with Sandbox(docker_client, dart_task.image_tag, ["sh", "-c", script], limits) as sandbox:
        run = sandbox.run(30)

    assert run.stdout.strip() == "ok", run.stderr


@pytest.mark.parametrize(
    ("solution", "verdict", "failed_test"),
    [
        ("fail_public", Verdict.WRONG_ANSWER, 2),
        ("pass", Verdict.ACCEPTED, None),
        ("fail_hidden", Verdict.WRONG_ANSWER, 3),
        ("compile_error", Verdict.COMPILE_ERROR, None),
        ("exception", Verdict.WRONG_ANSWER, 3),
    ],
)
def test_warm_image_judges_the_new_code_not_the_cached_solution(
    docker_client: docker.DockerClient,
    dart_task: BuildResult,
    solution: str,
    verdict: Verdict,
    failed_test: int | None,
) -> None:
    lib = lib_of(DART_FIXTURES / "solutions", solution)

    judgement = judge(docker_client, dart_task, load_profile("dart"), lib)

    assert (judgement.verdict, judgement.failed_test_index) == (verdict, failed_test)


def test_failing_solution_fails_the_build(
    docker_client: docker.DockerClient, dart_base_image: str, image_ids: set[str]
) -> None:
    with pytest.raises(BuildFailed) as error:
        build(docker_client, dart_package("fail_hidden"), "dart", dart_base_image, "darthid")

    assert error.value.errors[0].startswith(
        "Oʻqituvchi yechimi 3-testdan oʻtmadi: Chegirma 10% chegirma qoʻllanadi\nExpected"
    )
    assert "$ dart test" in error.value.log
    assert {image.id for image in docker_client.images.list(all=True)} == image_ids


def test_solution_that_does_not_compile_fails_the_build(
    docker_client: docker.DockerClient, dart_base_image: str
) -> None:
    with pytest.raises(BuildFailed) as error:
        build(docker_client, dart_package("compile_error"), "dart", dart_base_image, "dartce")

    assert "kompilyatsiya boʻlmadi" in error.value.errors[0]
    assert "The getter 'total' isn't defined" in error.value.errors[0]


def test_unknown_library_fails_the_install(
    docker_client: docker.DockerClient, dart_base_image: str, image_ids: set[str]
) -> None:
    pubspec = (
        b"name: cart\nenvironment:\n  sdk: ^3.0.0\n"
        b"dependencies:\n  ohw_no_such_package_anywhere: ^1.0.0\n"
        b"dev_dependencies:\n  test: ^1.25.0\n"
    )

    with pytest.raises(BuildFailed) as error:
        build(docker_client, dart_package("pass", pubspec), "dart", dart_base_image, "dartdep")

    assert "Kutubxonalarni oʻrnatib boʻlmadi" in error.value.errors[0]
    assert "ohw_no_such_package_anywhere" in error.value.log
    assert {image.id for image in docker_client.images.list(all=True)} == image_ids


def test_flutter_task_builds_and_judges_new_code(
    docker_client: docker.DockerClient, flutter_base_image: str
) -> None:
    result = build(docker_client, flutter_package(), "flutter", flutter_base_image, "flutter")
    try:
        assert result.manifest == Manifest(
            (
                ManifestTest("Tugma bosilganda son ortadi", 1, Visibility.PUBLIC),
                ManifestTest("Ikki marta oshirilganda 2 boʻladi", 1, Visibility.HIDDEN),
            )
        )
        assert 90 <= result.time_limit_s <= 300
        profile = load_profile("flutter")
        solutions = FLUTTER_FIXTURES / "solutions"
        failing = judge(docker_client, result, profile, lib_of(solutions, "fail"))
        passing = judge(docker_client, result, profile, lib_of(solutions, "pass"))
        assert (failing.verdict, failing.failed_test_index) == (Verdict.WRONG_ANSWER, 1)
        assert passing.verdict == Verdict.ACCEPTED
    finally:
        remove(docker_client, result.image_tag)
