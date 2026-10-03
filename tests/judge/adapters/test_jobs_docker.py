"""Build and judge jobs against a real Docker daemon (marker: docker).

The path a real task takes: the stored package becomes an image, then stored student
zips get their verdicts and live per-test rows.
"""

import contextlib
import hashlib
from collections.abc import Iterator

import docker
import pytest
from django.core.files.base import ContentFile
from docker.errors import ImageNotFound

from apps.submissions.models import Submission
from apps.tasks.models import Assignment, RunnerProfile, Task, TaskVersion
from judge.adapters.jobs import run_build, run_judge
from judge.config import JudgeConfig, read_env
from judge.env import REPO_ROOT
from tests.apps.world import World, zip_folder

pytestmark = [pytest.mark.docker, pytest.mark.django_db]
CART = REPO_ROOT / "examples" / "dart-cart"


@pytest.fixture(scope="module")
def config() -> JudgeConfig:
    return JudgeConfig.from_env(read_env(REPO_ROOT / ".env.example", environ={}))


@pytest.fixture
def built(
    world: World, docker_client: docker.DockerClient, dart_base_image: str, config: JudgeConfig
) -> Iterator[TaskVersion]:
    """dart-cart uploaded by centre a's teacher and built by the build job."""
    data = zip_folder(CART / "task")
    task = Task.objects.create(
        center=world.a.center,
        author=world.a.teacher,
        profile=RunnerProfile.objects.get(slug="dart"),
        title="Savat",
        statement_md="Savat",
    )
    version = TaskVersion(task=task, number=1, sha256=hashlib.sha256(data).hexdigest())
    version.package.save("package.zip", ContentFile(data), save=False)
    version.save()
    run_build(docker_client, config, version)
    version.refresh_from_db()
    task.published_version = version
    task.save()
    yield version
    if version.image_tag:
        with contextlib.suppress(ImageNotFound):
            docker_client.images.remove(version.image_tag, force=True)


def submit(world: World, version: TaskVersion, name: str) -> Submission:
    assignment, _ = Assignment.objects.get_or_create(task=version.task, group=world.a.group)
    data = zip_folder(CART / "submissions" / name)
    submission = Submission(
        assignment=assignment,
        student=world.a.student,
        task_version=version,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    submission.archive.save("solution.zip", ContentFile(data), save=False)
    submission.save()
    return submission


def test_the_build_job_makes_a_ready_version(built: TaskVersion) -> None:
    assert built.status == TaskVersion.Status.READY, built.build_errors
    assert built.test_count == 9
    assert built.image_tag.startswith(f"ohw-task:{built.pk}-")
    assert 15 <= built.time_limit_s <= 120
    assert 0 < built.warm_wall_ms < built.solution_wall_ms
    assert built.runtime_info == "Dart 3.13.5"
    assert built.import_rules["package_name"] == "cart"
    assert "$ dart pub get" in built.build_log


def test_a_broken_package_fails_with_the_teachers_errors(
    world: World, docker_client: docker.DockerClient, config: JudgeConfig
) -> None:
    data = zip_folder(CART / "task", leave_out="test/hidden")
    task = Task.objects.create(
        center=world.a.center,
        author=world.a.teacher,
        profile=RunnerProfile.objects.get(slug="dart"),
        title="Buzuq",
        statement_md="-",
    )
    version = TaskVersion(task=task, number=1, sha256="0" * 64)
    version.package.save("package.zip", ContentFile(data), save=False)
    version.save()

    run_build(docker_client, config, version)

    version.refresh_from_db()
    assert version.status == TaskVersion.Status.BUILD_FAILED
    assert "test/hidden" in version.build_errors[0]


@pytest.mark.parametrize(
    ("name", "verdict", "failed", "rows"),
    [
        ("ok", "accepted", None, ["pass"] * 9),
        ("fail_logic", "wrong_answer", 3, ["pass", "pass", "fail"]),
        ("forbidden_import", "rejected", None, []),
    ],
)
def test_the_judge_job_saves_the_verdict_and_each_test(
    world: World,
    built: TaskVersion,
    docker_client: docker.DockerClient,
    config: JudgeConfig,
    name: str,
    verdict: str,
    failed: int | None,
    rows: list[str],
) -> None:
    submission = submit(world, built, name)

    run_judge(docker_client, config, submission)

    submission.refresh_from_db()
    assert (submission.status, submission.verdict, submission.failed_test_index) == (
        "finished",
        verdict,
        failed,
    )
    assert list(submission.results.values_list("status", flat=True)) == rows
    assert submission.internal_log
    if verdict == "rejected":
        assert "dart:io" in submission.public_message


def test_a_node_without_the_image_builds_it_again(
    world: World, built: TaskVersion, docker_client: docker.DockerClient, config: JudgeConfig
) -> None:
    docker_client.images.remove(built.image_tag, force=True)
    submission = submit(world, built, "ok")

    run_judge(docker_client, config, submission)

    submission.refresh_from_db()
    assert submission.verdict == "accepted"
    assert docker_client.images.get(built.image_tag)
