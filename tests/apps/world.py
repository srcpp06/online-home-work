"""Two centres with every role, for permission and IDOR tests."""

import io
from dataclasses import dataclass
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Center, Direction, Group, Role, User
from apps.submissions.models import Submission
from apps.tasks.models import Assignment, RunnerProfile, Task, TaskVersion
from judge.core.verdict import Verdict

PASSWORD = "test-Parol-2026"  # noqa: S105 -- test accounts only


def make_user(username: str, role: Role, center: Center | None = None, **extra: object) -> User:
    """A user past their first sign-in; tests of that sign-in set must_change_password."""
    extra.setdefault("must_change_password", False)
    if role == Role.TEACHER:
        extra.setdefault("directions", [Direction.FLUTTER])
    return User.objects.create_user(
        username=username, password=PASSWORD, role=role, center=center, **extra
    )


@dataclass(frozen=True)
class CenterWorld:
    center: Center
    admin: User
    manager: User
    teacher: User
    student: User  # in group, taught by teacher
    group: Group
    other_teacher: User
    other_student: User  # in other_group, taught by other_teacher
    other_group: Group
    task: Task  # by teacher, published
    version: TaskVersion
    assignment: Assignment  # task given to group, open now
    submission: Submission  # student's accepted solution


def make_center(slug: str) -> CenterWorld:
    center = Center.objects.create(name=f"Markaz {slug}", slug=slug)
    teacher = make_user(f"{slug}-teacher", Role.TEACHER, center)
    other_teacher = make_user(f"{slug}-teacher2", Role.TEACHER, center)
    student = make_user(f"{slug}-student", Role.STUDENT, center)
    other_student = make_user(f"{slug}-student2", Role.STUDENT, center)
    group = Group.objects.create(center=center, name="Flutter 1", teacher=teacher)
    group.add_students([student])
    other_group = Group.objects.create(center=center, name="Flutter 2", teacher=other_teacher)
    other_group.add_students([other_student])
    task, version = make_task(teacher, "Savat hisobi")
    assignment = Assignment.objects.create(
        task=task,
        group=group,
        opens_at=timezone.now() - timedelta(hours=1),
        deadline=timezone.now() + timedelta(days=7),
    )
    submission = Submission.objects.create(
        assignment=assignment,
        student=student,
        task_version=version,
        archive=ContentFile(b"PK\x05\x06" + bytes(18), name="solution.zip"),
        sha256="0" * 64,
        status=Submission.Status.FINISHED,
        verdict=Verdict.ACCEPTED,
        tests_total=2,
        tests_passed=2,
    )
    return CenterWorld(
        center=center,
        admin=make_user(f"{slug}-admin", Role.CENTER_ADMIN, center),
        manager=make_user(f"{slug}-manager", Role.CENTER_MANAGER, center),
        teacher=teacher,
        student=student,
        group=group,
        other_teacher=other_teacher,
        other_student=other_student,
        other_group=other_group,
        task=task,
        version=version,
        assignment=assignment,
        submission=submission,
    )


def make_task(author: User, title: str, *, publish: bool = True) -> tuple[Task, TaskVersion]:
    """A dart task with one ready version, as if the worker had built it."""
    task = Task.objects.create(
        center=author.center,
        author=author,
        profile=RunnerProfile.objects.get(slug="dart"),
        title=title,
        statement_md="Savatdagi mahsulotlar narxini hisoblang.",
    )
    version = TaskVersion.objects.create(
        task=task,
        number=1,
        package=ContentFile(b"PK\x05\x06" + bytes(18), name="package.zip"),
        sha256="1" * 64,
        status=TaskVersion.Status.READY,
        image_tag=f"ohw-task:{task.pk}-111111111111",
        manifest={
            "tests": [
                {"name": "Savat boʻsh", "stage": 1, "visibility": "public"},
                {"name": "Chegirma", "stage": 1, "visibility": "hidden"},
            ]
        },
        time_limit_s=15,
    )
    if publish:
        task.published_version = version
        task.save()
    return task, version


@dataclass(frozen=True)
class World:
    superadmin: User
    a: CenterWorld
    b: CenterWorld


def make_world() -> World:
    call_command("load_profiles", stdout=io.StringIO())
    superadmin = User.objects.create_superuser(username="erkin", password=PASSWORD)
    return World(superadmin=superadmin, a=make_center("a"), b=make_center("b"))
