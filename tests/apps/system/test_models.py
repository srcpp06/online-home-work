"""The queue tables: only the superadmin sees them; a job always matches its kind."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.access import visible_to
from apps.system.models import Job, WorkerNode
from tests.apps.world import World

pytestmark = pytest.mark.django_db


def test_only_the_superadmin_sees_the_queue(world: World) -> None:
    Job.objects.create(kind="build", lane="fast", priority=0, task_version=world.a.version)
    WorkerNode.objects.create(
        name="node-1", arch="aarch64", started_at=timezone.now(), last_heartbeat=timezone.now()
    )

    for model in (Job, WorkerNode):
        assert visible_to(model, world.superadmin).count() == 1
        for user in (world.a.admin, world.a.manager, world.a.teacher, world.a.student):
            assert not visible_to(model, user).exists()


@pytest.mark.parametrize(
    "target",
    [
        {"kind": "build", "submission": "a.submission"},
        {"kind": "judge", "task_version": "a.version"},
        {"kind": "rejudge"},
    ],
)
def test_a_job_points_at_what_its_kind_needs(world: World, target: dict[str, str]) -> None:
    fields = {
        name: world.a.submission if value == "a.submission" else world.a.version
        for name, value in target.items()
        if name != "kind"
    }

    with pytest.raises(IntegrityError, match="target_matches_kind"), transaction.atomic():
        Job.objects.create(kind=target["kind"], lane="fast", priority=0, **fields)
