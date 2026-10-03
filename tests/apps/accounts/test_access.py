"""The permission layer (SPEC §1): what each role sees, and IDOR across centres."""

from collections.abc import Callable

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.models import Session
from django.db import models
from django.http import Http404

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.models import Center, Group, User
from tests.apps.world import World

Pick = Callable[[World], models.Model]


def seen(model: type[models.Model], user: User | AnonymousUser) -> set[models.Model]:
    return set(visible_to(model, user))


def test_superadmin_sees_everything(world: World) -> None:
    for model in (Center, User, Group):
        assert seen(model, world.superadmin) == set(model.objects.all())


def test_center_admin_sees_their_centre_only(world: World) -> None:
    a = world.a

    assert seen(Center, a.admin) == {a.center}
    assert seen(User, a.admin) == {
        a.admin,
        a.manager,
        a.teacher,
        a.other_teacher,
        a.student,
        a.other_student,
    }
    assert seen(Group, a.admin) == {a.group, a.other_group}


def test_center_manager_watches_their_whole_centre(world: World) -> None:
    a = world.a

    assert seen(Center, a.manager) == {a.center}
    assert seen(User, a.manager) == {
        a.manager,
        a.teacher,
        a.other_teacher,
        a.student,
        a.other_student,
    }
    assert seen(Group, a.manager) == {a.group, a.other_group}


def test_teacher_sees_their_groups_and_students(world: World) -> None:
    a = world.a

    assert seen(Center, a.teacher) == {a.center}
    assert seen(User, a.teacher) == {a.teacher, a.student}
    assert seen(Group, a.teacher) == {a.group}


def test_teacher_sees_a_student_once_across_groups(world: World) -> None:
    a = world.a
    second = Group.objects.create(center=a.center, name="Flutter 3", teacher=a.teacher)
    second.add_students([a.student])

    assert list(visible_to(User, a.teacher).filter(pk=a.student.pk)) == [a.student]


def test_student_sees_themselves_and_their_groups(world: World) -> None:
    a = world.a

    assert seen(Center, a.student) == {a.center}
    assert seen(User, a.student) == {a.student}
    assert seen(Group, a.student) == {a.group}


@pytest.mark.parametrize("model", [Center, User, Group])
def test_anonymous_sees_nothing(world: World, model: type[models.Model]) -> None:
    assert seen(model, AnonymousUser()) == set()


@pytest.mark.parametrize("model", [Center, User, Group])
def test_inactive_user_sees_nothing(world: World, model: type[models.Model]) -> None:
    world.a.admin.is_active = False

    assert seen(model, world.a.admin) == set()


# Every object of centre b, and centre a's objects outside a role's reach.
OTHER_CENTRE: dict[str, Pick] = {
    "center": lambda w: w.b.center,
    "admin": lambda w: w.b.admin,
    "manager": lambda w: w.b.manager,
    "teacher": lambda w: w.b.teacher,
    "student": lambda w: w.b.student,
    "group": lambda w: w.b.group,
}
VIEWERS: dict[str, Callable[[World], User]] = {
    "center_admin": lambda w: w.a.admin,
    "center_manager": lambda w: w.a.manager,
    "teacher": lambda w: w.a.teacher,
    "student": lambda w: w.a.student,
}


@pytest.mark.parametrize("viewer", VIEWERS)
@pytest.mark.parametrize("target", OTHER_CENTRE)
def test_another_centres_object_is_404(world: World, viewer: str, target: str) -> None:
    obj = OTHER_CENTRE[target](world)

    with pytest.raises(Http404):
        get_for_user_or_404(type(obj), VIEWERS[viewer](world), pk=obj.pk)


@pytest.mark.parametrize(
    ("viewer", "target"),
    [
        (lambda w: w.a.teacher, lambda w: w.a.other_group),
        (lambda w: w.a.teacher, lambda w: w.a.other_student),
        (lambda w: w.a.teacher, lambda w: w.a.admin),
        (lambda w: w.a.student, lambda w: w.a.other_group),
        (lambda w: w.a.student, lambda w: w.a.other_student),
        (lambda w: w.a.student, lambda w: w.a.teacher),
        (lambda w: w.a.admin, lambda w: w.superadmin),
        (lambda w: w.a.manager, lambda w: w.a.admin),
        (lambda w: w.a.manager, lambda w: w.superadmin),
        (lambda w: w.a.teacher, lambda w: w.a.manager),
        (lambda w: w.a.student, lambda w: w.a.manager),
    ],
    ids=[
        "teacher-other-group",
        "teacher-other-student",
        "teacher-centre-admin",
        "student-other-group",
        "student-other-student",
        "student-teacher",
        "centre-admin-superadmin",
        "manager-centre-admin",
        "manager-superadmin",
        "teacher-manager",
        "student-manager",
    ],
)
def test_same_centre_object_outside_the_role_is_404(
    world: World, viewer: Callable[[World], User], target: Pick
) -> None:
    obj = target(world)

    with pytest.raises(Http404):
        get_for_user_or_404(type(obj), viewer(world), pk=obj.pk)


def test_own_objects_are_found(world: World) -> None:
    a = world.a

    assert get_for_user_or_404(Group, a.teacher, pk=a.group.pk) == a.group
    assert get_for_user_or_404(User, a.teacher, pk=a.student.pk) == a.student
    assert get_for_user_or_404(Center, a.student, slug="a") == a.center


def test_a_model_without_for_user_is_refused(world: World) -> None:
    with pytest.raises(TypeError, match="Session's queryset has no for_user"):
        visible_to(Session, world.superadmin)


def test_every_project_model_has_for_user() -> None:
    project_models = [m for m in apps.get_models() if m.__module__.startswith("apps.")]
    missing = [
        m.__name__ for m in project_models if not hasattr(m._default_manager.all(), "for_user")
    ]

    assert project_models
    assert not missing, f"add for_user(user) to: {', '.join(missing)}"
