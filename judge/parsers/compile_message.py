"""The student's view of a compile error (SPEC §3.8).

The Dart and Flutter compilers print one block per problem: a ``path:line:col: Error:
message`` line, notes, then the offending line of code. A block in the student's own files
is theirs to read in full. A block in a test file says only what the tests expected of
their code: its message, never the path (test/hidden/... names tests) or the line (test
code). Everything else is dropped, so the output is a whitelist, not a filter: what this
module doesn't recognise never reaches the student.
"""

import re
from collections.abc import Sequence

from judge.core.messages import cut

INTERFACE_MISMATCH = "Kodingiz topshiriqdagi interfeysga mos emas: "
UNREADABLE = (
    "Kod kompilyatsiya boʻlmadi. Loyihangizni oʻz kompyuteringizda testlar bilan "
    "ishga tushirib, xatoni koʻring."
)

_HEADER = re.compile(
    r"^(?P<path>\S+?\.dart):\d+:\d+: (?P<kind>Error|Warning|Context|Info): (?P<message>.+)$"
)
_TEST_PATH = re.compile(r"(^|[\s'\"(/])test/")


def student_compile_message(text: str, student_paths: Sequence[str] = ("lib",)) -> str:
    shown: list[str] = []
    for header, path, kind, message, notes in _blocks(text):
        if _is_students(path, student_paths):
            block = "\n".join([header, *(line for line in notes if not _TEST_PATH.search(line))])
        elif kind == "Error":
            block = INTERFACE_MISMATCH + message
        else:
            continue
        if block not in shown:
            shown.append(block)
    if not shown:
        return UNREADABLE
    return cut("\n".join(shown))


def _blocks(text: str) -> list[tuple[str, str, str, str, list[str]]]:
    """(header, path, kind, message, the lines after it) for every compiler block; lines
    before the first block ("Failed to load ...") belong to none and are left out."""
    blocks: list[tuple[str, str, str, str, list[str]]] = []
    for line in text.splitlines():
        match = _HEADER.match(line)
        if match:
            blocks.append((line, match["path"], match["kind"], match["message"], []))
        elif blocks and line.strip():
            blocks[-1][4].append(line.rstrip())
    return blocks


def _is_students(path: str, student_paths: Sequence[str]) -> bool:
    return any(path.startswith(f"{root}/") for root in student_paths)
