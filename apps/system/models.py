"""The job queue and the worker nodes (SPEC §3.9).

The queue is this table: workers take jobs with SELECT ... FOR UPDATE SKIP LOCKED, so two
workers never take the same job, and nobody waits for a locked row (apps.system.queue).
"""

from typing import TYPE_CHECKING, Self

from django.db import models
from django.db.models import Q

from apps.accounts.models import Role, User, active_viewer
from judge.core.profile import Lane

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser


def _superadmin_only(queryset: models.QuerySet, user: "User | AnonymousUser") -> models.QuerySet:
    viewer = active_viewer(user)
    return (
        queryset.all() if viewer is not None and viewer.role == Role.SUPERADMIN else queryset.none()
    )


class JobQuerySet(models.QuerySet["Job"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        return _superadmin_only(self, user)


class Job(models.Model):
    class Kind(models.TextChoices):
        BUILD = "build", "Image yigʻish"
        JUDGE = "judge", "Tekshirish"
        REJUDGE = "rejudge", "Qayta tekshirish"

    class Status(models.TextChoices):
        QUEUED = "queued", "Navbatda"
        RUNNING = "running", "Bajarilmoqda"
        DONE = "done", "Tugadi"
        FAILED = "failed", "Xato"

    # Lower runs first: a teacher waits on a build, students on their checks.
    class Priority(models.IntegerChoices):
        BUILD = 0
        JUDGE = 10
        REJUDGE = 20

    kind = models.CharField(max_length=10, choices=Kind.choices)
    lane = models.CharField(max_length=10, choices=[(lane, lane) for lane in Lane])
    priority = models.SmallIntegerField(choices=Priority.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    task_version = models.ForeignKey(
        "tasks.TaskVersion", on_delete=models.CASCADE, null=True, blank=True, related_name="jobs"
    )
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="jobs",
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    worker_node = models.CharField(max_length=100, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        verbose_name = "vazifa (navbat)"
        verbose_name_plural = "navbat"
        ordering = ("priority", "created_at", "pk")
        indexes = (models.Index(fields=("status", "lane", "priority", "created_at")),)
        constraints = (
            models.CheckConstraint(
                condition=Q(kind="build", task_version__isnull=False, submission__isnull=True)
                | Q(
                    kind__in=["judge", "rejudge"],
                    task_version__isnull=True,
                    submission__isnull=False,
                ),
                name="system_job_target_matches_kind",
            ),
        )

    def __str__(self) -> str:
        return f"{self.kind} #{self.pk} ({self.status})"


class WorkerNodeQuerySet(models.QuerySet["WorkerNode"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        return _superadmin_only(self, user)


class WorkerNode(models.Model):
    name = models.CharField(max_length=100, unique=True)
    arch = models.CharField(max_length=20)
    slots = models.JSONField(default=dict)  # {"heavy": 1, "fast": 1}
    version = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField()
    last_heartbeat = models.DateTimeField()

    objects = WorkerNodeQuerySet.as_manager()

    class Meta:
        verbose_name = "worker"
        verbose_name_plural = "workerlar"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name
