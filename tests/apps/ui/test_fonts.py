"""Fonts: every @font-face file exists, never claims a letter it can't draw, and each font
stack draws Uzbek Latin (oʻ, gʻ, tutuq belgisi) and Russian with its own fonts."""

import re
from functools import cache
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from apps.ui.tokens import SOURCE_CSS
from judge.env import REPO_ROOT

FONTS_DIR = REPO_ROOT / "static" / "fonts"
FACE = re.compile(r"@font-face\s*\{(?P<body>[^}]*)\}")
FAMILY = re.compile(r'font-family:\s*"(?P<name>[^"]+)"')
SRC = re.compile(r'url\("\.\./fonts/(?P<file>[^"]+)"\)')
RANGE = re.compile(r"unicode-range:\s*(?P<ranges>[^;]+);")
STACK = re.compile(r"--font-(?P<kind>sans|serif|mono):\s*(?P<families>[^;]+);")
# The letters UI text depends on: ʻ ʼ, Latin, Russian.
NEEDED = {
    "ʻ": 0x02BB,
    "ʼ": 0x02BC,
    "o": ord("o"),
    "Ж": ord("Ж"),
    "я": ord("я"),
}


def parse_ranges(text: str) -> list[range]:
    ranges = []
    for part in text.replace("\n", " ").split(","):
        start, _, end = part.strip().removeprefix("U+").partition("-")
        ranges.append(range(int(start, 16), int(end or start, 16) + 1))
    return ranges


def faces() -> list[tuple[str, Path, list[range]]]:
    found = []
    for match in FACE.finditer(SOURCE_CSS.read_text()):
        body = match["body"]
        family, src, ranges = FAMILY.search(body), SRC.search(body), RANGE.search(body)
        assert family and src and ranges, f"incomplete @font-face: {body}"
        found.append((family["name"], FONTS_DIR / src["file"], parse_ranges(ranges["ranges"])))
    return found


@cache
def cmap(path: Path) -> frozenset[int]:
    return frozenset(TTFont(path).getBestCmap())


def test_every_font_file_exists() -> None:
    missing = [path.name for _, path, _ in faces() if not path.is_file()]

    assert faces()
    assert not missing


@pytest.mark.parametrize("letter", NEEDED)
def test_no_face_claims_a_letter_it_cannot_draw(letter: str) -> None:
    code = NEEDED[letter]
    liars = [
        path.name
        for _, path, ranges in faces()
        if any(code in r for r in ranges) and code not in cmap(path)
    ]

    assert not liars, f"{letter} is in their unicode-range but not in the font: {liars}"


@pytest.mark.parametrize("kind", ["sans", "serif", "mono"])
def test_each_font_stack_draws_every_needed_letter(kind: str) -> None:
    stack = {m["kind"]: m["families"] for m in STACK.finditer(SOURCE_CSS.read_text())}[kind]
    own = {name.strip().strip('"') for name in stack.split(",")}
    drawn = {
        code
        for family, path, ranges in faces()
        if family in own
        for code in NEEDED.values()
        if any(code in r for r in ranges) and code in cmap(path)
    }

    assert drawn == set(NEEDED.values())


def test_every_bundled_font_has_its_licence() -> None:
    licences = {p.name for p in (FONTS_DIR / "licenses").iterdir()}
    families = {path.name.split("-")[0] for _, path, _ in faces()} - {"ohw"}

    assert {f"{family}" for family in families} <= {name.split("-")[0] for name in licences}
    assert "inter-OFL.txt" in licences  # ohw-marks is a subset of Inter
