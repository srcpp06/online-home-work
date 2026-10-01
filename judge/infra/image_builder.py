"""Builds the image of a task version (SPEC §3.3).

1. Install the teacher's libraries into the base image: the only step with internet.
2. Warm up: run the tests with the teacher's solution exactly like a judge run (no
   internet, the same limits). Every test must pass. The compile cache stays in the image;
   the solution is deleted before the image is saved, so students can't import it.

No Dockerfile: each step is a sandbox container saved with commit.
"""

import contextlib
import json
import shlex
from dataclasses import dataclass

import docker
from docker.errors import APIError, ImageNotFound

from judge.core.events import EventType, RunEvent
from judge.core.limits import time_limit_s
from judge.core.manifest import Manifest, ManifestTest
from judge.core.profile import RunnerProfile
from judge.core.verdict import RunOutcome, Verdict, decide_verdict
from judge.infra.runner import TaskImage
from judge.infra.sandbox import ContainerRun, NodeSettings, Sandbox, SandboxLimits
from judge.packaging.combined_tests import combined_test_file
from judge.packaging.dart_imports import ImportRules
from judge.packaging.task_package import TaskPackage, visibility_of
from judge.parsers import make_parser

# The image describes itself: everything judging needs is in this label.
BUILD_LABEL = "ohw.build"


@dataclass(frozen=True)
class BuildResult:
    task: TaskImage
    solution_wall_ms: int
    log: str = ""  # not kept in the image label
    warm_up_peak_mb: int | None = None  # when the node samples memory; not in the label

    def label(self) -> dict[str, str]:
        data = {"task": self.task.to_json_data(), "solution_wall_ms": self.solution_wall_ms}
        return {BUILD_LABEL: json.dumps(data, ensure_ascii=False)}


class BuildFailed(Exception):
    """The task can't be published. ``errors`` are for the teacher, ``log`` has the details."""

    def __init__(self, errors: list[str], log: str = "") -> None:
        super().__init__("\n".join(errors))
        self.errors = errors
        self.log = log


def task_image_tag(task_version_id: int | str, package_sha256: str) -> str:
    """Deterministic, so any node can rebuild the same image from the stored package."""
    return f"ohw-task:{task_version_id}-{package_sha256[:12]}"


def load_build_result(client: docker.DockerClient, tag: str) -> BuildResult | None:
    """The build saved in an image's label, or None if there is no such image."""
    try:
        labels = client.images.get(tag).labels or {}
    except ImageNotFound:
        return None
    if BUILD_LABEL not in labels:
        return None
    data = json.loads(labels[BUILD_LABEL])
    return BuildResult(TaskImage.from_json_data(data["task"]), data["solution_wall_ms"])


def build_task_image(
    client: docker.DockerClient,
    package: TaskPackage,
    profile: RunnerProfile,
    node: NodeSettings,
    *,
    base_image: str,
    tag: str,
) -> BuildResult:
    limits = SandboxLimits.for_profile(profile, node)
    log = _BuildLog()

    with Sandbox(client, base_image, profile.install_command, limits, network=True) as sandbox:
        sandbox.put_files(
            [*package.project_files, combined_test_file(package.test_files, profile.test_import)]
        )
        run = sandbox.run(timeout_s=profile.build_timeout_s)
        log.add(shlex.join(profile.install_command), run, run.stdout)
        if run.timed_out:
            raise BuildFailed(
                [f"Kutubxonalarni oʻrnatish {profile.build_timeout_s} soniyada tugamadi."],
                log.text,
            )
        if run.exit_code != 0 or run.oom_killed or run.output_limit_exceeded:
            raise BuildFailed(
                [
                    "Kutubxonalarni oʻrnatib boʻlmadi. "
                    "pubspec.yaml ni tekshiring, toʻliq log quyida."
                ],
                log.text,
            )
        installed_image = sandbox.commit()

    try:
        return _warm_up(client, package, profile, limits, installed_image, tag, log)
    except BuildFailed:
        _remove_image(client, installed_image)
        raise


def _warm_up(
    client: docker.DockerClient,
    package: TaskPackage,
    profile: RunnerProfile,
    limits: SandboxLimits,
    installed_image: str,
    tag: str,
    log: "_BuildLog",
) -> BuildResult:
    test_command = shlex.join(profile.test_command)
    # The solution is removed in the same container, so it never reaches an image layer.
    command = ["sh", "-c", f"{test_command}; status=$?; rm -rf lib; exit $status"]
    parser = make_parser(profile.parser)
    events: list[RunEvent] = []

    def on_line(line: str) -> bool:
        event = parser.feed(line)
        if event is not None:
            events.append(event)
        return False  # the warm-up always runs to the end

    with Sandbox(client, installed_image, command, limits) as sandbox:
        sandbox.put_files(package.solution_files)
        run = sandbox.run(timeout_s=profile.max_time_s, on_line=on_line)
        log.add(test_command, run, "\n".join(parser.log))
        try:
            manifest = _check_warm_up(run, parser.compile_error, events, parser.test_files, profile)
        except BuildFailed as error:
            raise BuildFailed(error.errors, log.text) from None
        task = TaskImage(
            image_tag=tag,
            manifest=manifest,
            time_limit_s=time_limit_s(run.wall_ms, profile.min_time_s, profile.max_time_s),
            import_rules=_import_rules(package, profile),
        )
        result = BuildResult(
            task, solution_wall_ms=run.wall_ms, log=log.text, warm_up_peak_mb=run.peak_memory_mb
        )
        repository, _, version = tag.partition(":")
        sandbox.commit(repository, version or None, labels=result.label())
    return result


def _import_rules(package: TaskPackage, profile: RunnerProfile) -> ImportRules | None:
    if profile.static_check is None:
        return None
    if profile.static_check != "dart_imports":
        raise ValueError(f"unknown static check {profile.static_check!r}")
    return ImportRules.for_task(package, profile)


def _check_warm_up(
    run: ContainerRun,
    compile_error: str | None,
    events: list[RunEvent],
    test_files: dict[int, str],
    profile: RunnerProfile,
) -> Manifest:
    """The manifest of the run, if the teacher's solution passed every test."""

    def failed(message: str) -> BuildFailed:
        return BuildFailed([message])

    if run.output_limit_exceeded:
        raise failed("Testlar juda koʻp matn chiqardi. print chaqiruvlarini kamaytiring.")
    if run.timed_out:
        raise failed(
            f"Oʻqituvchi yechimi testlarni {profile.max_time_s} soniyada tugatmadi. "
            "Testlarni tezlashtiring."
        )
    if run.oom_killed:
        raise failed(f"Testlar {profile.memory_mb} MB xotiraga sigʻmadi.")
    if compile_error is not None:
        raise failed(f"Testlar yoki yechim kompilyatsiya boʻlmadi:\n{compile_error}")
    starts = [event for event in events if event.type == EventType.START]
    if not starts:
        raise failed("Test fayllarida birorta ham test yoʻq.")

    manifest = Manifest(
        tuple(
            # A test whose file is unknown counts as hidden: its messages stay hidden.
            ManifestTest(event.name, event.stage, visibility_of(test_files.get(event.index, "")))
            for event in starts
        )
    )
    judgement = decide_verdict(manifest, RunOutcome(events=tuple(events), exit_code=run.exit_code))
    if judgement.verdict == Verdict.WRONG_ANSWER:
        failure = next(e for e in events if e.type == EventType.FAIL)
        raise failed(
            f"Oʻqituvchi yechimi {failure.index}-testdan oʻtmadi: {failure.name}\n{failure.message}"
        )
    if judgement.verdict != Verdict.ACCEPTED:
        raise failed(f"Testlar oxirigacha bajarilmadi ({judgement.detail}). Logni tekshiring.")
    return manifest


class _BuildLog:
    """What the teacher sees: each step's command, result and output."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def add(self, command: str, run: ContainerRun, output: str) -> None:
        self._parts.append(f"$ {command}  ({run.describe()})")
        self._parts += [text.rstrip() for text in (output, run.stderr) if text.strip()]

    @property
    def text(self) -> str:
        return "\n".join(self._parts) + "\n"


def _remove_image(client: docker.DockerClient, image: str) -> None:
    with contextlib.suppress(ImageNotFound, APIError):
        client.images.remove(image, force=True)
