"""The journal (docs/UI.md §4): one mark per student and assignment, rows in acmp order."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from apps.submissions.journal import Cell, build_rows, cell_for, column_letter

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@dataclass
class Sub:
    """The fields of a Submission the journal reads."""

    verdict: str = ""
    status: str = "finished"
    is_late: bool = False
    pk: int = 0
    student_id: int = 1
    assignment_id: int = 1
    created_at: datetime = T0


def subs(*verdicts: str, late: bool = False) -> list[Sub]:
    return [
        Sub(verdict=v, pk=n, is_late=late, created_at=T0 + timedelta(minutes=n))
        for n, v in enumerate(verdicts, start=1)
    ]


@pytest.mark.parametrize(
    ("verdicts", "mark", "tone"),
    [
        ((), "", ""),
        (("accepted",), "+", "pass"),
        (("wrong_answer", "compile_error", "accepted"), "+2", "pass"),
        (("wrong_answer", "time_limit", "runtime_error"), "\u22123", "fail"),
        # Rejected and system errors are no attempts: they change nothing.
        (("rejected", "system_error", "accepted"), "+", "pass"),
        (("rejected",), "", ""),
        # What came after the first accepted solution doesn't count.
        (("accepted", "wrong_answer"), "+", "pass"),
    ],
)
def test_marks(verdicts: tuple[str, ...], mark: str, tone: str) -> None:
    cell = cell_for(subs(*verdicts))

    assert (cell.mark, cell.tone) == (mark, tone)


def test_a_solution_being_judged_shows_dots() -> None:
    history = [*subs("wrong_answer"), Sub(status="running", pk=9, created_at=T0 + timedelta(1))]

    cell = cell_for(history)

    assert (cell.mark, cell.submission_id) == ("…", 9)


def test_an_accepted_cell_opens_the_accepted_solution_and_tells_if_it_was_late() -> None:
    cell = cell_for(subs("wrong_answer", "accepted", "wrong_answer", late=True))

    assert (cell.submission_id, cell.late) == (2, True)
    assert cell.title == "Qabul qilindi, oldin 1 ta xato; kechikkan"


def test_a_failed_cell_opens_the_last_attempt() -> None:
    cell = cell_for(subs("wrong_answer", "compile_error"))

    assert cell.submission_id == 2
    assert cell.title == "2 ta urinish, hali qabul yoʻq"


def test_columns_are_letters() -> None:
    assert [column_letter(i) for i in (0, 1, 25, 26, 27)] == ["A", "B", "Z", "AA", "AB"]


@dataclass(frozen=True)
class Student:
    pk: int
    display_name: str


def test_rows_go_by_solved_then_attempts_then_name() -> None:
    karimova, aliyev, toshev, bobur = (
        Student(1, "Karimova Sora"),
        Student(2, "Aliyev Vali"),
        Student(3, "Toshev Anvar"),
        Student(4, "Bobur Ergashev"),
    )
    history = [
        # Karimova: A at once, B after one failure -> 2 solved, 3 attempts.
        Sub("accepted", student_id=1, assignment_id=10),
        Sub("wrong_answer", student_id=1, assignment_id=20),
        Sub("accepted", student_id=1, assignment_id=20, created_at=T0 + timedelta(1)),
        # Aliyev: A and B at once -> 2 solved, 2 attempts.
        Sub("accepted", student_id=2, assignment_id=10),
        Sub("accepted", student_id=2, assignment_id=20),
        # Toshev: three failures on A.
        *(Sub("wrong_answer", student_id=3, assignment_id=10) for _ in range(3)),
    ]

    rows = build_rows([karimova, aliyev, toshev, bobur], [10, 20], history)

    assert [row.student.display_name for row in rows] == [
        "Aliyev Vali",
        "Karimova Sora",
        "Bobur Ergashev",
        "Toshev Anvar",
    ]
    assert [(row.solved, row.attempts) for row in rows] == [(2, 2), (2, 3), (0, 0), (0, 3)]
    assert [cell.mark for cell in rows[1].cells] == ["+", "+1"]
    assert rows[2].cells == [Cell(), Cell()]
