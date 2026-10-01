"""Static import check for students' Dart code (SPEC §3.4 step 2, §3.7).

dart:io and friends would let student code write fake test results straight to stdout,
read files or exit the process, so they are rejected before anything runs. Students may
import only the dart: libraries the profile allows, their own package, the packages in the
task's pubspec dependencies, and files inside lib/.

The check must read the source exactly like the Dart compiler does, or a creative student
could hide an import from it. So it tokenizes: nested block comments, raw and triple-quoted
strings, escapes, ${...} interpolation and adjacent string literals ('dart:' 'io') are all
handled. A file that can't be tokenized is rejected rather than guessed at.
"""

import posixpath
import re
import urllib.parse
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from judge.core.profile import RunnerProfile
from judge.packaging.task_package import TaskPackage
from judge.packaging.zip_validator import ArchiveFile

_DIRECTIVES = frozenset({"import", "export", "part"})
_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")
_DART_LIBRARY = re.compile(r"[a-z_][a-z0-9_]*")
_IDENTIFIER_START = re.compile(r"[A-Za-z_$]")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_$]*")
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "f": "\f", "b": "\b", "t": "\t", "v": "\v"}


@dataclass(frozen=True)
class ImportRules:
    package_name: str
    allowed_packages: frozenset[str]
    forbidden_dart: frozenset[str]  # library names: "io", "ffi" ...

    @classmethod
    def for_task(cls, package: TaskPackage, profile: RunnerProfile) -> Self:
        forbidden = {uri.removeprefix("dart:") for uri in profile.forbidden_imports}
        if package.settings.allow_dart_io:
            forbidden.discard("io")
        return cls(
            package_name=package.package_name,
            allowed_packages=package.dependencies | {package.package_name},
            forbidden_dart=frozenset(forbidden),
        )


def find_forbidden_imports(files: Sequence[ArchiveFile], rules: ImportRules) -> list[str]:
    """Messages for the student, one per forbidden import; empty when the code is fine."""
    problems: list[str] = []
    for file in files:
        if not file.path.endswith(".dart"):
            continue
        try:
            source = file.data.decode("utf-8")
            directives = _directives(_Lexer(source).tokens())
        except UnicodeDecodeError:
            problems.append(
                f"{file.path}: fayl UTF-8 kodlashida emas. Faylni UTF-8 da saqlab qayta yuklang."
            )
            continue
        except _LexError:
            problems.append(
                f"{file.path}: faylni tekshirib boʻlmadi (yopilmagan string yoki izoh bor). "
                "Kodni tuzatib qayta yuklang."
            )
            continue
        for line, uri, interpolated in directives:
            reason = "importda $ ishlatib boʻlmaydi" if interpolated else None
            reason = reason or _reason(uri, file.path, rules)
            if reason:
                location = f"{file.path}:{line}"
                problems.append(f"Taqiqlangan import: {_shown(uri)} — {reason} ({location})")
    return problems


def _reason(uri: str, path: str, rules: ImportRules) -> str | None:
    """Why the URI is forbidden, or None.

    Normalized the way Dart's Uri reads it (percent-escapes, scheme case). Anything odd is
    rejected: Dart loads an imported file as Dart whatever its name, so only .dart files
    may be imported, and ?query or #fragment could hide the real file name.
    """
    target = urllib.parse.unquote(uri.strip())
    if any(char in target for char in "\\?#"):
        return "importda \\, ? yoki # ishlatib boʻlmaydi"
    if re.search(r"[\x00-\x20\x7f]", target):
        return "importda boʻsh joy yoki boshqaruv belgisi boʻlishi mumkin emas"
    scheme = _SCHEME.match(target)
    if scheme:
        name, rest = scheme.group(1).lower(), target[scheme.end() :]
        if name == "dart":
            library = rest.lower()
            if library in rules.forbidden_dart or not _DART_LIBRARY.fullmatch(library):
                return "bu topshiriqda ruxsat etilmagan"
            return None
        if name == "package":
            package, _, file = rest.partition("/")
            if package not in rules.allowed_packages:
                return "bu paket topshiriq kutubxonalari roʻyxatida yoʻq"
            if {"", ".", ".."} & set(file.split("/")):
                return "bu topshiriqda ruxsat etilmagan"
            if package == rules.package_name and not file.endswith(".dart"):
                return "faqat .dart fayllarni import qilish mumkin"
            return None
        return "faqat dart: va package: importlari ishlatiladi"
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    if target.startswith("/") or not resolved.startswith("lib/"):
        return "lib/ papkasidan tashqaridagi faylni ishlatib boʻlmaydi"
    if not resolved.endswith(".dart"):
        return "faqat .dart fayllarni import qilish mumkin"
    return None


def _shown(uri: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "?", uri)
    return cleaned if len(cleaned) <= 120 else cleaned[:117] + "..."


@dataclass(frozen=True)
class _Token:
    kind: str  # "identifier", "string" or "punctuation"
    text: str  # the name, the string's value, or the character
    line: int
    interpolated: bool = False


def _directives(tokens: list[_Token]) -> list[tuple[int, str, bool]]:
    """(line, uri, interpolated) of every import, export and part URI.

    A directive is the keyword, maybe a few words (`part of`, `import augment`), then a
    string; `var import = ...` is just a variable. Every string up to the `;` counts,
    conditional import URIs included. Adjacent strings are one literal, as in Dart.
    """
    found: list[tuple[int, str, bool]] = []
    for index, token in enumerate(tokens):
        if token.kind != "identifier" or token.text not in _DIRECTIVES:
            continue
        start = index + 1
        while _is(tokens, start, "identifier"):
            start += 1
        if not _is(tokens, start, "string"):
            continue
        literal: list[_Token] = []
        for current in tokens[start:]:
            if current.kind == "string":
                literal.append(current)
                continue
            if literal:
                found.append(_joined(literal))
                literal = []
            if current.kind == "punctuation" and current.text == ";":
                break
        if literal:
            found.append(_joined(literal))
    return found


def _is(tokens: list[_Token], index: int, kind: str) -> bool:
    return index < len(tokens) and tokens[index].kind == kind


def _joined(literal: list[_Token]) -> tuple[int, str, bool]:
    text = "".join(token.text for token in literal)
    return literal[0].line, text, any(token.interpolated for token in literal)


class _LexError(Exception):
    pass


class _Lexer:
    """Just enough of Dart's lexer to know what is code, comment and string."""

    def __init__(self, source: str) -> None:
        self.source = source.removeprefix("﻿")
        self.position = 0
        self.line = 1
        if self.source.startswith("#!"):  # script tag
            self._skip_line()

    def tokens(self) -> list[_Token]:
        tokens: list[_Token] = []
        self._scan(tokens, inside_interpolation=False)
        return tokens

    def _scan(self, tokens: list[_Token], inside_interpolation: bool) -> None:
        source = self.source
        depth = 0
        while self.position < len(source):
            char = source[self.position]
            if char == "\n":
                self.line += 1
                self.position += 1
            elif char.isspace():
                self.position += 1
            elif source.startswith("//", self.position):
                self._skip_line()
            elif source.startswith("/*", self.position):
                self._skip_block_comment()
            elif self._at_string():
                tokens.append(self._string())
            elif _IDENTIFIER_START.match(char):
                end = _IDENTIFIER.match(source, self.position + 1).end()  # type: ignore[union-attr]
                tokens.append(_Token("identifier", source[self.position : end], self.line))
                self.position = end
            elif char == "}" and inside_interpolation and depth == 0:
                self.position += 1
                return
            else:
                depth += {"{": 1, "}": -1}.get(char, 0)
                tokens.append(_Token("punctuation", char, self.line))
                self.position += 1
        if inside_interpolation:
            raise _LexError("unterminated interpolation")

    def _at_string(self) -> bool:
        """A quote, or r directly followed by a quote (a raw string)."""
        ahead = self.source[self.position : self.position + 2]
        return ahead[:1] in ("'", '"') or ahead in ("r'", 'r"')

    def _skip_line(self) -> None:
        end = self.source.find("\n", self.position)
        self.position = len(self.source) if end == -1 else end

    def _skip_block_comment(self) -> None:
        """Dart block comments nest: /* a /* b */ c */ is one comment."""
        source, depth = self.source, 0
        while self.position < len(source):
            if source.startswith("/*", self.position):
                depth += 1
                self.position += 2
            elif source.startswith("*/", self.position):
                depth -= 1
                self.position += 2
                if depth == 0:
                    return
            else:
                self.line += source[self.position] == "\n"
                self.position += 1
        raise _LexError("unterminated comment")

    def _string(self) -> _Token:
        source, line = self.source, self.line
        raw = source[self.position] == "r"
        self.position += raw
        quote = source[self.position]
        delimiter = quote * 3 if source.startswith(quote * 3, self.position) else quote
        self.position += len(delimiter)
        if len(delimiter) == 3:
            self._skip_blank_first_line(raw)
        value: list[str] = []
        interpolated = False
        while not source.startswith(delimiter, self.position):
            if self.position >= len(source):
                raise _LexError("unterminated string")
            char = source[self.position]
            if char == "\n":
                if len(delimiter) == 1:
                    raise _LexError("newline in a single-line string")
                self.line += 1
            if char == "\\" and not raw:
                value.append(self._escape())
            elif char == "$" and not raw:
                interpolated = True
                self._skip_interpolation()
            else:
                value.append(char)
                self.position += 1
        self.position += len(delimiter)
        return _Token("string", "".join(value), line, interpolated)

    def _skip_blank_first_line(self, raw: bool) -> None:
        """A multi-line string drops its first line if that line is only whitespace."""
        source, index = self.source, self.position
        while index < len(source):
            if source[index] in " \t":
                index += 1
            elif not raw and source[index] == "\\" and source[index + 1 : index + 2] in (" ", "\t"):
                index += 2
            else:
                break
        if not raw and source.startswith("\\", index):
            index += 1
        for newline in ("\r\n", "\n", "\r"):
            if source.startswith(newline, index):
                self.position = index + len(newline)
                self.line += 1
                return

    def _escape(self) -> str:
        source = self.source
        self.position += 1  # the backslash
        char = source[self.position : self.position + 1]
        if not char:
            raise _LexError("escape at the end of the file")
        if char in _SIMPLE_ESCAPES:
            self.position += 1
            return _SIMPLE_ESCAPES[char]
        if char == "x":
            return self._code_point(source[self.position + 1 : self.position + 3], 3)
        if char == "u" and source.startswith("{", self.position + 1):
            end = source.find("}", self.position)
            if end == -1:
                raise _LexError("unterminated \\u{")
            digits = source[self.position + 2 : end]
            return self._code_point(digits, end + 1 - self.position, max_digits=6)
        if char == "u":
            return self._code_point(source[self.position + 1 : self.position + 5], 5)
        self.line += char == "\n"
        self.position += 1
        return char  # \\ \' \" \$ and any other character stand for themselves

    def _code_point(self, digits: str, length: int, max_digits: int | None = None) -> str:
        expected = max_digits or length - 1
        if not digits or len(digits) > expected or not re.fullmatch(r"[0-9A-Fa-f]+", digits):
            raise _LexError("bad escape")
        if max_digits is None and len(digits) != expected:
            raise _LexError("bad escape")
        self.position += length
        try:
            return chr(int(digits, 16))
        except (ValueError, OverflowError) as error:
            raise _LexError("bad code point") from error

    def _skip_interpolation(self) -> None:
        source = self.source
        self.position += 1  # the $
        if source.startswith("{", self.position):
            self.position += 1
            self._scan([], inside_interpolation=True)
        elif self.position < len(source) and _IDENTIFIER_START.match(source[self.position]):
            self.position = _IDENTIFIER.match(source, self.position + 1).end()  # type: ignore[union-attr]
        else:
            raise _LexError("a lone $ in a string")
