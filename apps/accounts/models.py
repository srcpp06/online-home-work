"""Centres, users with roles and study groups (SPEC §1, §2).

Each model's queryset has for_user(user): the rows that user may see. It fails closed: an
anonymous or inactive user, or an unknown role, sees nothing. Views take objects only
through get_for_user_or_404 (apps.accounts.access).
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Self
from uuid import uuid4

from django import forms
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser


class Role(models.TextChoices):
    SUPERADMIN = "superadmin", "Superadmin"
    CENTER_ADMIN = "center_admin", "Markaz admini"
    # Heads the centre: watches all of it and keeps its admins (apps.accounts.permissions).
    CENTER_MANAGER = "center_manager", "Markaz menejeri"
    TEACHER = "teacher", "Oʻqituvchi"
    STUDENT = "student", "Oʻquvchi"


class Direction(models.TextChoices):
    """A teacher's directions decide which runner profiles they can use."""

    FLUTTER = "flutter", "Flutter"
    BACKEND = "backend", "Backend"
    FRONTEND = "frontend", "Frontend"


def active_viewer(user: "User | AnonymousUser") -> Any:
    """The user if they may see anything at all, else None."""
    if not user.is_authenticated or not user.is_active:
        return None
    return user


class CenterQuerySet(models.QuerySet["Center"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        if viewer.role == Role.SUPERADMIN:
            return self.all()
        return self.filter(pk=viewer.center_id) if viewer.center_id else self.none()


class Center(models.Model):
    name = models.CharField("nomi", max_length=200)
    slug = models.SlugField("slug", unique=True)
    is_active = models.BooleanField("faol", default=True)

    objects = CenterQuerySet.as_manager()

    class Meta:
        verbose_name = "markaz"
        verbose_name_plural = "markazlar"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class UserQuerySet(models.QuerySet["User"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        match viewer.role:
            case Role.SUPERADMIN:
                return self.all()
            case Role.CENTER_ADMIN:
                # The teachers and students they manage, and themselves.
                return self.filter(
                    Q(pk=viewer.pk)
                    | Q(center_id=viewer.center_id, role__in=(Role.TEACHER, Role.STUDENT))
                )
            case Role.CENTER_MANAGER:
                # Everyone in their centre: they watch it all and keep its admins.
                return self.filter(center_id=viewer.center_id)
            case Role.TEACHER:
                return self.filter(Q(pk=viewer.pk) | Q(study_groups__teacher=viewer)).distinct()
            case Role.STUDENT:
                return self.filter(pk=viewer.pk)
        return self.none()


class UserManager(DjangoUserManager.from_queryset(UserQuerySet)):
    def create_superuser(
        self, username: str, email: str | None = None, password: str | None = None, **extra: Any
    ) -> "User":
        # `manage.py createsuperuser` makes Erkin's account: the superadmin, who signs in
        # to /admin/ and has no first-login password change.
        extra.setdefault("role", Role.SUPERADMIN)
        extra.setdefault("must_change_password", False)
        return super().create_superuser(username, email, password, **extra)


def _avatar_path(user: "User", filename: str) -> str:
    """A new name for each picture, so a browser never shows a stale one from its cache."""
    return f"avatars/{user.center_id or 0}/{user.pk}/{uuid4().hex}.webp"


class DirectionsField(ArrayField):
    """A list of directions, edited as checkboxes instead of comma-separated text."""

    def formfield(self, **kwargs: Any) -> forms.Field:
        defaults = {
            "form_class": forms.TypedMultipleChoiceField,
            "choices": self.base_field.choices,
            "coerce": str,
            "widget": forms.CheckboxSelectMultiple,
            **kwargs,
        }
        # Field.formfield, not ArrayField's: that one builds a comma-separated text field.
        return super(ArrayField, self).formfield(**defaults)


class User(AbstractUser):
    """A platform user (SPEC §1, §2). Login is the username; email is optional.

    The role decides everything: only the superadmin has no centre and may use /admin/
    (is_staff and is_superuser follow the role on save); only teachers have directions.
    The database checks the same rules, so no code path can break them.
    """

    role = models.CharField("rol", max_length=20, choices=Role.choices)
    center = models.ForeignKey(
        Center,
        verbose_name="markaz",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    directions = DirectionsField(
        models.CharField(max_length=20, choices=Direction.choices),
        verbose_name="yoʻnalishlar",
        default=list,
        blank=True,
    )
    must_change_password = models.BooleanField("parolni almashtirishi kerak", default=True)
    # The profile (apps.accounts.views.profile): what the person says about themselves.
    avatar = models.FileField("rasm", upload_to=_avatar_path, max_length=300, blank=True)
    phone = models.CharField("telefon", max_length=20, blank=True)
    telegram = models.CharField("Telegram", max_length=33, blank=True)
    bio = models.TextField("oʻzi haqida", max_length=500, blank=True)

    REQUIRED_FIELDS: list[str] = []  # noqa: RUF012 -- Django's documented class attribute

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = "foydalanuvchi"
        verbose_name_plural = "foydalanuvchilar"
        constraints = (
            models.CheckConstraint(
                condition=Q(role__in=Role.values),
                name="accounts_user_role_valid",
                violation_error_message="Rolni tanlang.",
            ),
            models.CheckConstraint(
                condition=Q(role=Role.SUPERADMIN, center__isnull=True)
                | (~Q(role=Role.SUPERADMIN) & Q(center__isnull=False)),
                name="accounts_user_center_matches_role",
                violation_error_message=(
                    "Superadmin markazga biriktirilmaydi, boshqa rollar uchun markazni tanlang."
                ),
            ),
            models.CheckConstraint(
                condition=Q(role=Role.SUPERADMIN, is_staff=True, is_superuser=True)
                | (~Q(role=Role.SUPERADMIN) & Q(is_staff=False, is_superuser=False)),
                name="accounts_user_only_superadmin_is_staff",
                violation_error_message="Admin panelga faqat superadmin kira oladi.",
            ),
            models.CheckConstraint(
                condition=Q(role=Role.TEACHER) | Q(directions=[]),
                name="accounts_user_directions_only_for_teachers",
                violation_error_message="Yoʻnalishlar faqat oʻqituvchiga biriktiriladi.",
            ),
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.is_staff = self.is_superuser = self.role == Role.SUPERADMIN
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """ "Familiya Ism" as in class journals; the login when no name was entered."""
        return " ".join(filter(None, (self.last_name, self.first_name))) or self.username

    @property
    def initials(self) -> str:
        """Two letters for the picture's place when there is no picture."""
        letters = [name[0] for name in (self.first_name, self.last_name) if name]
        return ("".join(letters) or self.username[:2]).upper()

    @property
    def directions_display(self) -> str:
        return ", ".join(Direction(d).label for d in self.directions if d in Direction.values)

    def clean(self) -> None:
        super().clean()
        unknown = set(self.directions) - set(Direction.values)
        if unknown:
            raise ValidationError({"directions": f"Nomaʼlum yoʻnalish: {', '.join(unknown)}"})


class GroupQuerySet(models.QuerySet["Group"]):
    def for_user(self, user: "User | AnonymousUser") -> Self:
        viewer = active_viewer(user)
        if viewer is None:
            return self.none()
        match viewer.role:
            case Role.SUPERADMIN:
                return self.all()
            case Role.CENTER_ADMIN | Role.CENTER_MANAGER:
                return self.filter(center_id=viewer.center_id)
            case Role.TEACHER:
                return self.filter(teacher=viewer)
            case Role.STUDENT:
                return self.filter(students=viewer)
        return self.none()


class Group(models.Model):
    """A study group of one centre. Not django.contrib.auth's Group, which is unused."""

    center = models.ForeignKey(
        Center, verbose_name="markaz", on_delete=models.PROTECT, related_name="groups"
    )
    name = models.CharField("nomi", max_length=200)
    teacher = models.ForeignKey(
        User,
        verbose_name="oʻqituvchi",
        on_delete=models.PROTECT,
        related_name="teaching_groups",
    )
    students = models.ManyToManyField(
        User, verbose_name="oʻquvchilar", related_name="study_groups", blank=True
    )
    show_journal_to_students = models.BooleanField("jurnal oʻquvchilarga koʻrinadi", default=False)

    objects = GroupQuerySet.as_manager()

    class Meta:
        verbose_name = "guruh"
        verbose_name_plural = "guruhlar"
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=("center", "name"),
                name="accounts_group_name_unique_in_center",
                violation_error_message="Bu markazda shu nomli guruh bor.",
            ),
        )

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.teacher_id is None or self.center_id is None:
            return  # the required-field errors say enough
        if self.teacher.role != Role.TEACHER or self.teacher.center_id != self.center_id:
            raise ValidationError({"teacher": "Shu markazning oʻqituvchisini tanlang."})

    def add_students(self, students: Iterable[User]) -> None:
        """The only way to add students: each must be a student of this group's centre."""
        students = list(students)
        check_students(self.center_id, students)
        self.students.add(*students)


def check_students(center_id: int | None, students: Iterable[User]) -> None:
    wrong = [s.username for s in students if s.role != Role.STUDENT or s.center_id != center_id]
    if wrong:
        raise ValidationError(
            f"Bu foydalanuvchilar shu markazning oʻquvchisi emas: {', '.join(wrong)}"
        )
