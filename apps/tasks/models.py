"""Runner profiles, tasks with their versions, and assignments to groups (SPEC §2).

A task belongs to its author's centre. Each uploaded package is a new TaskVersion, built
into its own image by the worker; publishing points the task at a ready version. Students
reach a task only through an assignment of one of their groups that has opened.
"""

from typing import TYPE_CHECKING, Self

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Direction, Group, Role, User, active_viewer
from judge.core.profile import Lane
from judge.core.profile import RunnerProfile as JudgeProfile

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser


class RunnerProfileQuerySet(models.QuerySet["RunnerProfile"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None or viewer.role == Role.STUDENT:
            return self.none()
        if viewer.role == Role.SUPERADMIN:
            return self.all()
        active = self.filter(is_active=True)
        # A teacher builds tasks only in their directions (SPEC §1).
        return (
            active.filter(direction__in=viewer.directions)
            if viewer.role == Role.TEACHER
            else active
        )


class RunnerProfile(models.Model):
    """A language environment; the settings are profiles/<slug>/profile.json (load_profiles)."""

    slug = models.SlugField("slug", unique=True)
    title = models.CharField("nomi", max_length=100)
    direction = models.CharField("yoʻnalish", max_length=20, choices=Direction.choices)
    lane = models.CharField("navbat", max_length=10, choices=[(lane, lane) for lane in Lane])
    config = models.JSONField("sozlamalar")
    is_active = models.BooleanField("faol", default=True)

    objects = RunnerProfileQuerySet.as_manager()

    class Meta:
        verbose_name = "runner profil"
        verbose_name_plural = "runner profillar"
        ordering = ("title",)

    def __str__(self) -> str:
        return self.title

    def judge_profile(self) -> JudgeProfile:
        return JudgeProfile.from_json_data(self.config)

    def clean(self) -> None:
        try:
            profile = self.judge_profile()
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError({"config": f"Profil sozlamalari notoʻgʻri: {error}"}) from None
        if profile.slug != self.slug or profile.lane != self.lane:
            raise ValidationError({"config": "slug va lane maydonlar bilan bir xil boʻlsin."})


class TaskQuerySet(models.QuerySet["Task"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        match viewer.role:
            case Role.SUPERADMIN:
                return self.all()
            case Role.CENTER_MANAGER:
                return self.filter(center_id=viewer.center_id)
            case Role.TEACHER:
                return self.filter(author=viewer)
            case Role.STUDENT:
                open_assignments = Assignment.objects.for_user(viewer)
                return self.filter(assignments__in=open_assignments).distinct()
        return self.none()


class Task(models.Model):
    center = models.ForeignKey(
        "accounts.Center", verbose_name="markaz", on_delete=models.PROTECT, related_name="tasks"
    )
    author = models.ForeignKey(
        User, verbose_name="muallif", on_delete=models.PROTECT, related_name="authored_tasks"
    )
    profile = models.ForeignKey(
        RunnerProfile, verbose_name="profil", on_delete=models.PROTECT, related_name="tasks"
    )
    title = models.CharField("nomi", max_length=200)
    statement_md = models.TextField("shart (Markdown)")
    published_version = models.ForeignKey(
        "TaskVersion",
        verbose_name="eʼlon qilingan versiya",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    is_archived = models.BooleanField("arxivda", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        verbose_name = "topshiriq"
        verbose_name_plural = "topshiriqlar"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.author_id and self.center_id and self.author.center_id != self.center_id:
            raise ValidationError({"author": "Muallif shu markazning oʻqituvchisi boʻlishi kerak."})
        if self.published_version_id and (
            self.published_version.task_id != self.pk
            or self.published_version.status != TaskVersion.Status.READY
        ):
            raise ValidationError(
                {"published_version": "Faqat shu topshiriqning tayyor versiyasi."}
            )


def _package_path(version: "TaskVersion", filename: str) -> str:
    return f"tasks/{version.task.center_id}/{version.task_id}/v{version.number}/package.zip"


def _starter_path(version: "TaskVersion", filename: str) -> str:
    return f"tasks/{version.task.center_id}/{version.task_id}/v{version.number}/starter.zip"


class TaskVersionQuerySet(models.QuerySet["TaskVersion"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        visible = self.filter(task__in=Task.objects.for_user(viewer))
        if viewer.role == Role.STUDENT:
            # Only what was published: drafts and failed builds are the teacher's.
            return visible.filter(task__published_version=models.F("pk"))
        return visible


class TaskVersion(models.Model):
    """One uploaded package of a task and its image (SPEC §3.3)."""

    class Status(models.TextChoices):
        BUILDING = "building", "Yigʻilmoqda"
        BUILD_FAILED = "build_failed", "Yigʻilmadi"
        READY = "ready", "Tayyor"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField("versiya")
    package = models.FileField("paket", upload_to=_package_path, max_length=300)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BUILDING)
    image_tag = models.CharField(max_length=200, blank=True)
    build_log = models.TextField(blank=True)  # for the teacher; may show hidden tests
    build_errors = models.JSONField(default=list, blank=True)  # short messages for the teacher
    manifest = models.JSONField(null=True, blank=True)  # judge.core.manifest.Manifest
    import_rules = models.JSONField(null=True, blank=True)  # judge.packaging.dart_imports
    starter = models.FileField(upload_to=_starter_path, max_length=300, blank=True)
    solution_wall_ms = models.PositiveIntegerField(null=True, blank=True)
    warm_wall_ms = models.PositiveIntegerField(null=True, blank=True)
    time_limit_s = models.PositiveIntegerField("vaqt limiti, s", null=True, blank=True)
    memory_limit_mb = models.PositiveIntegerField(null=True, blank=True)  # None: the profile's
    runtime_info = models.CharField(max_length=200, blank=True)  # e.g. "Flutter 3.47.5"
    created_at = models.DateTimeField(auto_now_add=True)
    built_at = models.DateTimeField(null=True, blank=True)

    objects = TaskVersionQuerySet.as_manager()

    class Meta:
        verbose_name = "topshiriq versiyasi"
        verbose_name_plural = "topshiriq versiyalari"
        ordering = ("task", "-number")
        constraints = (
            models.UniqueConstraint(fields=("task", "number"), name="tasks_version_number_unique"),
        )

    def __str__(self) -> str:
        return f"{self.task} v{self.number}"

    @property
    def test_count(self) -> int:
        return len((self.manifest or {}).get("tests", []))


class AssignmentQuerySet(models.QuerySet["Assignment"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        match viewer.role:
            case Role.SUPERADMIN:
                return self.all()
            case Role.CENTER_MANAGER:
                return self.filter(group__center_id=viewer.center_id)
            case Role.TEACHER:
                return self.filter(group__teacher=viewer)
            case Role.STUDENT:
                return self.filter(
                    group__students=viewer,
                    opens_at__lte=timezone.now(),
                    task__published_version__isnull=False,
                    task__is_archived=False,
                ).distinct()
        return self.none()


class Assignment(models.Model):
    """A task given to a group: when it opens, its deadline and its attempt limit."""

    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="assignments")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="assignments")
    opens_at = models.DateTimeField("ochilish vaqti", default=timezone.now)
    deadline = models.DateTimeField("muddat", null=True, blank=True)
    allow_late = models.BooleanField("kechikib yuborishga ruxsat", default=False)
    max_attempts = models.PositiveIntegerField("urinishlar limiti", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AssignmentQuerySet.as_manager()

    class Meta:
        verbose_name = "biriktirish"
        verbose_name_plural = "biriktirishlar"
        ordering = ("-opens_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("task", "group"), name="tasks_assignment_once_per_group"
            ),
            models.CheckConstraint(
                condition=Q(deadline__isnull=True) | Q(deadline__gt=models.F("opens_at")),
                name="tasks_assignment_deadline_after_opening",
                violation_error_message="Muddat ochilish vaqtidan keyin boʻlishi kerak.",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__isnull=True) | Q(max_attempts__gte=1),
                name="tasks_assignment_attempts_positive",
                violation_error_message="Urinishlar limiti kamida 1 boʻlsin yoki boʻsh qolsin.",
            ),
        )

    def __str__(self) -> str:
        return f"{self.task} — {self.group}"

    def clean(self) -> None:
        super().clean()
        if self.task_id and self.group_id and self.task.center_id != self.group.center_id:
            raise ValidationError({"group": "Guruh topshiriq bilan bir markazdan boʻlishi kerak."})

    @property
    def is_open(self) -> bool:
        return self.opens_at <= timezone.now()

    def is_past_deadline(self, at: "timezone.datetime | None" = None) -> bool:
        return self.deadline is not None and (at or timezone.now()) > self.deadline
