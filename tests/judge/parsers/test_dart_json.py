"""dart_json parser against real `dart test --reporter json` output.

Fixtures are recorded by scripts/record-dart-json-fixtures.sh (Dart version in
fixtures/dart_json/VERSION). Each one runs the same tests against a different lib/.
"""

import json
from pathlib import Path

import pytest

from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.verdict import RunOutcome, Verdict, decide_verdict
from judge.parsers.dart_json import DartJsonParser

FIXTURES = Path(__file__).parent / "fixtures" / "dart_json"

PUBLIC_FILE = "public/01_cart_test.dart"
HIDDEN_FILE = "hidden/02_discount_test.dart"
NAMES = (
    "Savat boʻsh boʻlsa jami 0 ga teng",
    "Mahsulot qoʻshilganda jami ortadi",
    "Chegirma 10% chegirma qoʻllanadi",
    "Chegirma 0% chegirmada narx oʻzgarmaydi",
)
MANIFEST = Manifest(
    (
        ManifestTest(NAMES[0], 1, Visibility.PUBLIC),
        ManifestTest(NAMES[1], 1, Visibility.PUBLIC),
        ManifestTest(NAMES[2], 1, Visibility.HIDDEN),
        ManifestTest(NAMES[3], 1, Visibility.HIDDEN),
    )
)


def fixture_lines(name: str) -> list[str]:
    return (FIXTURES / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()


def parse_fixture(name: str, **kwargs: int) -> tuple[DartJsonParser, list[RunEvent]]:
    parser = DartJsonParser(**kwargs)
    return parser, list(parser.parse(fixture_lines(name)))


def shape(events: list[RunEvent]) -> list[tuple[str, int | None, str]]:
    return [(str(e.type), e.index, e.name) for e in events]


def passing(*indexes: int) -> list[tuple[str, int | None, str]]:
    result: list[tuple[str, int | None, str]] = []
    for index in indexes:
        result += [("start", index, NAMES[index - 1]), ("pass", index, NAMES[index - 1])]
    return result


def test_all_tests_pass() -> None:
    parser, events = parse_fixture("pass")

    assert shape(events) == [*passing(1, 2, 3, 4), ("done", None, "")]
    assert parser.compile_error is None


def test_file_group_is_stripped_but_teacher_groups_stay() -> None:
    parser, events = parse_fixture("pass")

    assert events[0].name == "Savat boʻsh boʻlsa jami 0 ga teng"
    assert events[4].name == "Chegirma 10% chegirma qoʻllanadi"
    assert parser.test_files == {1: PUBLIC_FILE, 2: PUBLIC_FILE, 3: HIDDEN_FILE, 4: HIDDEN_FILE}


def test_duration_comes_from_start_and_done_times() -> None:
    _, events = parse_fixture("pass")

    first_pass = events[1]
    assert first_pass.duration_ms == 537 - 523
    assert all(e.duration_ms is not None for e in events if e.type == EventType.PASS)


def test_failed_expectation_is_fail_with_the_assertion_message() -> None:
    _, events = parse_fixture("fail_public")

    assert shape(events[:4]) == [*passing(1), ("start", 2, NAMES[1]), ("fail", 2, NAMES[1])]
    assert events[3].message == "Expected: <4000>\n  Actual: <2500>"


def test_failed_run_has_no_done() -> None:
    _, events = parse_fixture("fail_public")

    assert events[-1].type != EventType.DONE


def test_exception_is_fail_without_the_stack_trace() -> None:
    parser, events = parse_fixture("exception")

    fail = events[5]
    assert (fail.type, fail.index) == (EventType.FAIL, 3)
    assert fail.message == "UnimplementedError: chegirma hali yozilmagan"
    assert any("Cart.totalWithDiscount" in entry for entry in parser.log)


def test_compile_error_has_no_test_events() -> None:
    parser, events = parse_fixture("compile_error")

    assert events == []
    assert parser.compile_error is not None
    assert "The getter 'total' isn't defined for the type 'Cart'" in parser.compile_error


def test_prints_go_to_the_log_only() -> None:
    parser, events = parse_fixture("print")

    assert shape(events) == [*passing(1, 2, 3, 4), ("done", None, "")]
    assert f"[{NAMES[1]}] print: qoʻshildi: 1500" in parser.log
    assert any("qoʻshildi: 10000" in entry for entry in parser.log)


@pytest.mark.parametrize(
    ("fixture", "passed"),
    [
        pytest.param("setup_all_error", (1, 2), id="setUpAll"),
        pytest.param("teardown_all_error", (1, 2, 3, 4), id="tearDownAll"),
    ],
)
def test_hook_error_is_not_a_test_and_leaves_the_run_without_done(
    fixture: str, passed: tuple[int, ...]
) -> None:
    parser, events = parse_fixture(fixture)

    assert shape(events) == passing(*passed)
    assert parser.compile_error is None
    assert any("error:" in entry for entry in parser.log)


def test_second_stage_continues_numbering() -> None:
    parser, events = parse_fixture("pass", stage=2, first_index=5)

    assert [e.index for e in events if e.type == EventType.START] == [5, 6, 7, 8]
    assert {e.stage for e in events} == {2}
    assert set(parser.test_files) == {5, 6, 7, 8}


@pytest.mark.parametrize(
    ("fixture", "verdict", "failed_test"),
    [
        ("pass", Verdict.ACCEPTED, None),
        ("print", Verdict.ACCEPTED, None),
        ("fail_public", Verdict.WRONG_ANSWER, 2),
        ("fail_hidden", Verdict.WRONG_ANSWER, 3),
        ("exception", Verdict.WRONG_ANSWER, 3),
        ("compile_error", Verdict.COMPILE_ERROR, None),
        ("setup_all_error", Verdict.RUNTIME_ERROR, None),
        ("teardown_all_error", Verdict.RUNTIME_ERROR, None),
    ],
)
def test_recorded_run_gets_the_expected_verdict(
    fixture: str, verdict: Verdict, failed_test: int | None
) -> None:
    parser, events = parse_fixture(fixture)

    outcome = RunOutcome(events=tuple(events), compile_error=parser.compile_error)
    judgement = decide_verdict(MANIFEST, outcome)

    assert (judgement.verdict, judgement.failed_test_index) == (verdict, failed_test)


# Edge cases the recorded runs don't cover. Lines follow the same protocol.


def line(**message: object) -> str:
    return json.dumps(message)


def start_line(test_id: int, name: str, group_ids: list[int]) -> str:
    return line(
        type="testStart",
        time=10,
        test={"id": test_id, "name": name, "groupIDs": group_ids, "metadata": {"skip": False}},
    )


HEADER = [
    line(type="group", time=1, group={"id": 1, "name": "", "parentID": None}),
    line(type="group", time=1, group={"id": 2, "name": PUBLIC_FILE, "parentID": 1}),
]


def test_skipped_test_is_never_a_pass() -> None:
    lines = [
        *HEADER,
        start_line(3, f"{PUBLIC_FILE} jami", [1, 2]),
        line(type="testDone", time=12, testID=3, result="success", skipped=True, hidden=False),
    ]

    events = list(DartJsonParser().parse(lines))

    assert shape(events) == [("start", 1, "jami"), ("fail", 1, "jami")]
    assert events[1].message == "test was skipped"


def test_hook_inside_a_teacher_group_is_not_a_test() -> None:
    lines = [
        *HEADER,
        line(type="group", time=1, group={"id": 3, "name": f"{PUBLIC_FILE} Savat", "parentID": 2}),
        start_line(4, f"{PUBLIC_FILE} Savat (setUpAll)", [1, 2, 3]),
        line(type="testDone", time=11, testID=4, result="success", skipped=False, hidden=True),
    ]

    assert list(DartJsonParser().parse(lines)) == []


@pytest.mark.parametrize(
    "bad_line",
    [
        pytest.param("Resolving dependencies...", id="not-json"),
        pytest.param('"just a string"', id="json-but-not-an-object"),
        pytest.param('{"type": "testStart", "time": 1}', id="missing-fields"),
        pytest.param('{"time": 1}', id="missing-type"),
        pytest.param(
            '{"type": "testDone", "testID": 99, "result": "success", "time": 1}',
            id="unknown-test",
        ),
    ],
)
def test_unexpected_line_is_logged_and_ignored(bad_line: str) -> None:
    parser = DartJsonParser()

    assert list(parser.parse([bad_line])) == []
    assert len(parser.log) == 1


def test_unknown_event_types_are_ignored() -> None:
    parser = DartJsonParser()

    assert list(parser.parse([line(type="debug", time=1), line(type="allSuites", count=1)])) == []
    assert parser.log == []


def test_blank_lines_are_ignored() -> None:
    parser = DartJsonParser()

    assert list(parser.parse(["", "   "])) == []
    assert parser.log == []
