"""The role table (SPEC §1): who may do what kind of thing."""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import Role, User
from apps.accounts.permissions import MANAGES, ROLE_ACTIONS, Action, can, manages
from tests.apps.world import World


def test_every_role_is_in_the_table() -> None:
    assert set(ROLE_ACTIONS) == set(Role)


def test_center_manager_watches_everything_and_manages_only_admins() -> None:
    actions = ROLE_ACTIONS[Role.CENTER_MANAGER]

    assert actions == {
        Action.VIEW_PEOPLE,
        Action.VIEW_GROUPS,
        Action.VIEW_TASKS,
        Action.VIEW_JOURNAL,
        Action.VIEW_CODE,
        Action.MANAGE_PEOPLE,
    }
    assert MANAGES[Role.CENTER_MANAGER] == {Role.CENTER_ADMIN}
    # The judge's raw log can carry hidden test details; it is for fixing faults.
    assert Action.VIEW_FULL_LOG not in actions


def test_center_admin_works_with_people_and_groups_only() -> None:
    assert ROLE_ACTIONS[Role.CENTER_ADMIN] == {
        Action.VIEW_PEOPLE,
        Action.VIEW_GROUPS,
        Action.MANAGE_PEOPLE,
        Action.MANAGE_GROUPS,
    }
    assert MANAGES[Role.CENTER_ADMIN] == {Role.TEACHER, Role.STUDENT}


def test_who_manages_whom() -> None:
    assert {
        Role.SUPERADMIN: {Role.CENTER_MANAGER, Role.CENTER_ADMIN, Role.TEACHER, Role.STUDENT},
        Role.CENTER_MANAGER: {Role.CENTER_ADMIN},
        Role.CENTER_ADMIN: {Role.TEACHER, Role.STUDENT},
    } == MANAGES


@pytest.mark.parametrize(
    ("action", "roles"),
    [
        (Action.MANAGE_CENTERS, {Role.SUPERADMIN}),
        (Action.MANAGE_PEOPLE, {Role.SUPERADMIN, Role.CENTER_MANAGER, Role.CENTER_ADMIN}),
        (Action.MANAGE_GROUPS, {Role.SUPERADMIN, Role.CENTER_ADMIN}),
        (Action.MANAGE_TASKS, {Role.TEACHER}),
        (Action.SUBMIT, {Role.STUDENT}),
        (Action.MANAGE_SYSTEM, {Role.SUPERADMIN}),
        (Action.VIEW_FULL_LOG, {Role.SUPERADMIN, Role.TEACHER}),
        (Action.VIEW_TASKS, {Role.SUPERADMIN, Role.CENTER_MANAGER, Role.TEACHER}),
        (
            Action.VIEW_JOURNAL,
            {Role.SUPERADMIN, Role.CENTER_MANAGER, Role.TEACHER, Role.STUDENT},
        ),
    ],
)
def test_who_may_do_what(action: Action, roles: set[Role]) -> None:
    assert {role for role, actions in ROLE_ACTIONS.items() if action in actions} == roles


@pytest.mark.django_db
def test_manages_needs_the_role_and_an_active_account(world: World) -> None:
    a = world.a

    assert manages(a.manager, Role.CENTER_ADMIN)
    assert not manages(a.manager, Role.TEACHER)
    assert manages(a.admin, Role.STUDENT)
    assert not manages(a.admin, Role.CENTER_MANAGER)
    assert not manages(a.teacher, Role.STUDENT)
    a.admin.is_active = False
    assert not manages(a.admin, Role.STUDENT)


@pytest.mark.django_db
def test_can_follows_the_users_role(world: World) -> None:
    assert can(world.a.manager, Action.VIEW_JOURNAL)
    assert not can(world.a.manager, Action.MANAGE_GROUPS)
    assert can(world.a.teacher, Action.MANAGE_TASKS)
    assert not can(world.a.student, Action.VIEW_GROUPS)


@pytest.mark.django_db
def test_can_fails_closed(world: World) -> None:
    inactive = world.a.admin
    inactive.is_active = False
    unknown = User(username="x", role="owner", center=world.a.center)

    for user in (AnonymousUser(), inactive, unknown):
        assert not any(can(user, action) for action in Action)
