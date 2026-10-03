"""Sending a solution (SPEC §3.4, §3.9): when a student may, and what becomes of the zip.

The zip is checked here, on upload, with the worker's own function: one that fails gets
"Rad etildi" at once and never waits in the queue. One that passes waits for a worker.
"""

import hashlib
import io
import math
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.submissions.models import Submission, SubmissionQuerySet
from apps.system.queue import enqueue_judge
from apps.tasks.models import Assignment, Task, TaskVersion
from judge.core.verdict import Verdict
from judge.packaging.dart_imports import ImportRules
from judge.packaging.submission import SubmissionRejected, check_submission

ACTIVE = (Submission.Status.QUEUED, Submission.Status.RUNNING)


class SubmitRefused(Exception):
    """Not now: the deadline passed, no attempts are left or it's too soon.
    ``str(error)`` is the message for the student."""


@dataclass(frozen=True)
class SubmitState:
    """What the assignment page says before the student uploads anything."""

    attempts_used: int
    max_attempts: int | None
    wait_s: int  # until the cooldown ends; 0 when it has
    late: bool  # a solution sent now is marked late
    blocked_by: str  # deadline, attempts, active or cooldown; "" when the student can send
    refusal: str  # the reason in words

    @property
    def can_submit(self) -> bool:
        return not self.refusal

    @property
    def attempts_left(self) -> int | None:
        if self.max_attempts is None:
            return None
        return max(self.max_attempts - self.attempts_used, 0)


def submit_state(assignment: Assignment, student: User, now: datetime | None = None) -> SubmitState:
    now = now or timezone.now()
    mine = Submission.objects.filter(assignment=assignment, student=student)
    used = mine.counting().count()
    late = assignment.is_past_deadline(now)
    wait_s = _cooldown_left_s(mine, now)
    active = Submission.objects.filter(student=student, status__in=ACTIVE).count()
    blocked_by, refusal = "", ""
    if late and not assignment.allow_late:
        blocked_by = "deadline"
        refusal = "Muddat tugagan: bu topshiriqqa yechim endi qabul qilinmaydi."
    elif assignment.max_attempts is not None and used >= assignment.max_attempts:
        blocked_by = "attempts"
        refusal = f"Urinishlar tugadi: {assignment.max_attempts} ta urinishning hammasi ishlatildi."
    elif active >= settings.SUBMISSION_MAX_ACTIVE_PER_STUDENT:
        blocked_by = "active"
        refusal = "Oldingi yechimingiz hali tekshirilmoqda. Natijasi chiqqach, yangisini yuboring."
    elif wait_s:
        blocked_by = "cooldown"
        refusal = f"Keyingi yechimni {wait_s} soniyadan keyin yuborish mumkin."
    return SubmitState(used, assignment.max_attempts, wait_s, late, blocked_by, refusal)


def _cooldown_left_s(mine: SubmissionQuerySet, now: datetime) -> int:
    """One solution per assignment every SUBMISSION_COOLDOWN_S. A rejected zip never reached
    the queue, so it doesn't count: the student fixes it and sends again at once."""
    last = (
        mine.exclude(verdict=Verdict.REJECTED)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if last is None:
        return 0
    left = settings.SUBMISSION_COOLDOWN_S - (now - last).total_seconds()
    return max(math.ceil(left), 0)


def submit(assignment: Assignment, student: User, upload: UploadedFile) -> Submission:
    """Store the solution and queue it, or reject it on the spot; SubmitRefused if the
    student may not send one now."""
    version = _published_version(assignment)
    upload.seek(0)
    data = upload.read()
    rules = ImportRules.from_json_data(version.import_rules) if version.import_rules else None
    try:
        check_submission(
            io.BytesIO(data),
            settings.SUBMISSION_ZIP_LIMITS,
            assignment.task.profile.judge_profile(),
            rules,
        )
        rejection = ""
    except SubmissionRejected as error:
        rejection = str(error)

    with transaction.atomic():
        # One submit at a time per student: two quick clicks can't both pass the checks.
        User.objects.select_for_update().filter(pk=student.pk).first()
        now = timezone.now()
        state = submit_state(assignment, student, now)
        if not state.can_submit:
            raise SubmitRefused(state.refusal)
        submission = Submission(
            assignment=assignment,
            student=student,
            task_version=version,
            sha256=hashlib.sha256(data).hexdigest(),
            is_late=state.late,
            tests_total=version.test_count,
        )
        if rejection:
            submission.status = Submission.Status.FINISHED
            submission.verdict = Verdict.REJECTED
            submission.public_message = rejection
            submission.internal_log = f"rejected on upload:\n{rejection}\n"
            submission.finished_at = now
        submission.archive.save("solution.zip", ContentFile(data), save=False)
        submission.save()
        if not rejection:
            enqueue_judge(submission)
    return submission


def _published_version(assignment: Assignment) -> TaskVersion:
    """Read again, not from the page: the teacher may have published a newer version."""
    task = Task.objects.select_related("published_version").get(pk=assignment.task_id)
    version = task.published_version
    if version is None or version.status != TaskVersion.Status.READY:
        raise SubmitRefused("Topshiriq hozircha yopiq. Keyinroq urinib koʻring.")
    return version


def rejudge(submission: Submission) -> None:
    """Judge again with the same task version (the teacher's "Qayta tekshirish"). The old
    result is cleared, so the page follows the new run from the start."""
    with transaction.atomic():
        locked = Submission.objects.select_for_update().get(pk=submission.pk)
        if locked.status != Submission.Status.FINISHED:
            raise SubmitRefused("Yechim hali tekshirilmoqda.")
        if locked.verdict == Verdict.REJECTED:
            raise SubmitRefused(
                "Rad etilgan yechim qayta tekshirilmaydi: u testlargacha yetib bormagan."
            )
        locked.results.all().delete()
        Submission.objects.filter(pk=locked.pk).update(
            status=Submission.Status.QUEUED,
            verdict="",
            tests_passed=0,
            failed_test_index=None,
            failed_test_name="",
            public_message="",
            internal_log="",
            wall_ms=None,
            started_at=None,
            finished_at=None,
        )
        enqueue_judge(locked, rejudge=True)
