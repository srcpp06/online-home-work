"""The queue table (SPEC §3.9): order, SKIP LOCKED, leases, retries and giving up."""

import threading
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.submissions.models import Submission
from apps.system import queue
from apps.system.models import Job
from apps.tasks.models import TaskVersion
from judge.core.verdict import Verdict
from tests.apps.world import World

pytestmark = pytest.mark.django_db
LEASE_S = 60


def test_builds_go_first_then_the_oldest(world: World) -> None:
    first_judge = queue.enqueue_judge(world.a.submission)
    second_judge = queue.enqueue_judge(world.b.submission)
    build = queue.enqueue_build(world.a.version)

    taken = [queue.claim(["fast"], "node-1", LEASE_S) for _ in range(3)]

    assert taken == [build, first_judge, second_judge]
    assert queue.claim(["fast"], "node-1", LEASE_S) is None


def test_a_lane_takes_only_its_jobs(world: World) -> None:
    queue.enqueue_judge(world.a.submission)  # dart: the fast lane

    assert queue.claim(["heavy"], "node-1", LEASE_S) is None
    assert queue.claim(["fast"], "node-1", LEASE_S) is not None


def test_lanes_are_tried_in_order(world: World) -> None:
    """A heavy slot takes heavy jobs first and fast ones when no heavy job waits (SPEC §3.9)."""
    fast = queue.enqueue_judge(world.a.submission)
    heavy = Job.objects.create(
        kind=Job.Kind.JUDGE,
        lane="heavy",
        priority=Job.Priority.JUDGE,
        submission=world.b.submission,
    )

    taken = [queue.claim(["heavy", "fast"], "node-1", LEASE_S) for _ in range(3)]

    assert taken == [heavy, fast, None]


def test_claiming_marks_the_job_as_this_workers(world: World) -> None:
    queue.enqueue_judge(world.a.submission)

    job = queue.claim(["fast"], "node-7", LEASE_S)

    assert job is not None
    job.refresh_from_db()
    assert (job.status, job.attempts, job.worker_node) == ("running", 1, "node-7")
    assert job.lease_expires_at > timezone.now() + timedelta(seconds=LEASE_S - 5)


@pytest.mark.django_db(transaction=True)
def test_a_job_another_worker_is_taking_is_skipped(world: World) -> None:
    first = queue.enqueue_judge(world.a.submission)
    second = queue.enqueue_judge(world.b.submission)
    locked, release = threading.Event(), threading.Event()

    def other_worker() -> None:
        with transaction.atomic():
            Job.objects.select_for_update().get(pk=first.pk)
            locked.set()
            release.wait(10)
        connection.close()

    thread = threading.Thread(target=other_worker)
    thread.start()
    try:
        assert locked.wait(10)
        taken = queue.claim(["fast"], "node-1", LEASE_S)  # does not wait for the lock
    finally:
        release.set()
        thread.join()

    assert taken == second


def test_queue_position_counts_who_goes_first(world: World) -> None:
    queue.enqueue_build(world.a.version)
    mine = queue.enqueue_judge(world.a.submission)
    later = queue.enqueue_judge(world.b.submission)

    assert queue.queue_position(mine) == 1
    assert queue.queue_position(later) == 2


class TestFailures:
    def test_a_failed_job_goes_back_to_the_queue(self, world: World) -> None:
        queue.enqueue_judge(world.a.submission)
        job = queue.claim(["fast"], "node-1", LEASE_S)

        queue.fail(job, "boom")

        job.refresh_from_db()
        assert (job.status, job.last_error, job.worker_node) == ("queued", "boom", "")

    def test_after_the_last_attempt_the_student_gets_a_system_error(self, world: World) -> None:
        Submission.objects.filter(pk=world.a.submission.pk).update(status="running", verdict="")
        queue.enqueue_judge(world.a.submission)
        for _ in range(queue.MAX_ATTEMPTS):
            job = queue.claim(["fast"], "node-1", LEASE_S)
            queue.fail(job, "boom")

        job.refresh_from_db()
        submission = Submission.objects.get(pk=world.a.submission.pk)
        assert job.status == "failed"
        assert (submission.status, submission.verdict) == ("finished", Verdict.SYSTEM_ERROR)
        assert "hisoblanmaydi" in submission.public_message
        assert not Submission.objects.counting().filter(pk=submission.pk).exists()

    def test_a_build_that_keeps_failing_is_marked_failed(self, world: World) -> None:
        TaskVersion.objects.filter(pk=world.a.version.pk).update(status="building")
        queue.enqueue_build(world.a.version)
        for _ in range(queue.MAX_ATTEMPTS):
            queue.fail(queue.claim(["fast"], "node-1", LEASE_S), "boom")

        version = TaskVersion.objects.get(pk=world.a.version.pk)
        assert version.status == "build_failed"
        assert "Tizim xatosi" in version.build_errors[0]

    def test_the_reaper_returns_jobs_of_dead_workers(self, world: World) -> None:
        queue.enqueue_judge(world.a.submission)
        job = queue.claim(["fast"], "node-1", LEASE_S)
        Job.objects.filter(pk=job.pk).update(lease_expires_at=timezone.now() - timedelta(seconds=1))

        assert queue.reap() == 1

        job.refresh_from_db()
        assert job.status == "queued"
        assert "lease expired on node-1" in job.last_error
        assert not queue.extend_lease(job, LEASE_S)  # the old worker learns it lost the job

    def test_a_live_lease_is_left_alone(self, world: World) -> None:
        queue.enqueue_judge(world.a.submission)
        job = queue.claim(["fast"], "node-1", LEASE_S)

        assert queue.reap() == 0
        assert queue.extend_lease(job, LEASE_S)
