"""Students' submissions and their test results (SPEC §2, §3.4, §3.8)."""

from typing import TYPE_CHECKING, Self
from uuid import uuid4

from django.db import models

from apps.accounts.models import Role, User, active_viewer
from apps.tasks.models import Assignment, TaskVersion
from judge.core.verdict import Verdict

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser


def _archive_path(submission: "Submission", filename: str) -> str:
    """The student's file name never reaches the disk path."""
    assignment = submission.assignment
    return (
        f"submissions/{assignment.group.center_id}/{assignment.pk}/"
        f"{submission.student_id}/{uuid4().hex}.zip"
    )


class SubmissionQuerySet(models.QuerySet["Submission"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        match viewer.role:
            case Role.SUPERADMIN:
                return self.all()
            case Role.CENTER_ADMIN | Role.CENTER_MANAGER:
                return self.filter(assignment__group__center_id=viewer.center_id)
            case Role.TEACHER:
                return self.filter(assignment__group__teacher=viewer)
            case Role.STUDENT:
                return self.filter(student=viewer)
        return self.none()

    def counting(self) -> Self:
        """Submissions that use up an attempt: all but rejected and system errors."""
        return self.exclude(verdict__in=[v for v in Verdict if not v.counts_as_attempt])


class Submission(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Navbatda"
        RUNNING = "running", "Tekshirilmoqda"
        FINISHED = "finished", "Tekshirildi"

    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="submissions")
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name="submissions")
    task_version = models.ForeignKey(
        TaskVersion, on_delete=models.PROTECT, related_name="submissions"
    )
    archive = models.FileField(upload_to=_archive_path, max_length=300)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    verdict = models.CharField(max_length=20, choices=[(v, v) for v in Verdict], blank=True)
    tests_total = models.PositiveIntegerField(default=0)
    tests_passed = models.PositiveIntegerField(default=0)
    failed_test_index = models.PositiveIntegerField(null=True, blank=True)
    failed_test_name = models.CharField(max_length=500, blank=True)
    public_message = models.TextField(blank=True)  # why a zip was rejected; for the student
    internal_log = models.TextField(blank=True)  # the judge's log; never for the student
    wall_ms = models.PositiveIntegerField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    objects = SubmissionQuerySet.as_manager()

    class Meta:
        verbose_name = "yechim"
        verbose_name_plural = "yechimlar"
        ordering = ("-created_at",)
        indexes = (models.Index(fields=("assignment", "student", "-created_at")),)

    def __str__(self) -> str:
        return f"{self.student} — {self.assignment} #{self.pk}"

    @property
    def is_finished(self) -> bool:
        return self.status == self.Status.FINISHED


class SubmissionTestResultQuerySet(models.QuerySet["SubmissionTestResult"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        return self.filter(submission__in=Submission.objects.for_user(user))


class SubmissionTestResult(models.Model):
    """One finished test, saved as soon as its event arrives (the live page reads these)."""

    class Status(models.TextChoices):
        PASS = "pass", "Oʻtdi"
        FAIL = "fail", "Xato"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    index = models.PositiveIntegerField()  # 1-based, as in "3-testda xato"
    name = models.CharField(max_length=500)
    stage = models.PositiveSmallIntegerField(default=1)
    visibility = models.CharField(max_length=10)  # judge.core.manifest.Visibility
    status = models.CharField(max_length=10, choices=Status.choices)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)  # hidden tests' messages never reach students

    objects = SubmissionTestResultQuerySet.as_manager()

    class Meta:
        ordering = ("submission", "index")
        constraints = (
            models.UniqueConstraint(
                fields=("submission", "index"), name="submissions_result_index_unique"
            ),
        )
