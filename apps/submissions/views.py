"""The student's pages (docs/UI.md §6): my assignments, an assignment with its upload form,
and the live result. Staff open the same result page with the code, and the teacher can
judge it again.

Every page checks the role first (require: 403), then reaches objects only through
get_for_user_or_404, so another centre's assignment or submission is a 404.
"""

from collections import defaultdict
from dataclasses import dataclass

from django.contrib import messages
from django.db.models import F
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.models import Group, Role, User
from apps.accounts.permissions import Action, can
from apps.accounts.views._guard import require
from apps.submissions.code import student_code
from apps.submissions.forms import SubmitForm
from apps.submissions.journal import build_rows, column_letter
from apps.submissions.models import Submission, SubmissionTestResult
from apps.submissions.services import ACTIVE, SubmitRefused, rejudge, submit, submit_state
from apps.system.models import Job
from apps.system.queue import queue_position
from apps.tasks.files import private_download
from apps.tasks.markdown import render_markdown
from apps.tasks.models import Assignment
from apps.tasks.views import STOP_POLLING
from judge.core.manifest import Visibility
from judge.core.verdict import Verdict


@dataclass(frozen=True)
class AssignmentRow:
    assignment: Assignment
    state: str  # new, active, tried, accepted
    attempts: int


def my_assignments(request: HttpRequest) -> HttpResponse:
    require(request, Action.SUBMIT)
    assignments = (
        visible_to(Assignment, request.user)
        .select_related("task", "group")
        .order_by("group__name", F("deadline").asc(nulls_last=True), "-opens_at")
    )
    mine = Submission.objects.filter(student=request.user, assignment__in=assignments)
    states: dict[int, list[Submission]] = defaultdict(list)
    for submission in mine.only("assignment_id", "status", "verdict"):
        states[submission.assignment_id].append(submission)
    groups: dict[Group, list[AssignmentRow]] = defaultdict(list)
    for assignment in assignments:
        submissions = states[assignment.pk]
        groups[assignment.group].append(
            AssignmentRow(assignment, _state(submissions), _attempts(submissions))
        )
    return render(request, "submissions/my_assignments.html", {"groups": dict(groups)})


def _state(submissions: list[Submission]) -> str:
    if any(s.verdict == Verdict.ACCEPTED for s in submissions):
        return "accepted"
    if any(s.status in ACTIVE for s in submissions):
        return "active"
    return "tried" if _attempts(submissions) else "new"


def _attempts(submissions: list[Submission]) -> int:
    return sum(
        1
        for s in submissions
        if s.status in ACTIVE or (s.verdict and Verdict(s.verdict).counts_as_attempt)
    )


def assignment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.SUBMIT)
    assignment = get_for_user_or_404(Assignment, request.user, pk=pk)
    task = assignment.task
    profile = task.profile.judge_profile()
    form = SubmitForm(
        request.POST or None, request.FILES or None, student_paths=profile.student_paths
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                submission = submit(assignment, request.user, form.cleaned_data["archive"])
            except SubmitRefused as error:
                form.add_error(None, str(error))
            else:
                return redirect("submissions:submission", submission.pk)
        status = 400
    history = (
        Submission.objects.filter(assignment=assignment, student=request.user)
        .select_related("task_version")
        .order_by("-created_at")
    )
    return render(
        request,
        "submissions/assignment_detail.html",
        {
            "assignment": assignment,
            "task": task,
            "version": task.published_version,
            "statement": render_markdown(task.statement_md),
            "form": form,
            "state": submit_state(assignment, request.user),
            "history": history,
        },
        status=status,
    )


def assignment_starter(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.SUBMIT)
    assignment = get_for_user_or_404(Assignment, request.user, pk=pk)
    version = assignment.task.published_version
    if version is None:
        raise Http404
    return private_download(version.starter, f"topshiriq-{assignment.task_id}-starter.zip")


def submission_detail(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.VIEW_CODE)
    submission = _submission(request, pk)
    context = _live_context(request.user, submission, seen=submission.results.count())
    is_student = request.user.pk == submission.student_id
    if not is_student:
        files, code_problem = student_code(submission)
        context |= {
            "files": files,
            "code_problem": code_problem,
            "attempts": visible_to(Submission, request.user)
            .filter(assignment_id=submission.assignment_id, student_id=submission.student_id)
            .order_by("-created_at"),
            "show_log": can(request.user, Action.VIEW_FULL_LOG),
            "can_rejudge": can(request.user, Action.MANAGE_TASKS),
        }
    context["is_student"] = is_student
    return render(request, "submissions/submission_detail.html", context)


def submission_live(request: HttpRequest, pk: int) -> HttpResponse:
    """The part of the result page that changes while the solution is judged (every 1 s)."""
    require(request, Action.VIEW_CODE)
    submission = _submission(request, pk)
    seen = request.GET.get("seen", "")
    context = _live_context(request.user, submission, seen=int(seen) if seen.isdigit() else 0)
    response = render(request, "submissions/_live.html", context)
    if submission.is_finished:
        response.status_code = STOP_POLLING
    return response


@require_POST
def submission_rejudge(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    submission = _submission(request, pk)
    try:
        rejudge(submission)
    except SubmitRefused as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Yechim qayta tekshirish navbatiga qoʻyildi.")
    return redirect("submissions:submission", submission.pk)


def journal(request: HttpRequest, pk: int) -> HttpResponse:
    """The group's results, acmp style (docs/UI.md §4). Students see it only where the
    group shows it, and open only their own solutions from it."""
    require(request, Action.VIEW_JOURNAL)
    group = get_for_user_or_404(Group, request.user, pk=pk)
    is_student = request.user.role == Role.STUDENT
    if is_student and not group.show_journal_to_students:
        raise Http404
    assignments = list(
        visible_to(Assignment, request.user)
        .filter(group=group)
        .select_related("task")
        .order_by("opens_at", "pk")
    )
    students = list(group.students.order_by("last_name", "first_name", "username"))
    submissions = Submission.objects.filter(assignment__in=assignments, student__in=students).only(
        "pk", "student_id", "assignment_id", "status", "verdict", "is_late", "created_at"
    )
    rows = build_rows(students, [a.pk for a in assignments], submissions)
    return render(
        request,
        "submissions/journal.html",
        {
            "group": group,
            "columns": [(column_letter(i), a) for i, a in enumerate(assignments)],
            # (row, whether its cells link to the solutions): a student opens only their own.
            "rows": [(row, not is_student or row.student.pk == request.user.pk) for row in rows],
            "is_student": is_student,
        },
    )


def _submission(request: HttpRequest, pk: int) -> Submission:
    return get_for_user_or_404(Submission, request.user, pk=pk)


@dataclass(frozen=True)
class ResultRow:
    index: int
    name: str
    passed: bool
    duration_ms: int | None
    note: str  # what this viewer may read under the row
    hidden_note: bool  # a hidden test failed and its message is not for this viewer


def _live_context(viewer: User, submission: Submission, seen: int) -> dict[str, object]:
    """``seen``: how many rows the page already shows. The poll redraws the whole notebook
    each second; only rows after these play the appear animation, the rest stay still."""
    # Hidden tests' messages quote the hidden tests: only those who may read the full log.
    sees_hidden = can(viewer, Action.VIEW_FULL_LOG)
    results = list(submission.results.all())
    rows = [_row(result, sees_hidden) for result in results]
    tests = (submission.task_version.manifest or {}).get("tests", [])
    running = ""
    if submission.status == Submission.Status.RUNNING and len(results) < len(tests):
        running = f"{len(results) + 1}. {tests[len(results)]['name']}"
    ahead = None
    if submission.status == Submission.Status.QUEUED:
        job = Job.objects.filter(submission=submission).order_by("-created_at").first()
        ahead = queue_position(job) if job is not None else 0
    return {
        "submission": submission,
        "assignment": submission.assignment,
        "rows": rows,
        "seen": seen,
        "running": running,
        "ahead": ahead,
        "attempt": _attempt_number(submission),
        "stopped_at": submission.failed_test_index
        if submission.verdict in (Verdict.TIME_LIMIT, Verdict.MEMORY_LIMIT)
        else None,
    }


def _row(result: SubmissionTestResult, sees_hidden: bool) -> ResultRow:
    failed = result.status == SubmissionTestResult.Status.FAIL
    may_read = result.visibility == Visibility.PUBLIC or sees_hidden
    return ResultRow(
        index=result.index,
        name=result.name,
        passed=not failed,
        duration_ms=result.duration_ms,
        note=result.message if failed and may_read else "",
        hidden_note=failed and not may_read,
    )


def _attempt_number(submission: Submission) -> int | None:
    """ "Urinish 3": rejected and system error solutions are not attempts."""
    if submission.verdict and not Verdict(submission.verdict).counts_as_attempt:
        return None
    return (
        Submission.objects.filter(
            assignment_id=submission.assignment_id,
            student_id=submission.student_id,
            created_at__lte=submission.created_at,
        )
        .counting()
        .count()
    )
