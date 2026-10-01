"""Parser for `dart test --reporter json` and `flutter test --reporter json` output (SPEC §3.5).

Each output line is one JSON object (the dart test JSON reporter protocol). Tests come from
the combined test file, where every test file is wrapped in ``group('<file path>', f.main)``;
the parser strips that group from test names.

Dart also reports synthetic tests: "loading <file>" (compiling the suite) and
"(setUpAll)" / "(tearDownAll)". They are never shown as tests. Their ``hidden`` flag can't be
trusted: dart turns it off when they fail. So they are recognised by their shape instead.
"""

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from judge.core.events import EventType, RunEvent

_HOOK_NAMES = ("(setUpAll)", "(tearDownAll)")


@dataclass
class _Test:
    name: str  # name shown to the user; dart's full name for synthetic tests
    started_ms: int
    index: int | None = None  # None for synthetic tests
    is_loading: bool = False
    errors: list[str] = field(default_factory=list)


class DartJsonParser:
    """Turns dart test JSON output into run events, one line at a time.

    Visible tests are numbered from ``first_index`` in the order they start. ``done`` is
    emitted only when dart reports the whole run as successful, so an error outside the
    visible tests (a failing ``setUpAll``, ``tearDownAll`` or an error after a test
    finished) leaves the stream incomplete, and such a run is never accepted.
    """

    def __init__(self, stage: int = 1, first_index: int = 1) -> None:
        self.stage = stage
        self._next_index = first_index
        self._groups: dict[int, str] = {}
        self._tests: dict[int, _Test] = {}
        self.compile_error: str | None = None
        # index -> file path from the combined file's group, e.g. "hidden/02_cart_test.dart".
        self.test_files: dict[int, str] = {}
        # Prints, errors with stack traces and unexpected lines, for the teacher's log.
        self.log: list[str] = []

    def parse(self, lines: Iterable[str]) -> Iterator[RunEvent]:
        for line in lines:
            event = self.feed(line)
            if event is not None:
                yield event

    def feed(self, line: str) -> RunEvent | None:
        line = line.strip()
        if not line:
            return None
        try:
            message = json.loads(line)
        except ValueError:
            message = None
        if not isinstance(message, dict):
            self.log.append(f"unexpected output: {line}")
            return None
        try:
            return self._handle(message)
        except (KeyError, TypeError, ValueError) as error:
            self.log.append(f"unreadable event ({error!r}): {line}")
            return None

    def _handle(self, message: dict[str, Any]) -> RunEvent | None:
        match message["type"]:
            case "group":
                group = message["group"]
                self._groups[group["id"]] = group["name"]
            case "testStart":
                return self._on_test_start(message["test"], message["time"])
            case "error":
                self._on_error(message)
            case "print":
                test = self._tests.get(message["testID"])
                where = test.name if test else f"test {message['testID']}"
                self.log.append(f"[{where}] {message['messageType']}: {message['message']}")
            case "testDone":
                return self._on_test_done(message)
            case "done":
                if message["success"] is True:
                    return RunEvent(EventType.DONE, self.stage)
                self.log.append("dart test reported the run as failed")
        return None

    def _on_test_start(self, test: dict[str, Any], time_ms: int) -> RunEvent | None:
        full_name: str = test["name"]
        group_ids: list[int] = test["groupIDs"]
        if not group_ids:
            self._tests[test["id"]] = _Test(full_name, time_ms, is_loading=True)
            return None
        parent_group = self._groups.get(group_ids[-1], "")
        if full_name in {f"{parent_group} {hook}".lstrip() for hook in _HOOK_NAMES}:
            self._tests[test["id"]] = _Test(full_name, time_ms)
            return None

        file_path = self._groups.get(group_ids[1], "") if len(group_ids) > 1 else ""
        name = full_name.removeprefix(f"{file_path} ") if file_path else full_name
        name = name or full_name.strip()
        index = self._next_index
        self._next_index += 1
        self._tests[test["id"]] = _Test(name, time_ms, index=index)
        self.test_files[index] = file_path
        return RunEvent(EventType.START, self.stage, index, name)

    def _on_error(self, message: dict[str, Any]) -> None:
        test = self._tests.get(message["testID"])
        where = test.name if test else f"test {message['testID']}"
        self.log.append(f"[{where}] error: {message['error']}\n{message.get('stackTrace', '')}")
        if test is not None:
            test.errors.append(message["error"].strip())

    def _on_test_done(self, message: dict[str, Any]) -> RunEvent | None:
        test = self._tests.get(message["testID"])
        if test is None:
            self.log.append(f"testDone for an unknown test {message['testID']}")
            return None
        failed = message["result"] != "success"
        if test.index is None:
            if failed and test.is_loading:
                self.compile_error = "\n".join(test.errors) or f"{test.name}: {message['result']}"
            elif failed:
                self.log.append(f"[{test.name}] {message['result']}")
            return None

        duration_ms = max(0, message["time"] - test.started_ms)
        if failed or message["skipped"]:
            reason = "\n".join(test.errors) or (
                "test was skipped" if message["skipped"] else message["result"]
            )
            return RunEvent(EventType.FAIL, self.stage, test.index, test.name, duration_ms, reason)
        return RunEvent(EventType.PASS, self.stage, test.index, test.name, duration_ms)
