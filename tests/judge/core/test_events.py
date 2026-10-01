import pytest

from judge.core.events import EventType, RunEvent


def test_event_types_match_the_common_format() -> None:
    assert [t.value for t in EventType] == ["start", "pass", "fail", "done"]


@pytest.mark.parametrize("event_type", [EventType.START, EventType.PASS, EventType.FAIL])
def test_test_event_keeps_its_fields(event_type: EventType) -> None:
    event = RunEvent(event_type, stage=1, index=2, name="jami", duration_ms=15, message="x")

    assert (event.type, event.stage, event.index, event.name) == (event_type, 1, 2, "jami")
    assert (event.duration_ms, event.message) == (15, "x")


def test_done_event_belongs_to_a_stage_only() -> None:
    event = RunEvent(EventType.DONE, stage=2)

    assert (event.index, event.name) == (None, "")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"index": 1},
        {"name": "jami"},
    ],
)
def test_done_event_rejects_test_fields(kwargs: dict) -> None:
    with pytest.raises(ValueError, match="no test index or name"):
        RunEvent(EventType.DONE, stage=1, **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "jami"},
        {"index": 0, "name": "jami"},
        {"index": 1},
    ],
)
def test_test_event_needs_index_and_name(kwargs: dict) -> None:
    with pytest.raises(ValueError, match="needs a test index"):
        RunEvent(EventType.START, stage=1, **kwargs)


def test_stage_starts_at_one() -> None:
    with pytest.raises(ValueError, match="stage"):
        RunEvent(EventType.DONE, stage=0)


def test_duration_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="duration_ms"):
        RunEvent(EventType.PASS, stage=1, index=1, name="jami", duration_ms=-1)
