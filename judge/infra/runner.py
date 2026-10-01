"""Judges one submission inside its task image (SPEC §3.4, steps 3-7).

Static checks and choosing the student's files happen before this; here the files go into
a fresh sandbox, the tests run, and every event is checked against the manifest as it
arrives. The run stops at the first failed test, or as soon as the stream stops matching
the manifest. Results reach the caller live, test by test.
"""

import dataclasses
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import docker

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest
from judge.core.profile import RunnerProfile
from judge.core.progress import RunProgress
from judge.core.verdict import Judgement, RunOutcome, decide_verdict
from judge.infra.sandbox import NodeSettings, Sandbox, SandboxLimits
from judge.packaging.zip_validator import ArchiveFile
from judge.parsers import make_parser

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


@dataclass(frozen=True)
class JudgeResult:
    judgement: Judgement
    results: tuple[RunEvent, ...]  # pass and fail events, one per test that finished
    compile_error: str | None
    wall_ms: int
    log: str  # for the teacher only: never shown to the student


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
