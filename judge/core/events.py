"""Common event format that every parser produces (SPEC §3.5)."""

from dataclasses import dataclass
from enum import StrEnum


class EventType(StrEnum):
    START = "start"
    PASS = "pass"  # noqa: S105 -- a test result, not a password
    FAIL = "fail"
    DONE = "done"  # a stage finished normally


@dataclass(frozen=True)
class RunEvent:
    """One event of a test run.

    ``index`` is the 1-based position of the test in the manifest. A ``done`` event
    belongs to a stage, not to a test: its ``index`` is ``None`` and ``name`` is empty.
    """

    type: EventType
    stage: int
    index: int | None = None
    name: str = ""
    duration_ms: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.stage < 1:
            raise ValueError(f"stage must be >= 1, got {self.stage}")
        if self.type == EventType.DONE:
            if self.index is not None or self.name:
                raise ValueError("a done event has no test index or name")
        elif self.index is None or self.index < 1 or not self.name:
            raise ValueError(f"a {self.type} event needs a test index >= 1 and a name")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError(f"duration_ms must be >= 0, got {self.duration_ms}")
