"""Checks an untrusted zip before anything is unpacked (SPEC §3.6).

Nothing is written to disk: files are read into memory and later handed to Docker as a
tar archive. Every entry's metadata is checked first; data is decompressed only in
``ValidatedZip.read`` and only within the limits.
"""

import lzma
import os
import re
import stat
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO

_MB = 1024 * 1024
_SUPPORTED_COMPRESSION = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
}
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_FLAG_ENCRYPTED = 0x1
_FLAG_PATCHED_DATA = 0x20
_FLAG_STRONG_ENCRYPTION = 0x40
# What a broken or hostile zip can raise while being parsed or decompressed.
# ValueError: a corrupted header offset makes zipfile seek to a negative position.
# NotImplementedError: a corrupted "version needed to extract" field.
_BROKEN_ZIP_ERRORS = (
    zipfile.BadZipFile,
    EOFError,
    OSError,
    ValueError,
    NotImplementedError,
    zlib.error,
    lzma.LZMAError,
)


class ZipProblem(StrEnum):
    TOO_LARGE = "too_large"
    BROKEN = "broken"
    ENCRYPTED = "encrypted"
    UNSUPPORTED = "unsupported"
    UNSAFE_PATH = "unsafe_path"
    NOT_A_REGULAR_FILE = "not_a_regular_file"
    DUPLICATE = "duplicate"
    PATH_CONFLICT = "path_conflict"
    TOO_MANY_FILES = "too_many_files"
    TOO_LARGE_UNPACKED = "too_large_unpacked"


class ZipRejected(Exception):
    """The zip can't be accepted. ``str(error)`` is the message for the user."""

    def __init__(self, problem: ZipProblem, message: str) -> None:
        super().__init__(message)
        self.problem = problem


@dataclass(frozen=True)
class ZipLimits:
    max_zip_bytes: int
    max_unpacked_bytes: int  # total size of the files read
    max_files: int  # number of files read

    def __post_init__(self) -> None:
        if min(self.max_zip_bytes, self.max_unpacked_bytes, self.max_files) < 1:
            raise ValueError("zip limits must be positive")


@dataclass(frozen=True)
class ArchiveFile:
    path: str  # relative POSIX path, e.g. "lib/main.dart"
    data: bytes


class ValidatedZip:
    """A zip whose every entry passed the metadata checks. Read files with ``read``."""

    def __init__(
        self, archive: zipfile.ZipFile, files: dict[str, zipfile.ZipInfo], limits: ZipLimits
    ) -> None:
        self._archive = archive
        self._files = files
        self._limits = limits

    @property
    def paths(self) -> list[str]:
        """All file paths in zip order, directories left out."""
        return list(self._files)

    def read(self, keep: Callable[[str], bool] | None = None) -> list[ArchiveFile]:
        """Decompress the files ``keep`` selects (all by default) within the limits."""
        chosen = [(path, info) for path, info in self._files.items() if keep is None or keep(path)]
        limits = self._limits
        if len(chosen) > limits.max_files:
            raise ZipRejected(
                ZipProblem.TOO_MANY_FILES,
                f"Zip ichida fayllar juda koʻp: {len(chosen)} ta, ruxsat etilgani "
                f"{limits.max_files} ta. Faqat kerakli fayllarni zip qilib qayta yuklang.",
            )
        if sum(info.file_size for _, info in chosen) > limits.max_unpacked_bytes:
            raise _too_large_unpacked(limits)

        budget = limits.max_unpacked_bytes
        files: list[ArchiveFile] = []
        for path, info in chosen:
            try:
                with self._archive.open(info) as member:
                    # Never trust the declared size: read at most what is left of the budget.
                    data = member.read(budget + 1)
            except _BROKEN_ZIP_ERRORS as error:
                raise _broken() from error
            if len(data) > budget:
                raise _too_large_unpacked(limits)
            budget -= len(data)
            files.append(ArchiveFile(path, data))
        return files


def validate_zip(source: BinaryIO, limits: ZipLimits) -> ValidatedZip:
    """Check the zip's size and every entry's metadata without decompressing anything."""
    size = source.seek(0, os.SEEK_END)
    source.seek(0)
    if size > limits.max_zip_bytes:
        raise ZipRejected(
            ZipProblem.TOO_LARGE,
            f"Zip hajmi juda katta: {size / _MB:.1f} MB, ruxsat etilgani "
            f"{limits.max_zip_bytes / _MB:g} MB. Faqat kerakli fayllarni zip qilib qayta yuklang.",
        )
    try:
        archive = zipfile.ZipFile(source)
        infos = archive.infolist()
    except _BROKEN_ZIP_ERRORS as error:
        raise _broken() from error

    files: dict[str, zipfile.ZipInfo] = {}
    directories: set[str] = set()
    for info in infos:
        path, is_directory = _normalized_path(info.filename)
        _check_entry(info, path)
        if is_directory:
            if path:
                directories.add(path)
            continue
        if path in files:
            raise ZipRejected(
                ZipProblem.DUPLICATE,
                f"Zip ichida bir xil nomli ikkita fayl bor: {_shown(path)}. "
                "Zipni qayta yarating va yuklang.",
            )
        files[path] = info
        parts = path.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))

    for path in files:
        if path in directories:
            raise ZipRejected(
                ZipProblem.PATH_CONFLICT,
                f"Zip ichida {_shown(path)} ham fayl, ham papka sifatida bor. "
                "Zipni qayta yarating va yuklang.",
            )
    return ValidatedZip(archive, files, limits)


def _normalized_path(name: str) -> tuple[str, bool]:
    """Return the safe relative path and whether the entry is a directory.

    Backslashes become slashes (Windows tools write them), "." and empty parts are dropped.
    Absolute paths, drive letters, ".." and control characters are rejected (zip-slip).
    """
    raw = name.replace("\\", "/")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if (
        raw.startswith("/")
        or _DRIVE_LETTER.match(raw)
        or _CONTROL_CHARS.search(raw)
        or ".." in parts
    ):
        raise ZipRejected(
            ZipProblem.UNSAFE_PATH,
            f"Zip ichida xavfli yoʻl bor: {_shown(name)}. "
            "Zipni loyiha papkasining ichidan yarating va qayta yuklang.",
        )
    return "/".join(parts), raw.endswith("/") or not parts


def _check_entry(info: zipfile.ZipInfo, path: str) -> None:
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        kind = "simvolik havola (symlink)" if stat.S_ISLNK(mode) else "oddiy boʻlmagan fayl"
        raise ZipRejected(
            ZipProblem.NOT_A_REGULAR_FILE,
            f"Zip ichida {kind} bor: {_shown(path)}. "
            "Faqat oddiy fayllardan zip yarating va qayta yuklang.",
        )
    if info.flag_bits & (_FLAG_ENCRYPTED | _FLAG_STRONG_ENCRYPTION):
        raise ZipRejected(
            ZipProblem.ENCRYPTED,
            f"Zip ichidagi fayl parol bilan himoyalangan: {_shown(path)}. "
            "Parolsiz zip yarating va qayta yuklang.",
        )
    if info.compress_type not in _SUPPORTED_COMPRESSION or info.flag_bits & _FLAG_PATCHED_DATA:
        raise ZipRejected(
            ZipProblem.UNSUPPORTED,
            f"Zip ichidagi fayl qoʻllab-quvvatlanmaydigan usulda siqilgan: {_shown(path)}. "
            "Oddiy zip (Deflate) yarating va qayta yuklang.",
        )


def _shown(path: str) -> str:
    """A path from the zip, safe to put into a message."""
    cleaned = _CONTROL_CHARS.sub("?", path)
    return cleaned if len(cleaned) <= 120 else cleaned[:117] + "..."


def _broken() -> ZipRejected:
    return ZipRejected(
        ZipProblem.BROKEN, "Fayl zip emas yoki buzilgan. Zipni qayta yarating va yuklang."
    )


def _too_large_unpacked(limits: ZipLimits) -> ZipRejected:
    return ZipRejected(
        ZipProblem.TOO_LARGE_UNPACKED,
        f"Zip ochilganda {limits.max_unpacked_bytes / _MB:g} MB dan oshadi. "
        "Faqat kerakli fayllarni zip qilib qayta yuklang.",
    )
