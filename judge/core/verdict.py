"""Verdicts and how the outcome of a run turns into one (SPEC §2, §3.4)."""

from dataclasses import dataclass
from enum import StrEnum

from judge.core.events import RunEvent
from judge.core.manifest import Manifest
from judge.core.progress import RunProgress


class Verdict(StrEnum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    COMPILE_ERROR = "compile_error"
    TIME_LIMIT = "time_limit"
    MEMORY_LIMIT = "memory_limit"
    RUNTIME_ERROR = "runtime_error"
    REJECTED = "rejected"  # invalid zip or forbidden code, decided before the run
    SYSTEM_ERROR = "system_error"  # platform failure, the submission is judged again

    @property
    def counts_as_attempt(self) -> bool:
        """Rejected and system error submissions don't use up an attempt."""
        return self not in (Verdict.REJECTED, Verdict.SYSTEM_ERROR)


@dataclass(frozen=True)
class RunOutcome:
    """What the runner observed while running the tests of one submission."""

    events: tuple[RunEvent, ...] = ()
    timed_out: bool = False
    oom_killed: bool = False
    compile_error: str | None = None  # compiler output, None when everything compiled
    exit_code: int | None = 0  # of the test process; anything but 0 is never accepted


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    tests_total: int
    tests_passed: int
    # 1-based; the test that failed, or the one running when the run stopped.
    failed_test_index: int | None = None
    failed_test_name: str = ""
    # Technical reason for the teacher's log. Never shown to the student.
    detail: str = ""


def decide_verdict(manifest: Manifest, outcome: RunOutcome) -> Judgement:
    """Decide the verdict of a finished run, checking conditions in SPEC §3.4 order."""
    progress = RunProgress(manifest)
    for event in outcome.events:
        progress.feed(event)

    if outcome.timed_out:
        verdict, detail = Verdict.TIME_LIMIT, "wall-clock time limit exceeded"
    elif outcome.oom_killed:
        verdict, detail = Verdict.MEMORY_LIMIT, "killed by the out-of-memory killer"
    elif outcome.compile_error is not None:
        verdict, detail = Verdict.COMPILE_ERROR, "tests failed to load or compile"
    elif progress.mismatch is not None:
        verdict, detail = Verdict.RUNTIME_ERROR, f"event stream broke: {progress.mismatch}"
    elif progress.failed_index is not None:
        verdict, detail = Verdict.WRONG_ANSWER, ""
    elif not progress.complete:
        verdict, detail = Verdict.RUNTIME_ERROR, "event stream ended before all tests finished"
    elif outcome.exit_code != 0:
        verdict, detail = Verdict.RUNTIME_ERROR, f"test process exited with {outcome.exit_code}"
    else:
        verdict, detail = Verdict.ACCEPTED, ""

    stopped_at = None
    if verdict not in (Verdict.ACCEPTED, Verdict.COMPILE_ERROR):
        stopped_at = progress.failed_index or progress.running_index
    return Judgement(
        verdict=verdict,
        tests_total=len(manifest.tests),
        tests_passed=progress.passed,
        failed_test_index=stopped_at,
        failed_test_name=manifest.tests[stopped_at - 1].name if stopped_at else "",
        detail=detail,
    )
