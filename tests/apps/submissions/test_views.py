"""The student's pages and the result page (docs/UI.md §6, SPEC §3.8): who sees what."""

from datetime import timedelta
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.submissions.journal import MINUS
from apps.submissions.models import Submission, SubmissionTestResult
from apps.system.models import Job
from apps.system.queue import enqueue_judge
from apps.tasks.models import Assignment
from judge.core.verdict import Verdict
from judge.env import REPO_ROOT
from tests.apps.world import World, make_task, zip_folder

pytestmark = pytest.mark.django_db
SUBMISSIONS = REPO_ROOT / "examples" / "dart-cart" / "submissions"


def as_(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def solution(folder: str = "ok") -> SimpleUploadedFile:
    return SimpleUploadedFile("cart.zip", zip_folder(SUBMISSIONS / folder))


def fresh(world: World) -> Any:
    Submission.objects.filter(student=world.a.student).delete()
    return world.a


def failed_on_hidden_test(world: World) -> Submission:
    """Centre a's submission: test 1 passed, the hidden test 2 failed."""
    submission = world.a.submission
    Submission.objects.filter(pk=submission.pk).update(
        verdict=Verdict.WRONG_ANSWER,
        tests_passed=1,
        failed_test_index=2,
        failed_test_name="Chegirma",
        internal_log="$ dart test\nSECRET-LOG-LINE\nverdict: wrong_answer\n",
    )
    SubmissionTestResult.objects.create(
        submission=submission, index=1, name="Savat boʻsh", visibility="public", status="pass"
    )
    SubmissionTestResult.objects.create(
        submission=submission,
        index=2,
        name="Chegirma",
        visibility="hidden",
        status="fail",
        message="Expected: <9000> SECRET-EXPECTED",
    )
    submission.refresh_from_db()
    return submission


class TestMyAssignments:
    def test_the_home_page_lists_the_open_assignments_by_group(
        self, client: Client, world: World
    ) -> None:
        a = world.a
        later, _ = make_task(a.teacher, "Hali ochilmagan")
        Assignment.objects.create(
            task=later, group=a.group, opens_at=timezone.now() + timedelta(days=1)
        )
        as_(client, a.student)

        page = client.get("/", follow=True).content.decode()

        assert "<h1>Topshiriqlarim</h1>" in page
        assert a.group.name in page
        assert f'href="/assignments/{a.assignment.pk}/"' in page
        assert "Qabul qilindi" in page  # the world's submission
        assert "Hali ochilmagan" not in page
        assert f'href="/assignments/{world.b.assignment.pk}/"' not in page

    def test_each_state_reads_in_words(self, client: Client, world: World) -> None:
        a = fresh(world)
        as_(client, a.student)

        assert "Yangi" in client.get("/assignments/").content.decode()

        Submission.objects.create(
            assignment=a.assignment,
            student=a.student,
            task_version=a.version,
            archive="x.zip",
            sha256="0" * 64,
            status=Submission.Status.FINISHED,
            verdict=Verdict.WRONG_ANSWER,
        )
        assert "Urinilgan: 1 ta" in client.get("/assignments/").content.decode()

    def test_without_assignments_the_empty_state_says_what_comes(
        self, client: Client, world: World
    ) -> None:
        as_(client, world.a.other_student)

        page = client.get("/assignments/").content.decode()

        assert "Hali topshiriq yoʻq." in page

    def test_only_students_have_this_page(self, client: Client, world: World) -> None:
        as_(client, world.a.teacher)

        assert client.get("/assignments/").status_code == 403


class TestAssignmentPage:
    def test_it_has_the_statement_the_starter_and_the_form(
        self, client: Client, world: World
    ) -> None:
        a = fresh(world)
        as_(client, a.student)

        page = client.get(f"/assignments/{a.assignment.pk}/").content.decode()

        assert "Savatdagi mahsulotlar narxini hisoblang." in page
        assert f"/assignments/{a.assignment.pk}/starter/" in page
        assert 'type="file"' in page
        assert "Yechimni yuborish" in page
        assert "Hali yechim yuborilmagan." in page

    def test_the_starter_downloads(self, client: Client, world: World) -> None:
        as_(client, world.a.student)

        response = client.get(f"/assignments/{world.a.assignment.pk}/starter/")

        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert "attachment" in response["Content-Disposition"]

    def test_a_good_zip_goes_to_the_result_page(self, client: Client, world: World) -> None:
        a = fresh(world)
        as_(client, a.student)

        response = client.post(f"/assignments/{a.assignment.pk}/", {"archive": solution()})

        submission = Submission.objects.get(student=a.student)
        assert response["Location"] == f"/submissions/{submission.pk}/"
        assert Job.objects.filter(submission=submission).exists()

    def test_a_forbidden_import_is_rejected_at_once(self, client: Client, world: World) -> None:
        a = fresh(world)
        as_(client, a.student)

        url = f"/assignments/{a.assignment.pk}/"
        response = client.post(url, {"archive": solution("forbidden_import")}, follow=True)

        page = response.content.decode()
        assert "Rad etildi" in page
        assert "Taqiqlangan import: dart:io" in page
        assert not Job.objects.filter(submission__student=a.student).exists()

    def test_a_zip_over_the_limit_is_refused_and_not_stored(
        self, client: Client, world: World, settings: Any
    ) -> None:
        from judge.packaging.zip_validator import ZipLimits

        settings.SUBMISSION_ZIP_LIMITS = ZipLimits(100, 10_000, 10)
        a = fresh(world)
        as_(client, a.student)

        response = client.post(f"/assignments/{a.assignment.pk}/", {"archive": solution()})

        assert response.status_code == 400
        assert "Zip hajmi juda katta" in response.content.decode()
        assert not Submission.objects.filter(student=a.student).exists()

    def test_when_attempts_are_gone_the_page_says_so(self, client: Client, world: World) -> None:
        a = world.a
        a.assignment.max_attempts = 1
        a.assignment.save()
        as_(client, a.student)

        page = client.get(f"/assignments/{a.assignment.pk}/").content.decode()
        response = client.post(f"/assignments/{a.assignment.pk}/", {"archive": solution()})

        assert "Urinishlar tugadi" in page
        assert 'type="file"' not in page
        assert response.status_code == 400
        assert Submission.objects.filter(student=a.student).count() == 1

    def test_during_the_cooldown_the_button_counts_down(self, client: Client, world: World) -> None:
        a = fresh(world)
        as_(client, a.student)
        client.post(f"/assignments/{a.assignment.pk}/", {"archive": solution()})
        Submission.objects.filter(student=a.student).update(
            status=Submission.Status.FINISHED, verdict=Verdict.WRONG_ANSWER
        )

        page = client.get(f"/assignments/{a.assignment.pk}/").content.decode()

        assert "data-cooldown=" in page
        assert "disabled" in page

    def test_a_closed_assignment_is_a_404(self, client: Client, world: World) -> None:
        a = world.a
        a.assignment.opens_at = timezone.now() + timedelta(days=1)
        a.assignment.deadline = None
        a.assignment.save()
        as_(client, a.student)

        assert client.get(f"/assignments/{a.assignment.pk}/").status_code == 404

    def test_a_classmate_in_another_group_cannot_open_it(
        self, client: Client, world: World
    ) -> None:
        as_(client, world.a.other_student)

        assert client.get(f"/assignments/{world.a.assignment.pk}/").status_code == 404


class TestResultPage:
    def test_the_student_sees_rows_and_the_stamp_but_no_hidden_message_or_log(
        self, client: Client, world: World
    ) -> None:
        submission = failed_on_hidden_test(world)
        as_(client, world.a.student)

        page = client.get(f"/submissions/{submission.pk}/").content.decode()

        assert "1. Savat boʻsh" in page
        assert "2. Chegirma" in page
        assert "2-testda xato" in page
        assert "Yashirin test: tafsiloti koʻrsatilmaydi." in page
        assert "SECRET-EXPECTED" not in page
        assert "SECRET-LOG-LINE" not in page
        assert "Urinish 1" in page

    def test_the_teacher_sees_the_message_the_log_and_the_code(
        self, client: Client, world: World
    ) -> None:
        submission = failed_on_hidden_test(world)
        submission.archive.save("s.zip", solution().file, save=True)
        as_(client, world.a.teacher)

        page = client.get(f"/submissions/{submission.pk}/").content.decode()

        assert "SECRET-EXPECTED" in page
        assert "SECRET-LOG-LINE" in page
        assert "lib/cart.dart" in page
        assert "class</span>" in page or 'class="k' in page  # highlighted
        assert "Qayta tekshirish" in page

    def test_the_manager_sees_the_code_but_no_hidden_message_or_log(
        self, client: Client, world: World
    ) -> None:
        submission = failed_on_hidden_test(world)
        submission.archive.save("s.zip", solution().file, save=True)
        as_(client, world.a.manager)

        page = client.get(f"/submissions/{submission.pk}/").content.decode()

        assert "lib/cart.dart" in page
        assert "SECRET-EXPECTED" not in page
        assert "SECRET-LOG-LINE" not in page
        assert "Qayta tekshirish" not in page

    def test_a_broken_zip_shows_why_instead_of_code(self, client: Client, world: World) -> None:
        as_(client, world.a.teacher)

        page = client.get(f"/submissions/{world.a.submission.pk}/").content.decode()

        assert "lib/ papkasi topilmadi" in page

    def test_queued_shows_the_place_in_line_and_keeps_polling(
        self, client: Client, world: World
    ) -> None:
        a, b = fresh(world), world.b
        enqueue_judge(b.submission)  # another centre's solution in the same lane
        as_(client, a.student)
        client.post(f"/assignments/{a.assignment.pk}/", {"archive": solution()})
        submission = Submission.objects.get(student=a.student)

        response = client.get(f"/submissions/{submission.pk}/live/")

        assert response.status_code == 200
        assert "Navbatda. Oldingizda 1 ta yechim." in response.content.decode()
        assert "hx-trigger" in response.content.decode()

    def test_a_running_solution_shows_the_test_being_written(
        self, client: Client, world: World
    ) -> None:
        submission = world.a.submission
        Submission.objects.filter(pk=submission.pk).update(
            status=Submission.Status.RUNNING, verdict=""
        )
        SubmissionTestResult.objects.create(
            submission=submission, index=1, name="Savat boʻsh", visibility="public", status="pass"
        )
        as_(client, world.a.student)

        page = client.get(f"/submissions/{submission.pk}/live/").content.decode()

        assert "2. Chegirma" in page
        assert "yozilmoqda" in page

    def test_only_new_rows_play_the_appear_animation(self, client: Client, world: World) -> None:
        """The poll redraws the page every second: rows already shown must not flash again."""
        submission = world.a.submission
        Submission.objects.filter(pk=submission.pk).update(
            status=Submission.Status.RUNNING, verdict=""
        )
        for index, name in ((1, "Savat boʻsh"), (2, "Chegirma")):
            SubmissionTestResult.objects.create(
                submission=submission, index=index, name=name, visibility="public", status="pass"
            )
        as_(client, world.a.student)

        polled = client.get(f"/submissions/{submission.pk}/live/?seen=1").content.decode()
        opened = client.get(f"/submissions/{submission.pk}/").content.decode()

        assert polled.count("row-appear") == 1
        assert "seen=2" in polled
        assert opened.count("row-appear") == 0

    def test_a_finished_solution_stops_the_polling(self, client: Client, world: World) -> None:
        as_(client, world.a.student)

        response = client.get(f"/submissions/{world.a.submission.pk}/live/")

        assert response.status_code == 286
        assert "hx-trigger" not in response.content.decode()
        assert "Qabul qilindi" in response.content.decode()

    def test_a_compile_error_shows_the_students_message(self, client: Client, world: World) -> None:
        submission = world.a.submission
        Submission.objects.filter(pk=submission.pk).update(
            verdict=Verdict.COMPILE_ERROR,
            public_message="Kodingiz topshiriqdagi interfeysga mos emas: total",
        )
        as_(client, world.a.student)

        page = client.get(f"/submissions/{submission.pk}/").content.decode()

        assert "Kompilyatsiya xatosi" in page
        assert "interfeysga mos emas" in page

    def test_another_student_cannot_see_it(self, client: Client, world: World) -> None:
        as_(client, world.a.other_student)

        assert client.get(f"/submissions/{world.a.submission.pk}/").status_code == 404


class TestRejudge:
    def test_the_teacher_sends_it_back_to_the_queue(self, client: Client, world: World) -> None:
        submission = failed_on_hidden_test(world)
        as_(client, world.a.teacher)

        response = client.post(f"/submissions/{submission.pk}/rejudge/")

        submission.refresh_from_db()
        assert response["Location"] == f"/submissions/{submission.pk}/"
        assert (submission.status, submission.verdict) == ("queued", "")
        assert not submission.results.exists()
        job = Job.objects.get(submission=submission)
        assert (job.kind, job.priority) == (Job.Kind.REJUDGE, Job.Priority.REJUDGE)

    def test_a_rejected_solution_is_not_judged_again(self, client: Client, world: World) -> None:
        submission = world.a.submission
        Submission.objects.filter(pk=submission.pk).update(verdict=Verdict.REJECTED)
        as_(client, world.a.teacher)

        client.post(f"/submissions/{submission.pk}/rejudge/")

        assert not Job.objects.filter(submission=submission).exists()

    @pytest.mark.parametrize("who", ["manager", "admin", "student"])
    def test_only_the_teacher_may(self, client: Client, world: World, who: str) -> None:
        as_(client, getattr(world.a, who))

        response = client.post(f"/submissions/{world.a.submission.pk}/rejudge/")

        assert response.status_code == 403
        assert not Job.objects.exists()


class TestJournal:
    def test_the_teacher_sees_marks_and_opens_the_solutions(
        self, client: Client, world: World
    ) -> None:
        a = world.a
        as_(client, a.teacher)

        page = client.get(f"/groups/{a.group.pk}/journal/").content.decode()

        assert '<abbr title="Savat hisobi">A</abbr>' in page
        assert a.student.display_name in page
        assert f'href="/submissions/{a.submission.pk}/"' in page
        assert 'class="cell-pass"' in page

    @pytest.mark.parametrize("who", ["admin", "manager"])
    def test_the_centre_watches_it_too(self, client: Client, world: World, who: str) -> None:
        as_(client, getattr(world.a, who))

        assert client.get(f"/groups/{world.a.group.pk}/journal/").status_code == 200

    def test_another_teachers_group_is_a_404(self, client: Client, world: World) -> None:
        as_(client, world.a.other_teacher)

        assert client.get(f"/groups/{world.a.group.pk}/journal/").status_code == 404

    def test_students_see_it_only_when_the_group_shows_it(
        self, client: Client, world: World
    ) -> None:
        a = world.a
        classmate = User.objects.create_user(
            username="a-classmate", role="student", center=a.center, last_name="Zokirov"
        )
        a.group.add_students([classmate])
        Submission.objects.create(
            assignment=a.assignment,
            student=classmate,
            task_version=a.version,
            archive="x.zip",
            sha256="0" * 64,
            status=Submission.Status.FINISHED,
            verdict=Verdict.WRONG_ANSWER,
        )
        as_(client, a.student)
        url = f"/groups/{a.group.pk}/journal/"

        assert client.get(url).status_code == 404
        assert "Guruh jurnali" not in client.get("/assignments/").content.decode()

        a.group.show_journal_to_students = True
        a.group.save()
        page = client.get(url).content.decode()

        assert "Guruh jurnali" in client.get("/assignments/").content.decode()
        assert "Zokirov" in page
        assert f"{MINUS}1" in page  # the classmate's mark is shown...
        assert f'href="/submissions/{a.submission.pk}/"' in page  # ...own cells open
        classmate_submission = Submission.objects.get(student=classmate)
        assert f"/submissions/{classmate_submission.pk}/" not in page  # theirs don't

    def test_staff_see_every_attempt_on_the_result_page(self, client: Client, world: World) -> None:
        a = world.a
        older = Submission.objects.create(
            assignment=a.assignment,
            student=a.student,
            task_version=a.version,
            archive="x.zip",
            sha256="0" * 64,
            status=Submission.Status.FINISHED,
            verdict=Verdict.WRONG_ANSWER,
            failed_test_index=2,
        )
        as_(client, a.teacher)

        page = client.get(f"/submissions/{a.submission.pk}/").content.decode()

        assert f'href="/submissions/{older.pk}/"' in page
        assert "2-testda xato" in page
        assert "shu yechim" in page
