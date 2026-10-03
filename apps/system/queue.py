"""The job queue (SPEC §3.9): the site adds rows, workers take them.

Only database work here, so the site can enqueue without Docker; the worker loop that
runs the jobs is judge.adapters.worker.
"""

from collections.abc import Sequence
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.submissions.models import Submission
from apps.system.models import Job
from apps.tasks.models import TaskVersion
from judge.core.verdict import Verdict


def enqueue_build(version: TaskVersion) -> Job:
    return Job.objects.create(
        kind=Job.Kind.BUILD,
        lane=version.task.profile.lane,
        priority=Job.Priority.BUILD,
        task_version=version,
    )


def enqueue_judge(submission: Submission, *, rejudge: bool = False) -> Job:
    return Job.objects.create(
        kind=Job.Kind.REJUDGE if rejudge else Job.Kind.JUDGE,
        lane=submission.task_version.task.profile.lane,
        priority=Job.Priority.REJUDGE if rejudge else Job.Priority.JUDGE,
        submission=submission,
    )


def queue_position(job: Job) -> int:
    """How many jobs of the same lane go first; 0 when it is next or already running."""
    if job.status != Job.Status.QUEUED:
        return 0
    return (
        Job.objects.filter(lane=job.lane, status=Job.Status.QUEUED)
        .filter(priority__lte=job.priority)
        .exclude(pk=job.pk)
        .exclude(priority=job.priority, created_at__gt=job.created_at)
        .count()
    )


# A job is tried this many times: a worker that dies mid-job gives it back through the
# reaper, a crash in the job itself retries it. After that the submission gets
# system_error (the student is not charged an attempt) and a build is marked failed.
MAX_ATTEMPTS = 3
SYSTEM_ERROR_MESSAGE = "Tizim xatosi: yechim tekshirilmadi. Bu urinish hisoblanmaydi."


def claim(lanes: Sequence[str], node: str, lease_s: int) -> Job | None:
    """Take the next queued job of the first lane that has one, or None.

    A heavy slot passes ["heavy", "fast"]: heavy jobs first, and fast ones when none waits,
    so a quick check never idles behind an empty heavy slot (SPEC §3.9).
    SKIP LOCKED: a row another worker is taking right now is skipped, not waited for, so
    workers never block each other and never take the same job.
    """
    for lane in lanes:
        job = _claim_lane(lane, node, lease_s)
        if job is not None:
            return job
    return None


def _claim_lane(lane: str, node: str, lease_s: int) -> Job | None:
    now = timezone.now()
    with transaction.atomic():
        job = (
            Job.objects.select_for_update(skip_locked=True)
            .filter(status=Job.Status.QUEUED, lane=lane)
            .order_by("priority", "created_at", "pk")
            .first()
        )
        if job is None:
            return None
        job.status = Job.Status.RUNNING
        job.attempts += 1
        job.worker_node = node
        job.started_at = now
        job.lease_expires_at = now + timedelta(seconds=lease_s)
        job.save(
            update_fields=["status", "attempts", "worker_node", "started_at", "lease_expires_at"]
        )
    return job


def extend_lease(job: Job, lease_s: int) -> bool:
    """The worker's heartbeat; False if the job is no longer this worker's (reaped)."""
    updated = Job.objects.filter(
        pk=job.pk, status=Job.Status.RUNNING, worker_node=job.worker_node
    ).update(lease_expires_at=timezone.now() + timedelta(seconds=lease_s))
    return updated == 1


def finish(job: Job) -> None:
    Job.objects.filter(pk=job.pk).update(
        status=Job.Status.DONE, finished_at=timezone.now(), lease_expires_at=None
    )


def fail(job: Job, error: str) -> None:
    """A job that raised: back to the queue while attempts remain, else given up."""
    job.refresh_from_db()
    if job.attempts < MAX_ATTEMPTS:
        Job.objects.filter(pk=job.pk).update(
            status=Job.Status.QUEUED, last_error=error, lease_expires_at=None, worker_node=""
        )
        return
    _give_up(job, error)


def reap() -> int:
    """Return the jobs of workers that stopped heartbeating (crashed, killed, lost)."""
    count = 0
    expired = Job.objects.filter(status=Job.Status.RUNNING, lease_expires_at__lt=timezone.now())
    for job in expired:
        fail(job, f"lease expired on {job.worker_node or 'an unknown worker'}")
        count += 1
    return count


def _give_up(job: Job, error: str) -> None:
    now = timezone.now()
    with transaction.atomic():
        Job.objects.filter(pk=job.pk).update(
            status=Job.Status.FAILED, last_error=error, finished_at=now, lease_expires_at=None
        )
        if job.submission_id is not None:
            Submission.objects.filter(pk=job.submission_id).update(
                status=Submission.Status.FINISHED,
                verdict=Verdict.SYSTEM_ERROR,
                public_message=SYSTEM_ERROR_MESSAGE,
                finished_at=now,
            )
        if job.task_version_id is not None:
            TaskVersion.objects.filter(pk=job.task_version_id).update(
                status=TaskVersion.Status.BUILD_FAILED,
                build_errors=["Tizim xatosi: image yigʻilmadi. Paketni qayta yuklang."],
                built_at=now,
            )
