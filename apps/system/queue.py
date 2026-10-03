"""Putting work on the queue. The site only adds rows; the worker takes them
(apps.system.worker), so the site never needs Docker."""

from apps.submissions.models import Submission
from apps.system.models import Job
from apps.tasks.models import TaskVersion


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
