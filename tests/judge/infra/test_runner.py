"""Runner against a real Docker daemon (marker: docker): one task image, many submissions."""

import dataclasses
import io
import zipfile

import docker
import pytest

from judge.core.events import RunEvent
from judge.core.verdict import Verdict
from judge.infra.image_builder import BuildResult
from judge.infra.runner import JudgeResult, TaskImage, judge_submission
from judge.packaging.submission import read_submission
from judge.packaging.zip_validator import ArchiveFile, ZipLimits, validate_zip
from tests.judge.infra.support import NODE, cart_lib, cart_project, load_profile, task_image

pytestmark = pytest.mark.docker

DART = load_profile("dart")


def run(
    client: docker.DockerClient,
    task: TaskImage,
    lib: list[ArchiveFile],
    events: list[RunEvent] | None = None,
) -> JudgeResult:
    on_event = None if events is None else events.append
    return judge_submission(client, task, DART, NODE, lib, on_event=on_event)


def test_correct_solution_is_accepted_and_reported_live(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    live: list[RunEvent] = []
    result = run(docker_client, task_image(dart_task), cart_lib("pass"), live)

    assert result.judgement.verdict == Verdict.ACCEPTED
    assert result.judgement.tests_passed == 4
    assert [e.type.value for e in live] == ["start", "pass"] * 4 + ["done"]
    assert [(e.index, e.type.value) for e in result.results] == [
        (1, "pass"),
        (2, "pass"),
        (3, "pass"),
        (4, "pass"),
    ]


def test_run_stops_at_the_first_failed_test(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    live: list[RunEvent] = []
    result = run(docker_client, task_image(dart_task), cart_lib("fail_public"), live)

    assert (result.judgement.verdict, result.judgement.failed_test_index) == (
        Verdict.WRONG_ANSWER,
        2,
    )
    assert [(e.index, e.type.value) for e in result.results] == [(1, "pass"), (2, "fail")]
    assert result.results[1].message == "Expected: <4000>\n  Actual: <2500>"
    assert [e.index for e in live] == [1, 1, 2, 2], "tests after the failure must not start"
    assert "stopped at the first failure" in result.log


def test_compile_error_reports_the_compiler(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    result = run(docker_client, task_image(dart_task), cart_lib("compile_error"))

    assert result.judgement.verdict == Verdict.COMPILE_ERROR
    assert result.results == ()
    assert "The getter 'total' isn't defined" in (result.compile_error or "")


def test_infinite_loop_hits_the_time_limit(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    task = dataclasses.replace(task_image(dart_task), time_limit_s=3)

    result = run(docker_client, task, cart_lib("infinite_loop"))

    assert (result.judgement.verdict, result.judgement.failed_test_index) == (
        Verdict.TIME_LIMIT,
        1,
    )
    assert result.wall_ms < 10_000


def test_memory_hog_hits_the_memory_limit(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    task = dataclasses.replace(task_image(dart_task), memory_limit_mb=512)

    result = run(docker_client, task, cart_lib("memory_hog"))

    assert result.judgement.verdict == Verdict.MEMORY_LIMIT


def test_print_flood_is_cut_off(docker_client: docker.DockerClient, dart_task: BuildResult) -> None:
    result = run(docker_client, task_image(dart_task), cart_lib("print_flood"))

    assert result.judgement.verdict == Verdict.RUNTIME_ERROR
    assert "output limit exceeded" in result.log


def test_fake_reporter_lines_are_never_accepted(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    """spoof_attempt (SPEC §3.7): printed JSON stays a print, never a test result."""
    result = run(docker_client, task_image(dart_task), cart_lib("spoof_print"))

    assert result.judgement.verdict != Verdict.ACCEPTED
    assert (result.judgement.verdict, result.judgement.failed_test_index) == (
        Verdict.WRONG_ANSWER,
        1,
    )
    assert '"type":"done"' in result.log  # the fake line ended up in the teacher's log


def test_whole_project_zip_is_judged_end_to_end(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in cart_project():  # the student's copy of tests and pubspec is ignored
            archive.writestr(f"Downloads/cart/{file.path}", file.data)
        for file in cart_lib("pass"):
            archive.writestr(f"Downloads/cart/{file.path}", file.data)
        archive.writestr("Downloads/cart/build/cache.dill", b"\0" * 100_000)
        archive.writestr("__MACOSX/Downloads/cart/lib/._cart.dart", b"junk")
    mb = 1024 * 1024
    limits = ZipLimits(max_zip_bytes=5 * mb, max_unpacked_bytes=20 * mb, max_files=500)

    student_files = read_submission(validate_zip(buffer, limits), DART.student_paths)
    result = run(docker_client, task_image(dart_task), student_files)

    assert [f.path for f in student_files] == ["lib/cart.dart"]
    assert result.judgement.verdict == Verdict.ACCEPTED


def test_no_containers_are_left_behind(
    docker_client: docker.DockerClient, dart_task: BuildResult
) -> None:
    run(docker_client, task_image(dart_task), cart_lib("fail_hidden"))

    ancestor = {"ancestor": dart_task.task.image_tag}
    leftovers = docker_client.containers.list(all=True, filters=ancestor)
    assert leftovers == []
