"""Sending a solution (SPEC §3.4, §3.9): deadline, attempts, cooldown, one at a time, and
the static check that rejects a zip on the spot."""

from datetime import timedelta
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.submissions.models import Submission
from apps.submissions.services import SubmitRefused, submit, submit_state
from apps.system.models import Job
from judge.core.verdict import Verdict
from judge.env import REPO_ROOT
from tests.apps.world import World, zip_folder

pytestmark = pytest.mark.django_db

SUBMISSIONS = REPO_ROOT / "examples" / "dart-cart" / "submissions"


def upload(folder: str = "ok") -> SimpleUploadedFile:
    return SimpleUploadedFile("yechim.zip", zip_folder(SUBMISSIONS / folder))


def fresh(world: World) -> Any:
    """Centre a's student with no submissions yet."""
    Submission.objects.filter(student=world.a.student).delete()
    return world.a


def test_a_good_zip_is_stored_and_queued(world: World) -> None:
    a = fresh(world)

    submission = submit(a.assignment, a.student, upload())

    assert submission.status == Submission.Status.QUEUED
    assert submission.task_version == a.version
    assert len(submission.sha256) == 64
    assert submission.archive.name.endswith(".zip")
    assert "yechim" not in submission.archive.name  # the student's file name never reaches disk
    job = Job.objects.get(submission=submission)
    assert (job.kind, job.status) == (Job.Kind.JUDGE, Job.Status.QUEUED)


@pytest.mark.parametrize(
    ("folder", "says"),
    [
        ("forbidden_import", "Taqiqlangan import: dart:io"),
        ("../task/test", "lib/ papkasi topilmadi"),
    ],
)
def test_a_bad_zip_is_rejected_at_once_and_never_queued(
    world: World, folder: str, says: str
) -> None:
    a = fresh(world)

    submission = submit(a.assignment, a.student, upload(folder))

    assert (submission.status, submission.verdict) == ("finished", Verdict.REJECTED)
    assert says in submission.public_message
    assert submission.finished_at is not None
    assert not Job.objects.filter(submission=submission).exists()


def test_a_file_that_is_not_a_zip_is_rejected(world: World) -> None:
    a = fresh(world)

    submission = submit(a.assignment, a.student, SimpleUploadedFile("x.zip", b"not a zip"))

    assert submission.verdict == Verdict.REJECTED


def test_rejected_solutions_cost_no_attempt_and_no_wait(world: World) -> None:
    a = fresh(world)
    a.assignment.max_attempts = 1
    a.assignment.save()

    submit(a.assignment, a.student, upload("forbidden_import"))
    state = submit_state(a.assignment, a.student)

    assert state.can_submit
    assert (state.attempts_used, state.attempts_left, state.wait_s) == (0, 1, 0)


def test_one_solution_at_a_time(world: World, settings: Any) -> None:
    settings.SUBMISSION_COOLDOWN_S = 1
    a = fresh(world)
    submit(a.assignment, a.student, upload())

    with pytest.raises(SubmitRefused, match="hali tekshirilmoqda"):
        submit(a.assignment, a.student, upload())


def test_the_cooldown_counts_down(world: World) -> None:
    a = fresh(world)
    first = submit(a.assignment, a.student, upload())
    Submission.objects.filter(pk=first.pk).update(
        status=Submission.Status.FINISHED, verdict=Verdict.WRONG_ANSWER
    )

    state = submit_state(a.assignment, a.student, now=first.created_at + timedelta(seconds=15))

    assert state.wait_s == 45
    assert state.refusal == "Keyingi yechimni 45 soniyadan keyin yuborish mumkin."
    later = submit_state(a.assignment, a.student, now=first.created_at + timedelta(seconds=61))
    assert later.can_submit


def test_attempts_run_out(world: World) -> None:
    a = world.a  # already has one accepted submission
    a.assignment.max_attempts = 1
    a.assignment.save()

    state = submit_state(a.assignment, a.student)

    assert (state.attempts_used, state.attempts_left) == (1, 0)
    assert state.refusal == "Urinishlar tugadi: 1 ta urinishning hammasi ishlatildi."
    with pytest.raises(SubmitRefused, match="Urinishlar tugadi"):
        submit(a.assignment, a.student, upload())


def test_after_the_deadline_only_with_late_allowed(world: World) -> None:
    a = fresh(world)
    a.assignment.opens_at = timezone.now() - timedelta(days=2)
    a.assignment.deadline = timezone.now() - timedelta(days=1)
    a.assignment.save()

    with pytest.raises(SubmitRefused, match="Muddat tugagan"):
        submit(a.assignment, a.student, upload())

    a.assignment.allow_late = True
    a.assignment.save()
    assert submit(a.assignment, a.student, upload()).is_late


def test_a_solution_in_time_is_not_late(world: World) -> None:
    a = fresh(world)

    assert not submit(a.assignment, a.student, upload()).is_late


def test_the_published_version_is_judged(world: World) -> None:
    """A version published after the student opened the page is the one used."""
    a = fresh(world)
    newer = a.version
    newer.pk = None
    newer.number = 2
    newer.save()
    a.task.published_version = newer
    a.task.save()

    assert submit(a.assignment, a.student, upload()).task_version == newer


def test_zip_contents_are_read_from_the_start(world: World) -> None:
    """The form reads the upload to check its size; the service must not see it empty."""
    a = fresh(world)
    file = upload()
    file.read()

    assert submit(a.assignment, a.student, file).status == Submission.Status.QUEUED
