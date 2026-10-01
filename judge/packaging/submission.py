"""Which files of a student's zip are judged (SPEC §3.4, step 1).

Students zip all sorts of things: just lib/, the whole project, the project folder itself.
The root is wherever the folder of the first student path (lib/ for dart and flutter) is
found, at most three folders deep. Only the profile's student paths are taken; the
student's pubspec, tests and everything else are ignored, because only the teacher
chooses libraries and tests.
"""

from collections.abc import Sequence

from judge.packaging.task_package import is_junk
from judge.packaging.zip_validator import ArchiveFile, ValidatedZip

MAX_ROOT_DEPTH = 3


class SubmissionInvalid(Exception):
    """The zip has nothing to judge. ``str(error)`` is the message for the student."""


def select_student_files(paths: Sequence[str], student_paths: Sequence[str]) -> dict[str, str]:
    """Map zip paths of the files to judge to their paths in the project."""
    marker = student_paths[0]
    paths = [path for path in paths if not is_junk(path)]
    roots = {
        "/".join(parts[:depth])
        for parts in (path.split("/") for path in paths)
        for depth in range(min(len(parts) - 1, MAX_ROOT_DEPTH + 1))
        if parts[depth] == marker
    }
    if not roots:
        raise SubmissionInvalid(
            f"Zip ichida {marker}/ papkasi topilmadi. "
            f"Loyihangizning {marker}/ papkasini zip qilib qayta yuklang."
        )
    shallowest = min(root.count("/") + bool(root) for root in roots)
    candidates = sorted(root for root in roots if root.count("/") + bool(root) == shallowest)
    if len(candidates) > 1:
        shown = ", ".join(f"{root}/{marker}/" for root in candidates)
        raise SubmissionInvalid(
            f"Zip ichida bir nechta {marker}/ papkasi bor: {shown}. "
            "Faqat bitta loyihani zip qilib qayta yuklang."
        )

    prefix = f"{candidates[0]}/" if candidates[0] else ""
    selected = {}
    for path in paths:
        relative = path.removeprefix(prefix)
        if path.startswith(prefix) and relative.split("/", 1)[0] in student_paths:
            selected[path] = relative
    return selected


def read_submission(archive: ValidatedZip, student_paths: Sequence[str]) -> list[ArchiveFile]:
    """The student's files, renamed to project paths; only these are decompressed."""
    selected = select_student_files(archive.paths, student_paths)
    files = archive.read(keep=lambda path: path in selected)
    return [ArchiveFile(selected[file.path], file.data) for file in files]
