"""Judges one submission inside its task image (SPEC §3.4).

judge_zip is the whole check of a student's zip: validate it, pick the student's files,
run the static check, then judge_submission. That puts the files into a fresh sandbox,
runs the tests and checks every event against the manifest as it arrives. The run stops
at the first failed test, or as soon as the stream stops matching the manifest. Results
reach the caller live, test by test.
"""

import dataclasses
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, BinaryIO, Self

import docker

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest
from judge.core.profile import RunnerProfile
from judge.core.progress import RunProgress
from judge.core.verdict import Judgement, RunOutcome, Verdict, decide_verdict
from judge.infra.sandbox import NodeSettings, Sandbox, SandboxLimits
from judge.packaging.dart_imports import ImportRules, find_forbidden_imports
from judge.packaging.submission import SubmissionInvalid, read_submission
from judge.packaging.zip_validator import ArchiveFile, ZipLimits, ZipRejected, validate_zip
from judge.parsers import make_parser

MAX_PUBLIC_MESSAGE = 2000  # SPEC §3.8

# Called with every event that matched the manifest: start (show the running test),
# pass and fail (save the test's row), done.
EventHandler = Callable[[RunEvent], None]


@dataclass(frozen=True)
class TaskImage:
    """What the runner needs from a task version."""

    image_tag: str
    manifest: Manifest
    time_limit_s: int
    memory_limit_mb: int | None = None  # None: the profile's limit
    import_rules: ImportRules | None = None  # None: the profile has no static check

    def to_json_data(self) -> dict[str, Any]:
        return {
            "image_tag": self.image_tag,
            "manifest": self.manifest.to_json_data(),
            "time_limit_s": self.time_limit_s,
            "memory_limit_mb": self.memory_limit_mb,
            "import_rules": self.import_rules and self.import_rules.to_json_data(),
        }

    @classmethod
    def from_json_data(cls, data: dict[str, Any]) -> Self:
        rules = data.get("import_rules")
        return cls(
            image_tag=data["image_tag"],
            manifest=Manifest.from_json_data(data["manifest"]),
            time_limit_s=data["time_limit_s"],
            memory_limit_mb=data.get("memory_limit_mb"),
            import_rules=ImportRules.from_json_data(rules) if rules else None,
        )


@dataclass(frozen=True)
class JudgeResult:
    judgement: Judgement
    results: tuple[RunEvent, ...]  # pass and fail events, one per test that finished
    compile_error: str | None
    wall_ms: int
    log: str  # for the teacher only: never shown to the student
    public_message: str = ""  # for the student: why the zip was rejected


def judge_zip(
    client: docker.DockerClient,
    task: TaskImage,
    profile: RunnerProfile,
    node: NodeSettings,
    archive: BinaryIO,
    limits: ZipLimits,
    on_event: EventHandler | None = None,
) -> JudgeResult:
    """Judge a student's zip. A broken zip, missing lib/ or forbidden import is rejected."""
    try:
        files = read_submission(validate_zip(archive, limits), profile.student_paths)
    except (ZipRejected, SubmissionInvalid) as error:
        return _rejected(task, str(error))
    if task.import_rules is not None:
        problems = find_forbidden_imports(files, task.import_rules)
        if problems:
            return _rejected(task, "\n".join(problems))
    elif profile.static_check is not None:
        raise ValueError(f"{task.image_tag} has no import rules for {profile.static_check}")
    return judge_submission(client, task, profile, node, files, on_event)


def _rejected(task: TaskImage, message: str) -> JudgeResult:
    judgement = Judgement(Verdict.REJECTED, tests_total=len(task.manifest.tests), tests_passed=0)
    if len(message) > MAX_PUBLIC_MESSAGE:
        message = message[: MAX_PUBLIC_MESSAGE - 3] + "..."
    return JudgeResult(
        judgement=judgement,
        results=(),
        compile_error=None,
        wall_ms=0,
        log=f"rejected before running:\n{message}\n",
        public_message=message,
    )


def judge_submission(
    client: docker.DockerClient,
    task: TaskImage,
    profile: RunnerProfile,
    node: NodeSettings,
    student_files: Sequence[ArchiveFile],
    on_event: EventHandler | None = None,
) -> JudgeResult:
    limits = SandboxLimits.for_profile(profile, node)
    if task.memory_limit_mb is not None:
        limits = dataclasses.replace(limits, memory_mb=task.memory_limit_mb)
    parser = make_parser(profile.parser)
    progress = RunProgress(task.manifest)
    events: list[RunEvent] = []

    def on_line(line: str) -> bool:
        event = parser.feed(line)
        if event is None:
            return False
        progress.feed(event)
        if progress.mismatch is not None:
            return True  # nothing after this can be trusted
        events.append(event)
        if on_event is not None:
            on_event(event)
        return progress.should_stop  # the first failed test ends the run

    with Sandbox(client, task.image_tag, profile.test_command, limits) as sandbox:
        sandbox.put_files(student_files)
        run = sandbox.run(task.time_limit_s, on_line=on_line)

    outcome = RunOutcome(
        events=tuple(events),
        timed_out=run.timed_out,
        oom_killed=run.oom_killed,
        compile_error=parser.compile_error,
        exit_code=run.exit_code,
    )
    judgement = decide_verdict(task.manifest, outcome)
    log = [f"$ {shlex.join(profile.test_command)}  ({run.describe()})"]
    log += [text.rstrip() for text in ("\n".join(parser.log), run.stderr) if text.strip()]
    detail = f" ({judgement.detail})" if judgement.detail else ""
    log.append(f"verdict: {judgement.verdict}{detail}")
    return JudgeResult(
        judgement=judgement,
        results=tuple(e for e in events if e.type in (EventType.PASS, EventType.FAIL)),
        compile_error=parser.compile_error,
        wall_ms=run.wall_ms,
        log="\n".join(log) + "\n",
    )
