import pytest

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.progress import RunProgress

ONE_STAGE = Manifest(
    (
        ManifestTest("a", 1, Visibility.PUBLIC),
        ManifestTest("b", 1, Visibility.HIDDEN),
    )
)
TWO_STAGES = Manifest(
    (
        ManifestTest("a", 1, Visibility.PUBLIC),
        ManifestTest("w", 2, Visibility.PUBLIC),
    )
)


def start(index: int, name: str, stage: int = 1) -> RunEvent:
    return RunEvent(EventType.START, stage, index, name)


def passed(index: int, name: str, stage: int = 1) -> RunEvent:
    return RunEvent(EventType.PASS, stage, index, name, duration_ms=3)


def failed(index: int, name: str, stage: int = 1) -> RunEvent:
    return RunEvent(EventType.FAIL, stage, index, name, message="Expected: 0 Actual: 1")


def done(stage: int = 1) -> RunEvent:
    return RunEvent(EventType.DONE, stage)


def feed_all(manifest: Manifest, events: list[RunEvent]) -> RunProgress:
    progress = RunProgress(manifest)
    for event in events:
        progress.feed(event)
    return progress


def test_new_progress_has_nothing_yet() -> None:
    progress = RunProgress(ONE_STAGE)

    assert (progress.passed, progress.running_index, progress.failed_index) == (0, None, None)
    assert not progress.complete
    assert not progress.should_stop


def test_all_tests_pass_in_one_stage() -> None:
    progress = feed_all(
        ONE_STAGE, [start(1, "a"), passed(1, "a"), start(2, "b"), passed(2, "b"), done()]
    )

    assert progress.complete
    assert progress.passed == 2
    assert progress.mismatch is None


def test_all_tests_pass_in_two_stages() -> None:
    progress = feed_all(
        TWO_STAGES,
        [start(1, "a"), passed(1, "a"), done(1), start(2, "w", 2), passed(2, "w", 2), done(2)],
    )

    assert progress.complete
    assert progress.passed == 2


def test_running_test_is_known_between_start_and_result() -> None:
    progress = feed_all(ONE_STAGE, [start(1, "a"), passed(1, "a"), start(2, "b")])

    assert progress.running_index == 2
    assert not progress.complete


def test_all_passed_but_no_done_is_not_complete() -> None:
    progress = feed_all(ONE_STAGE, [start(1, "a"), passed(1, "a"), start(2, "b"), passed(2, "b")])

    assert progress.passed == 2
    assert not progress.complete


def test_first_failure_stops_the_run_and_later_events_are_ignored() -> None:
    progress = feed_all(
        ONE_STAGE, [start(1, "a"), failed(1, "a"), start(2, "b"), passed(2, "b"), done()]
    )

    assert progress.failed_index == 1
    assert progress.passed == 0
    assert progress.should_stop
    assert not progress.complete
    assert progress.mismatch is None


@pytest.mark.parametrize(
    ("manifest", "events", "reason"),
    [
        pytest.param(
            ONE_STAGE,
            [start(1, "fake")],
            "expected start of test 1 'a' (stage 1), got start of test 1 'fake' (stage 1)",
            id="unknown-test-name",
        ),
        pytest.param(
            ONE_STAGE,
            [start(2, "b")],
            "expected start of test 1 'a'",
            id="tests-out-of-order",
        ),
        pytest.param(
            ONE_STAGE,
            [passed(1, "a")],
            "expected start of test 1 'a' (stage 1), got pass of test 1 'a' (stage 1)",
            id="result-without-start",
        ),
        pytest.param(
            ONE_STAGE,
            [start(1, "a"), passed(1, "a"), passed(1, "a")],
            "expected start of test 2 'b'",
            id="result-reported-twice",
        ),
        pytest.param(
            ONE_STAGE,
            [start(1, "a"), start(2, "b")],
            "expected pass/fail of test 1 'a' (stage 1), got start of test 2 'b'",
            id="next-test-before-result",
        ),
        pytest.param(
            ONE_STAGE,
            [start(1, "a"), passed(1, "a"), done()],
            "expected start of test 2 'b' (stage 1), got done of stage 1",
            id="stage-done-too-early",
        ),
        pytest.param(
            TWO_STAGES,
            [start(1, "a"), passed(1, "a"), start(2, "w", 2)],
            "expected done of stage 1",
            id="stage-2-before-stage-1-done",
        ),
        pytest.param(
            TWO_STAGES,
            [start(1, "a", 2)],
            "got start of test 1 'a' (stage 2)",
            id="wrong-stage",
        ),
        pytest.param(
            ONE_STAGE,
            [start(1, "a"), passed(1, "a"), start(2, "b"), passed(2, "b"), done(), start(3, "c")],
            "unexpected start of test 3 'c' (stage 1) after the last stage finished",
            id="event-after-the-end",
        ),
    ],
)
def test_stream_that_breaks_the_manifest_is_a_mismatch(
    manifest: Manifest, events: list[RunEvent], reason: str
) -> None:
    progress = feed_all(manifest, events)

    assert progress.mismatch is not None
    assert reason in progress.mismatch
    assert progress.should_stop
    assert not progress.complete


def test_events_after_a_mismatch_are_ignored() -> None:
    progress = feed_all(ONE_STAGE, [start(1, "fake"), start(1, "a"), passed(1, "a"), start(2, "b")])

    assert progress.passed == 0
    assert "'fake'" in (progress.mismatch or "")
