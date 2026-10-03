"""The role table (SPEC §1): who may do what kind of thing."""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import Role, User
from apps.accounts.permissions import ROLE_ACTIONS, Action, can
from tests.apps.world import World


def test_every_role_is_in_the_table() -> None:
    assert set(ROLE_ACTIONS) == set(Role)


def test_center_manager_only_watches() -> None:
    actions = ROLE_ACTIONS[Role.CENTER_MANAGER]

    assert actions == {
        Action.VIEW_PEOPLE,
        Action.VIEW_GROUPS,
        Action.VIEW_TASKS,
        Action.VIEW_JOURNAL,
        Action.VIEW_CODE,
    }
    assert all(action.startswith("view_") for action in actions)
    # The judge's raw log can carry hidden test details; it is for fixing faults.
    assert Action.VIEW_FULL_LOG not in actions


@pytest.mark.parametrize(
    ("action", "roles"),
    [
        (Action.MANAGE_CENTERS, {Role.SUPERADMIN}),
        (Action.MANAGE_PEOPLE, {Role.SUPERADMIN, Role.CENTER_ADMIN}),
        (Action.MANAGE_GROUPS, {Role.SUPERADMIN, Role.CENTER_ADMIN}),
        (Action.MANAGE_TASKS, {Role.TEACHER}),
        (Action.SUBMIT, {Role.STUDENT}),
        (Action.MANAGE_SYSTEM, {Role.SUPERADMIN}),
        (Action.VIEW_FULL_LOG, {Role.SUPERADMIN, Role.CENTER_ADMIN, Role.TEACHER}),
    ],
)
def test_who_may_change_things(action: Action, roles: set[Role]) -> None:
    assert {role for role, actions in ROLE_ACTIONS.items() if action in actions} == roles


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
