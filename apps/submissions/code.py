"""A submission's code for the staff's eyes (docs/UI.md §6), highlighted on the server.

Only the files that were judged are shown (the profile's student paths), read through the
same zip checks as judging, so a hostile zip is never unpacked.
"""

import io
from dataclasses import dataclass

from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from apps.submissions.models import Submission
from judge.packaging.submission import SubmissionInvalid, read_submission
from judge.packaging.zip_validator import ZipRejected, validate_zip

MAX_SHOWN_BYTES = 256 * 1024  # a longer file is cut: it is for reading, not downloading
_FORMATTER = HtmlFormatter(linenos="inline", wrapcode=True, cssclass="code")


@dataclass(frozen=True)
class CodeFile:
    path: str
    html: SafeString


def student_code(submission: Submission) -> tuple[list[CodeFile], str]:
    """(files, problem): the judged files, or why none can be shown."""
    profile = submission.task_version.task.profile.judge_profile()
    with submission.archive.open("rb") as archive:
        data = archive.read()
    try:
        checked = validate_zip(io.BytesIO(data), settings.SUBMISSION_ZIP_LIMITS)
        files = read_submission(checked, profile.student_paths)
    except (ZipRejected, SubmissionInvalid) as error:
        return [], str(error)
    return [CodeFile(file.path, _highlighted(file.path, file.data)) for file in files], ""


def _highlighted(path: str, data: bytes) -> SafeString:
    try:
        text = data[:MAX_SHOWN_BYTES].decode("utf-8")
    except UnicodeDecodeError:
        return mark_safe(f'<p class="text-text-2">{escape("Matnli fayl emas.")}</p>')  # noqa: S308
    try:
        lexer = get_lexer_for_filename(path)
    except ClassNotFound:
        lexer = TextLexer()
    if len(data) > MAX_SHOWN_BYTES:
        text += "\n…"
    return mark_safe(highlight(text, lexer, _FORMATTER))  # noqa: S308 -- Pygments escapes
