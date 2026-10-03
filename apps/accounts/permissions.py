"""What each role may do (SPEC §1), as one table.

can(user, action) says whether the user's role may do this kind of thing at all; which
rows it reaches is for_user()'s job. A view checks both. Like for_user, it fails closed:
anonymous and inactive users, and roles missing from the table, may do nothing.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from apps.accounts.models import Role

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.models import User


class Action(StrEnum):
    MANAGE_CENTERS = "manage_centers"  # centres and their admins
    MANAGE_PEOPLE = "manage_people"  # add, edit, reset password: the roles in MANAGES
    VIEW_PEOPLE = "view_people"
    MANAGE_GROUPS = "manage_groups"
    VIEW_GROUPS = "view_groups"  # a group's page: its teacher and students
    MANAGE_TASKS = "manage_tasks"  # create, upload the package, assign, rejudge
    VIEW_TASKS = "view_tasks"  # statement, settings, test names; never the package
    VIEW_JOURNAL = "view_journal"  # a student: only where their group shows it
    VIEW_CODE = "view_code"  # a submission's code and test results; a student: their own
    VIEW_FULL_LOG = "view_full_log"  # the judge's raw log, for finding faults
    SUBMIT = "submit"
    MANAGE_SYSTEM = "manage_system"  # runner profiles, /system


_WATCH = frozenset(
    {
        Action.VIEW_PEOPLE,
        Action.VIEW_GROUPS,
        Action.VIEW_TASKS,
        Action.VIEW_JOURNAL,
        Action.VIEW_CODE,
    }
)

ROLE_ACTIONS: dict[Role, frozenset[Action]] = {
    Role.SUPERADMIN: _WATCH
    | {
        Action.MANAGE_CENTERS,
        Action.MANAGE_PEOPLE,
        Action.MANAGE_GROUPS,
        Action.VIEW_FULL_LOG,
        Action.MANAGE_SYSTEM,
    },
    # The head of the centre: watches everything its teachers and students do, and keeps
    # its admins (MANAGES). Gets neither hidden tests nor raw logs: not needed to watch.
    Role.CENTER_MANAGER: _WATCH | {Action.MANAGE_PEOPLE},
    # Runs the centre's people and groups; tasks, solutions and journals are not theirs.
    Role.CENTER_ADMIN: frozenset(
        {Action.VIEW_PEOPLE, Action.VIEW_GROUPS, Action.MANAGE_PEOPLE, Action.MANAGE_GROUPS}
    ),
    Role.TEACHER: _WATCH | {Action.MANAGE_TASKS, Action.VIEW_FULL_LOG},
    Role.STUDENT: frozenset({Action.VIEW_JOURNAL, Action.VIEW_CODE, Action.SUBMIT}),
}

# Whose accounts each role adds, edits, resets and deletes (MANAGE_PEOPLE), always within
# its own centre. The superadmin does it in Django admin.
MANAGES: dict[Role, frozenset[Role]] = {
    Role.SUPERADMIN: frozenset(
        {Role.CENTER_MANAGER, Role.CENTER_ADMIN, Role.TEACHER, Role.STUDENT}
    ),
    Role.CENTER_MANAGER: frozenset({Role.CENTER_ADMIN}),
    Role.CENTER_ADMIN: frozenset({Role.TEACHER, Role.STUDENT}),
}


def can(user: "User | AnonymousUser", action: Action) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    return action in ROLE_ACTIONS.get(user.role, frozenset())


def manages(user: "User | AnonymousUser", role: str) -> bool:
    """Whether the user may manage accounts of this role (in their centre)."""
    return can(user, Action.MANAGE_PEOPLE) and role in MANAGES.get(user.role, frozenset())
