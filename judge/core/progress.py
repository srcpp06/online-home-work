"""Follows the event stream of a run and checks it against the manifest (SPEC §3.4, §3.7)."""

from collections.abc import Collection
from dataclasses import dataclass

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest

_START = frozenset({EventType.START})
_RESULT = frozenset({EventType.PASS, EventType.FAIL})
_DONE = frozenset({EventType.DONE})


@dataclass(frozen=True)
class _Step:
    """One expected event: start or result of test ``index``, or ``done`` of ``stage``."""

    types: frozenset[EventType]
    stage: int
    index: int | None = None
    name: str = ""

    def accepts(self, event: RunEvent) -> bool:
        return (
            event.type in self.types
            and event.stage == self.stage
            and event.index == self.index
            and event.name == self.name
        )


class RunProgress:
    """Checks events one by one against the order the manifest promises.

    The only valid stream is: for every test, ``start`` then ``pass`` or ``fail``;
    right after the last test of a stage, ``done`` of that stage. The first ``fail``
    ends the run (the runner kills the container), so later events are ignored.
    Anything else is a mismatch, and the run can't be trusted.
    """

    def __init__(self, manifest: Manifest) -> None:
        self._steps = _expected_steps(manifest)
        self._position = 0
        self.passed = 0
        self.failed_index: int | None = None
        self.running_index: int | None = None
        self.mismatch: str | None = None

    @property
    def should_stop(self) -> bool:
        """True when the run must be stopped now: a test failed or the stream broke."""
        return self.failed_index is not None or self.mismatch is not None

    @property
    def complete(self) -> bool:
        """True when every test passed and every stage reported ``done``."""
        return self._position == len(self._steps) and not self.should_stop

    def feed(self, event: RunEvent) -> None:
        if self.should_stop:
            return
        if self._position == len(self._steps):
            self.mismatch = f"unexpected {_describe_event(event)} after the last stage finished"
            return
        step = self._steps[self._position]
        if not step.accepts(event):
            self.mismatch = f"expected {_describe_step(step)}, got {_describe_event(event)}"
            return

        self._position += 1
        if event.type == EventType.START:
            self.running_index = event.index
        elif event.type == EventType.PASS:
            self.passed += 1
            self.running_index = None
        elif event.type == EventType.FAIL:
            self.failed_index = event.index
            self.running_index = None


def _expected_steps(manifest: Manifest) -> list[_Step]:
    tests = manifest.tests
    steps: list[_Step] = []
    for index, test in enumerate(tests, start=1):
        steps.append(_Step(_START, test.stage, index, test.name))
        steps.append(_Step(_RESULT, test.stage, index, test.name))
        if index == len(tests) or tests[index].stage != test.stage:
            steps.append(_Step(_DONE, test.stage))
    return steps


def _describe(types: Collection[EventType], stage: int, index: int | None, name: str) -> str:
    kinds = "/".join(t for t in EventType if t in types)
    if index is None:
        return f"{kinds} of stage {stage}"
    return f"{kinds} of test {index} {name!r} (stage {stage})"


def _describe_step(step: _Step) -> str:
    return _describe(step.types, step.stage, step.index, step.name)


def _describe_event(event: RunEvent) -> str:
    return _describe({event.type}, event.stage, event.index, event.name)
