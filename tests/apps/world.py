"""Two centres with every role, for permission and IDOR tests."""

from dataclasses import dataclass

from apps.accounts.models import Center, Direction, Group, Role, User

PASSWORD = "test-Parol-2026"  # noqa: S105 -- test accounts only


def make_user(username: str, role: Role, center: Center | None = None, **extra: object) -> User:
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
    )


@dataclass(frozen=True)
class World:
    superadmin: User
    a: CenterWorld
    b: CenterWorld


def make_world() -> World:
    superadmin = User.objects.create_superuser(username="erkin", password=PASSWORD)
    return World(superadmin=superadmin, a=make_center("a"), b=make_center("b"))
