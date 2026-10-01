"""Task image builder against a real Docker daemon (marker: docker).

The key property: an image warmed up with the teacher's solution must judge the student's
code, never the cached solution.
"""

from collections.abc import Iterator

import docker
import pytest

from judge.core.limits import time_limit_s
from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.verdict import Verdict
from judge.infra.image_builder import (
    BuildFailed,
    BuildResult,
    load_build_result,
    task_image_tag,
)
from judge.infra.runner import judge_submission
from judge.infra.sandbox import Sandbox, SandboxLimits
from judge.packaging.dart_imports import ImportRules
from tests.judge.infra.support import (
    NODE,
    build,
    cart_lib,
    dart_package,
    flutter_lib,
    flutter_package,
    load_profile,
    remove_image,
    task_image,
)

pytestmark = pytest.mark.docker

DART_MANIFEST = Manifest(
    (
        ManifestTest("Savat boʻsh boʻlsa jami 0 ga teng", 1, Visibility.PUBLIC),
        ManifestTest("Mahsulot qoʻshilganda jami ortadi", 1, Visibility.PUBLIC),
        ManifestTest("Chegirma 10% chegirma qoʻllanadi", 1, Visibility.HIDDEN),
        ManifestTest("Chegirma 0% chegirmada narx oʻzgarmaydi", 1, Visibility.HIDDEN),
    )
)


@pytest.fixture
def image_ids(docker_client: docker.DockerClient) -> Iterator[set[str]]:
    """Image ids before a test: a failed build must leave nothing behind."""
    yield {image.id for image in docker_client.images.list(all=True)}


def test_task_image_tag_is_deterministic() -> None:
    assert task_image_tag(42, "0123456789abcdef" * 4) == "ohw-task:42-0123456789ab"


def test_dart_task_builds_with_manifest_and_time_limit(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    assert dart_task.task.manifest == DART_MANIFEST
    assert dart_task.solution_wall_ms > 0
    assert dart_task.task.time_limit_s == time_limit_s(dart_task.solution_wall_ms, 20, 120)
    assert docker_client.images.get(dart_task.task.image_tag)
    assert "$ dart pub get" in dart_task.log


def test_image_carries_its_build_in_a_label(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    loaded = load_build_result(docker_client, dart_task.task.image_tag)

    assert loaded == BuildResult(dart_task.task, dart_task.solution_wall_ms)
    assert loaded.task.import_rules == ImportRules(
        package_name="cart",
        allowed_packages=frozenset({"cart"}),
        forbidden_dart=frozenset({"io", "ffi", "isolate", "mirrors", "cli"}),
    )
    config = docker_client.images.get(dart_task.task.image_tag).attrs["Config"]
    assert config["User"] in ("ohw", "1000:1000")
    assert config["WorkingDir"] == "/home/ohw/app"


def test_missing_image_has_no_build(docker_client: docker.DockerClient) -> None:
    assert load_build_result(docker_client, "ohw-task:no-such-image") is None


def test_image_keeps_tests_and_cache_but_not_the_solution(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    script = (
        "test ! -e lib && test -d .dart_tool && test -f test/_ohw_all_test.dart "
        "&& test -f test/hidden/02_discount_test.dart && echo ok"
    )
    limits = SandboxLimits.for_profile(load_profile("dart"), NODE)
    with Sandbox(docker_client, dart_task.task.image_tag, ["sh", "-c", script], limits) as sandbox:
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
    result = judge_submission(
        docker_client, task_image(dart_task), load_profile("dart"), NODE, cart_lib(solution)
    )

    assert (result.judgement.verdict, result.judgement.failed_test_index) == (verdict, failed_test)


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
        assert result.task.manifest == Manifest(
            (
                ManifestTest("Tugma bosilganda son ortadi", 1, Visibility.PUBLIC),
                ManifestTest("Ikki marta oshirilganda 2 boʻladi", 1, Visibility.HIDDEN),
            )
        )
        assert 90 <= result.task.time_limit_s <= 300
        task, profile = task_image(result), load_profile("flutter")
        failing = judge_submission(docker_client, task, profile, NODE, flutter_lib("fail"))
        passing = judge_submission(docker_client, task, profile, NODE, flutter_lib("pass"))
        assert (failing.judgement.verdict, failing.judgement.failed_test_index) == (
            Verdict.WRONG_ANSWER,
            1,
        )
        assert passing.judgement.verdict == Verdict.ACCEPTED
    finally:
        remove_image(docker_client, result.task.image_tag)
