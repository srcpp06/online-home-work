"""Migration 0002 on a database made before roles (Erkin's createsuperuser account)."""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import Role, User
from tests.apps.world import PASSWORD

BEFORE = [("accounts", "0001_initial")]
AFTER = [("accounts", "0002_center_roles_group")]


@pytest.fixture
def executor(transactional_db: None) -> Iterator[MigrationExecutor]:
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    yield executor
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


def old_user_model(executor: MigrationExecutor) -> Any:  # a historical model class
    executor.loader.build_graph()
    return executor.loader.project_state(BEFORE).apps.get_model("accounts", "User")


def test_existing_superuser_becomes_the_superadmin(executor: MigrationExecutor) -> None:
    old_user_model(executor).objects.create(
        username="erkin", password=PASSWORD, is_staff=True, is_superuser=True
    )

    executor.loader.build_graph()
    executor.migrate(AFTER)

    user = User.objects.get(username="erkin")
    assert (user.role, user.center, user.must_change_password) == (Role.SUPERADMIN, None, False)


def test_other_existing_users_stop_the_migration(executor: MigrationExecutor) -> None:
    OldUser = old_user_model(executor)
    OldUser.objects.create(username="ali", password=PASSWORD)

    executor.loader.build_graph()
    with pytest.raises(RuntimeError, match="need a centre: ali"):
        executor.migrate(AFTER)

    OldUser.objects.filter(username="ali").delete()
