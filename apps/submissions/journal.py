"""The class journal (docs/UI.md §4): students down, assignments across, one mark each.

    +    accepted at the first attempt       +2   accepted after 2 failed attempts
    -3   3 attempts, none accepted yet       …    a solution is being judged
    (empty) no attempt yet

Rejected and system error solutions are no attempts, so they leave the mark as it was.
Nothing after the first accepted solution changes the mark. Pure: the view loads the rows.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from judge.core.verdict import Verdict

ACTIVE = ("queued", "running")
MINUS = "\u2212"  # shown as a real minus sign, not a hyphen


class SubmissionLike(Protocol):
    pk: int
    student_id: int
    assignment_id: int
    status: str
    verdict: str
    is_late: bool
    created_at: datetime


class StudentLike(Protocol):
    pk: int
    display_name: str


@dataclass(frozen=True)
class Cell:
    mark: str = ""
    tone: str = ""  # pass, fail or "" (the design system's tone-* names)
    late: bool = False  # the accepted solution came after the deadline
    submission_id: int | None = None  # what the cell opens: the accepted one, else the last
    title: str = ""  # the mark in words, for the tooltip and screen readers
    attempts: int = 0


@dataclass(frozen=True)
class Row:
    student: StudentLike
    cells: list[Cell] = field(default_factory=list)

    @property
    def solved(self) -> int:
        return sum(1 for cell in self.cells if cell.tone == "pass")

    @property
    def attempts(self) -> int:
        return sum(cell.attempts for cell in self.cells)


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, as in a spreadsheet."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def cell_for(history: Sequence[SubmissionLike]) -> Cell:
    """One student's solutions to one assignment, oldest first."""
    counted = [s for s in history if s.status in ACTIVE or _counts(s.verdict)]
    for failures, submission in enumerate(counted):
        if submission.verdict == Verdict.ACCEPTED:
            title = "Qabul qilindi" + (f", oldin {failures} ta xato" if failures else "")
            if submission.is_late:
                title += "; kechikkan"
            return Cell(
                mark=f"+{failures or ''}",
                tone="pass",
                late=submission.is_late,
                submission_id=submission.pk,
                title=title,
                attempts=failures + 1,
            )
    active = [s for s in counted if s.status in ACTIVE]
    if active:
        return Cell("…", "", False, active[-1].pk, "Tekshirilmoqda", len(counted))
    if counted:
        tries = len(counted)
        title = f"{tries} ta urinish, hali qabul yoʻq"
        return Cell(f"{MINUS}{tries}", "fail", False, counted[-1].pk, title, tries)
    return Cell()


def build_rows(
    students: Iterable[StudentLike],
    assignment_ids: Sequence[int],
    submissions: Iterable[SubmissionLike],
) -> list[Row]:
    """Rows sorted as acmp does: most solved first, then fewest attempts, then by name."""
    by_cell: dict[tuple[int, int], list[SubmissionLike]] = defaultdict(list)
    for submission in sorted(submissions, key=lambda s: (s.created_at, s.pk)):
        by_cell[submission.student_id, submission.assignment_id].append(submission)
    rows = [
        Row(student, [cell_for(by_cell[student.pk, aid]) for aid in assignment_ids])
        for student in students
    ]
    return sorted(rows, key=lambda row: (-row.solved, row.attempts, row.student.display_name))


def _counts(verdict: str) -> bool:
    return bool(verdict) and Verdict(verdict).counts_as_attempt
