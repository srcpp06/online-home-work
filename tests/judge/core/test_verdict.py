import pytest

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.verdict import Judgement, RunOutcome, Verdict, decide_verdict

MANIFEST = Manifest(
    (
        ManifestTest("savat bo'sh", 1, Visibility.PUBLIC),
        ManifestTest("jami narx", 1, Visibility.PUBLIC),
        ManifestTest("chegirma", 1, Visibility.HIDDEN),
    )
)


def run_events(manifest: Manifest, fail_at: int | None = None) -> tuple[RunEvent, ...]:
    """The stream a correct runner produces; it stops at the first failure."""
    events: list[RunEvent] = []
    tests = manifest.tests
    for index, test in enumerate(tests, start=1):
        events.append(RunEvent(EventType.START, test.stage, index, test.name))
        if index == fail_at:
            events.append(RunEvent(EventType.FAIL, test.stage, index, test.name, message="x"))
            return tuple(events)
        events.append(RunEvent(EventType.PASS, test.stage, index, test.name))
        if index == len(tests) or tests[index].stage != test.stage:
            events.append(RunEvent(EventType.DONE, test.stage))
    return tuple(events)


def test_verdict_values_match_the_spec() -> None:
    assert [v.value for v in Verdict] == [
        "accepted",
        "wrong_answer",
        "compile_error",
        "time_limit",
        "memory_limit",
        "runtime_error",
        "rejected",
        "system_error",
    ]


@pytest.mark.parametrize(
    ("verdict", "counts"),
    [
        (Verdict.ACCEPTED, True),
        (Verdict.WRONG_ANSWER, True),
        (Verdict.COMPILE_ERROR, True),
        (Verdict.TIME_LIMIT, True),
        (Verdict.MEMORY_LIMIT, True),
        (Verdict.RUNTIME_ERROR, True),
        (Verdict.REJECTED, False),
        (Verdict.SYSTEM_ERROR, False),
    ],
)
def test_only_rejected_and_system_error_do_not_use_an_attempt(
    verdict: Verdict, counts: bool
) -> None:
    assert verdict.counts_as_attempt is counts


def test_all_tests_pass_is_accepted() -> None:
    judgement = decide_verdict(MANIFEST, RunOutcome(events=run_events(MANIFEST)))

    assert judgement == Judgement(Verdict.ACCEPTED, tests_total=3, tests_passed=3)


def test_two_stage_run_is_accepted_only_after_both_stages() -> None:
    manifest = Manifest(
        (ManifestTest("mantiq", 1, Visibility.PUBLIC), ManifestTest("widget", 2, Visibility.PUBLIC))
    )
    events = run_events(manifest)

    assert decide_verdict(manifest, RunOutcome(events=events)).verdict == Verdict.ACCEPTED
    stage_1_only = events[:3]
    assert decide_verdict(manifest, RunOutcome(events=stage_1_only)).verdict == (
        Verdict.RUNTIME_ERROR
    )


def test_failed_test_is_wrong_answer_at_that_test() -> None:
    judgement = decide_verdict(MANIFEST, RunOutcome(events=run_events(MANIFEST, fail_at=2)))

    assert judgement == Judgement(
        Verdict.WRONG_ANSWER,
        tests_total=3,
        tests_passed=1,
        failed_test_index=2,
        failed_test_name="jami narx",
    )


def test_timeout_points_at_the_running_test() -> None:
    running_test_2 = run_events(MANIFEST)[:3]

    judgement = decide_verdict(MANIFEST, RunOutcome(events=running_test_2, timed_out=True))

    assert judgement.verdict == Verdict.TIME_LIMIT
    assert (judgement.tests_passed, judgement.failed_test_index) == (1, 2)
    assert judgement.failed_test_name == "jami narx"


def test_timeout_before_any_test_has_no_failed_test() -> None:
    judgement = decide_verdict(MANIFEST, RunOutcome(timed_out=True))

    assert judgement.verdict == Verdict.TIME_LIMIT
    assert (judgement.failed_test_index, judgement.failed_test_name) == (None, "")


def test_oom_kill_is_memory_limit() -> None:
    running_test_3 = run_events(MANIFEST)[:5]

    judgement = decide_verdict(MANIFEST, RunOutcome(events=running_test_3, oom_killed=True))

    assert judgement.verdict == Verdict.MEMORY_LIMIT
    assert judgement.failed_test_index == 3


def test_compile_error_has_no_failed_test() -> None:
    outcome = RunOutcome(compile_error="The method 'total' isn't defined for the type 'Cart'")

    judgement = decide_verdict(MANIFEST, outcome)

    assert judgement.verdict == Verdict.COMPILE_ERROR
    assert (judgement.tests_passed, judgement.failed_test_index) == (0, None)


def test_no_events_at_all_is_runtime_error() -> None:
    judgement = decide_verdict(MANIFEST, RunOutcome())

    assert judgement.verdict == Verdict.RUNTIME_ERROR
    assert "ended before all tests finished" in judgement.detail


def test_crash_in_the_middle_of_a_test_is_runtime_error_at_that_test() -> None:
    judgement = decide_verdict(MANIFEST, RunOutcome(events=run_events(MANIFEST)[:3]))

    assert judgement.verdict == Verdict.RUNTIME_ERROR
    assert judgement.failed_test_index == 2


def test_spoofed_stream_is_never_accepted() -> None:
    """Every test reported as passed, but the names are not the task's tests."""
    spoofed = tuple(
        RunEvent(event.type, event.stage, event.index, f"{event.name} (fake)")
        if event.index is not None
        else event
        for event in run_events(MANIFEST)
    )

    judgement = decide_verdict(MANIFEST, RunOutcome(events=spoofed))

    assert judgement.verdict == Verdict.RUNTIME_ERROR
    assert judgement.tests_passed == 0
    assert "event stream broke" in judgement.detail


def test_extra_test_after_the_end_is_never_accepted() -> None:
    extra = RunEvent(EventType.PASS, 1, 4, "qo'shimcha")
    events = (*run_events(MANIFEST), extra)

    assert decide_verdict(MANIFEST, RunOutcome(events=events)).verdict == Verdict.RUNTIME_ERROR


@pytest.mark.parametrize("exit_code", [1, 137, None])
def test_complete_stream_with_a_failed_process_is_never_accepted(exit_code: int | None) -> None:
    outcome = RunOutcome(events=run_events(MANIFEST), exit_code=exit_code)

    judgement = decide_verdict(MANIFEST, outcome)

    assert judgement.verdict == Verdict.RUNTIME_ERROR
    assert f"exited with {exit_code}" in judgement.detail


def test_failed_test_stays_wrong_answer_despite_the_exit_code() -> None:
    outcome = RunOutcome(events=run_events(MANIFEST, fail_at=1), exit_code=1)

    assert decide_verdict(MANIFEST, outcome).verdict == Verdict.WRONG_ANSWER


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        pytest.param(
            RunOutcome(timed_out=True, oom_killed=True, compile_error="e"),
            Verdict.TIME_LIMIT,
            id="time-limit-first",
        ),
        pytest.param(
            RunOutcome(oom_killed=True, compile_error="e"),
            Verdict.MEMORY_LIMIT,
            id="then-memory-limit",
        ),
        pytest.param(
            RunOutcome(events=run_events(MANIFEST, fail_at=1), compile_error="e"),
            Verdict.COMPILE_ERROR,
            id="then-compile-error",
        ),
        pytest.param(
            RunOutcome(events=(RunEvent(EventType.START, 1, 1, "fake"),)),
            Verdict.RUNTIME_ERROR,
            id="then-broken-stream",
        ),
    ],
)
def test_verdict_priority_follows_the_spec(outcome: RunOutcome, expected: Verdict) -> None:
    assert decide_verdict(MANIFEST, outcome).verdict == expected
