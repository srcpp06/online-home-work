"""What a student downloads before solving (SPEC §3.3, step 6), and the package checklist
a teacher sees after uploading (docs/UI.md §5).

The starter is the package without the solution, the hidden tests and ohw.yaml, with the
starter/ folder laid over it: starter/lib/main.dart becomes lib/main.dart.
"""

import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass

from judge.packaging.task_package import is_junk, strip_common_root
from judge.packaging.zip_validator import ArchiveFile

# Fixed timestamps: the same package always gives the same starter bytes.
_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
_NOT_FOR_STUDENTS = ("solution/", "test/hidden/", "starter/")


def starter_files(files: Sequence[ArchiveFile]) -> list[ArchiveFile]:
    files = strip_common_root([f for f in files if not is_junk(f.path)])
    chosen = {
        file.path: file.data
        for file in files
        if file.path != "ohw.yaml" and not file.path.startswith(_NOT_FOR_STUDENTS)
    }
    for file in files:
        if file.path.startswith("starter/"):
            chosen[file.path.removeprefix("starter/")] = file.data  # starter/ wins
    return [ArchiveFile(path, data) for path, data in sorted(chosen.items())]


def starter_zip(files: Sequence[ArchiveFile], folder: str) -> bytes:
    """A zip with everything inside ``folder``/, so unzipping gives one project folder."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in starter_files(files):
            info = zipfile.ZipInfo(f"{folder}/{file.path}", date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, file.data)
    return buffer.getvalue()


@dataclass(frozen=True)
class CheckItem:
    label: str  # e.g. "test/hidden"
    found: bool
    detail: str  # e.g. "5 ta fayl"


def package_checklist(files: Sequence[ArchiveFile]) -> list[CheckItem]:
    """What a package has and lacks, in the order a teacher reads it."""
    files = strip_common_root([f for f in files if not is_junk(f.path)])
    paths = [file.path for file in files]

    def count(prefix: str, suffix: str = "") -> int:
        return sum(1 for path in paths if path.startswith(prefix) and path.endswith(suffix))

    def item(label: str, n: int, unit: str = "ta fayl") -> CheckItem:
        return CheckItem(label, n > 0, f"{n} {unit}" if n else "topilmadi")

    starter = count("starter/")
    return [
        CheckItem(
            "pubspec.yaml",
            "pubspec.yaml" in paths,
            "bor" if "pubspec.yaml" in paths else "topilmadi",
        ),
        item("solution/lib", count("solution/lib/", ".dart"), "ta .dart fayl"),
        item("test/public", count("test/public/", "_test.dart"), "ta test fayli"),
        item("test/hidden", count("test/hidden/", "_test.dart"), "ta test fayli"),
        CheckItem("starter/ (ixtiyoriy)", True, f"{starter} ta fayl" if starter else "yoʻq"),
    ]
