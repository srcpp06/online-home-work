"""Structure of a teacher's dart/flutter task package (SPEC §3.2).

pubspec.yaml        libraries; only the teacher chooses them
solution/lib/       the teacher's solution: warms up the image, then is removed
test/public/        open tests, given to students with the starter
test/hidden/        hidden tests, only inside the image
ohw.yaml, starter/  settings and starter code, not part of the image
"""

from collections.abc import Sequence
from dataclasses import dataclass

from judge.core.manifest import Visibility
from judge.packaging.combined_tests import COMBINED_TEST_PATH, is_safe_test_path
from judge.packaging.zip_validator import ArchiveFile

# Left out of every package: tool caches and OS leftovers (SPEC §3.4, step 1).
JUNK_DIRS = frozenset(
    {"__MACOSX", ".git", "build", ".dart_tool", "node_modules", "venv", "__pycache__"}
)
JUNK_FILES = frozenset({".DS_Store", "Thumbs.db"})


class PackageInvalid(Exception):
    """The package can't be built. ``errors`` are messages for the teacher."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class TaskPackage:
    project_files: tuple[ArchiveFile, ...]  # go into the image: pubspec, tests, assets ...
    solution_files: tuple[ArchiveFile, ...]  # paths under lib/, used only to warm up
    test_files: tuple[str, ...]  # relative to test/, run order: public, then hidden


def visibility_of(test_file: str) -> Visibility:
    """Visibility of a test file given relative to test/. Anything not public is hidden."""
    return Visibility.PUBLIC if test_file.startswith("public/") else Visibility.HIDDEN


def is_junk(path: str) -> bool:
    parts = path.split("/")
    return parts[-1] in JUNK_FILES or any(part in JUNK_DIRS for part in parts[:-1])


def read_task_package(files: Sequence[ArchiveFile]) -> TaskPackage:
    files = _strip_common_root([f for f in files if not is_junk(f.path)])
    errors: list[str] = []
    project: list[ArchiveFile] = []
    solution: list[ArchiveFile] = []
    tests: dict[str, list[str]] = {"public": [], "hidden": []}
    combined_name = COMBINED_TEST_PATH.removeprefix("test/")
    lib_at_root = False

    for file in files:
        path = file.path
        if path == "ohw.yaml" or path.startswith("starter/"):
            continue
        if path.startswith("solution/"):
            if path.startswith("solution/lib/"):
                solution.append(ArchiveFile(path.removeprefix("solution/"), file.data))
            continue
        if path.startswith("lib/"):
            lib_at_root = True
            continue
        if path.startswith("test/"):
            test_file = path.removeprefix("test/")
            folder = test_file.split("/", 1)[0]
            if test_file == combined_name:
                errors.append(f"{path} nomi platforma uchun band. Faylni boshqa nom bilan saqlang.")
                continue
            if test_file.endswith("_test.dart"):
                if folder not in tests or "/" not in test_file:
                    errors.append(
                        f"{path}: test fayli test/public yoki test/hidden papkasida boʻlishi kerak."
                    )
                    continue
                if not is_safe_test_path(test_file):
                    errors.append(
                        f"{path}: fayl nomida ruxsat etilmagan belgi bor. "
                        "Faqat lotin harflari, raqamlar va _ - . belgilarini ishlating."
                    )
                    continue
                tests[folder].append(test_file)
        project.append(file)

    paths = {file.path for file in project}
    if "pubspec.yaml" not in paths:
        errors.append("pubspec.yaml topilmadi. Uni paketning ildiziga qoʻying.")
    if lib_at_root:
        errors.append("Ildizdagi lib/ papkasi ishlatilmaydi. Yechimni solution/lib ga koʻchiring.")
    if not any(file.path.endswith(".dart") for file in solution):
        errors.append(
            "solution/lib papkasida .dart fayl yoʻq. Oʻqituvchi yechimini solution/lib ga qoʻying."
        )
    for folder, kind in (("public", "Ochiq"), ("hidden", "Yashirin")):
        if not tests[folder]:
            errors.append(
                f"test/{folder} papkasida test fayli (*_test.dart) yoʻq. "
                f"{kind} testlarni shu papkaga qoʻying."
            )
    if errors:
        raise PackageInvalid(errors)
    return TaskPackage(
        project_files=tuple(project),
        solution_files=tuple(solution),
        test_files=(*sorted(tests["public"]), *sorted(tests["hidden"])),
    )


def _strip_common_root(files: list[ArchiveFile]) -> list[ArchiveFile]:
    """A zipped folder (cart_task/pubspec.yaml ...) is read as if zipped from inside."""
    if not files or any(file.path == "pubspec.yaml" for file in files):
        return files
    roots = {file.path.split("/", 1)[0] for file in files}
    if len(roots) != 1 or any("/" not in file.path for file in files):
        return files
    prefix = f"{roots.pop()}/"
    return [ArchiveFile(file.path.removeprefix(prefix), file.data) for file in files]
