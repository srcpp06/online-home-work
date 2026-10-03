"""Who sees which submissions and results (SPEC §1, §3.8)."""

import pytest

from apps.accounts.access import visible_to
from apps.submissions.models import Submission, SubmissionTestResult
from judge.core.verdict import Verdict
from tests.apps.world import World

pytestmark = pytest.mark.django_db


def test_each_role_sees_its_submissions(world: World) -> None:
    a, b = world.a, world.b

    assert set(visible_to(Submission, a.student)) == {a.submission}
    assert not visible_to(Submission, a.other_student).exists()
    assert set(visible_to(Submission, a.teacher)) == {a.submission}
    assert not visible_to(Submission, a.other_teacher).exists()
    assert not visible_to(Submission, a.admin).exists()
    assert set(visible_to(Submission, a.manager)) == {a.submission}
    assert set(visible_to(Submission, world.superadmin)) == {a.submission, b.submission}


def test_results_follow_their_submission(world: World) -> None:
    result = SubmissionTestResult.objects.create(
        submission=world.a.submission, index=1, name="Savat", visibility="public", status="pass"
    )

    assert set(visible_to(SubmissionTestResult, world.a.student)) == {result}
    assert not visible_to(SubmissionTestResult, world.b.student).exists()


@pytest.mark.parametrize(
    ("verdict", "counts"),
    [
        (Verdict.ACCEPTED, True),
        (Verdict.WRONG_ANSWER, True),
        (Verdict.REJECTED, False),
        (Verdict.SYSTEM_ERROR, False),
        ("", True),  # still being judged: it will count
    ],
)
def test_attempts_leave_out_rejections_and_system_errors(
    world: World, verdict: str, counts: bool
) -> None:
    Submission.objects.filter(pk=world.a.submission.pk).update(verdict=verdict)

    assert Submission.objects.counting().filter(pk=world.a.submission.pk).exists() is counts
