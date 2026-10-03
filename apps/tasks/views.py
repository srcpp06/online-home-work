"""Teacher pages: create a task, follow its build, publish it, give it to groups
(docs/UI.md §6). Centre admins, managers and the superadmin look without changing.

Every page checks the role (require: 403 before any lookup), then reaches objects only
through get_for_user_or_404, so another centre's task is a 404.
"""

import hashlib

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.permissions import Action, can
from apps.accounts.views._guard import require
from apps.system.queue import enqueue_build
from apps.tasks.files import private_download
from apps.tasks.forms import AssignmentForm, PublishForm, TaskForm, VersionForm
from apps.tasks.markdown import render_markdown
from apps.tasks.models import Assignment, Task, TaskVersion
from judge.packaging.starter import starter_zip

# HTMX stops polling when a response has this status (CLAUDE.md, "Jonli natija").
STOP_POLLING = 286


def task_list(request: HttpRequest) -> HttpResponse:
    require(request, Action.VIEW_TASKS)
    tasks = (
        visible_to(Task, request.user)
        .select_related("profile", "author", "published_version")
        .annotate(assignment_count=Count("assignments"))
        .order_by("is_archived", "-created_at")
    )
    return render(
        request,
        "tasks/task_list.html",
        {"tasks": tasks, "can_manage": can(request.user, Action.MANAGE_TASKS)},
    )


def task_create(request: HttpRequest) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    teacher = request.user
    task = Task(center=teacher.center, author=teacher)
    form = TaskForm(
        request.POST or None, request.FILES or None, instance=task, teacher=teacher, creating=True
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            task = form.save()
            version = _save_version(task, form)
        return redirect("tasks:version", task.pk, version.number)
    return render(request, "tasks/task_form.html", {"form": form, "creating": True})


def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.VIEW_TASKS)
    task = get_for_user_or_404(Task, request.user, pk=pk)
    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "statement": render_markdown(task.statement_md),
            "versions": task.versions.order_by("-number"),
            "assignments": visible_to(Assignment, request.user)
            .filter(task=task)
            .select_related("group")
            .order_by("group__name"),
            "can_manage": can(request.user, Action.MANAGE_TASKS),
        },
    )


def task_edit(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    task = get_for_user_or_404(Task, request.user, pk=pk)
    form = TaskForm(request.POST or None, instance=task, teacher=request.user, creating=False)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oʻzgarishlar saqlandi.")
        return redirect("tasks:task", task.pk)
    return render(request, "tasks/task_form.html", {"form": form, "task": task, "creating": False})


@require_POST
def task_archive(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    task = get_for_user_or_404(Task, request.user, pk=pk)
    task.is_archived = not task.is_archived
    task.save(update_fields=["is_archived", "updated_at"])
    messages.success(
        request,
        "Topshiriq arxivlandi: oʻquvchilar uni endi koʻrmaydi."
        if task.is_archived
        else "Topshiriq arxivdan qaytarildi.",
    )
    return redirect("tasks:task", task.pk)


def version_create(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    task = get_for_user_or_404(Task, request.user, pk=pk)
    form = VersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            version = _save_version(task, form)
        return redirect("tasks:version", task.pk, version.number)
    return render(request, "tasks/version_form.html", {"form": form, "task": task})


def _save_version(task: Task, form: TaskForm | VersionForm) -> TaskVersion:
    """Store the checked package and its starter, and queue the image build."""
    upload = form.cleaned_data["package"]
    upload.seek(0)
    data = upload.read()
    last = task.versions.aggregate(last=Max("number"))["last"] or 0
    version = TaskVersion(task=task, number=last + 1, sha256=hashlib.sha256(data).hexdigest())
    version.package.save("package.zip", ContentFile(data), save=False)
    starter = starter_zip(form.archive_files, form.package.package_name)
    version.starter.save("starter.zip", ContentFile(starter), save=False)
    version.save()
    enqueue_build(version)
    return version


def _version(request: HttpRequest, pk: int, number: int) -> TaskVersion:
    task = get_for_user_or_404(Task, request.user, pk=pk)
    return get_for_user_or_404(TaskVersion, request.user, task=task, number=number)


def version_detail(request: HttpRequest, pk: int, number: int) -> HttpResponse:
    require(request, Action.VIEW_TASKS)
    version = _version(request, pk, number)
    return render(request, "tasks/version_detail.html", _version_context(request, version))


def version_status(request: HttpRequest, pk: int, number: int) -> HttpResponse:
    """The part of the version page that changes while the image builds (HTMX, every 1 s)."""
    require(request, Action.VIEW_TASKS)
    version = _version(request, pk, number)
    response = render(request, "tasks/_version_status.html", _version_context(request, version))
    if version.status != TaskVersion.Status.BUILDING:
        response.status_code = STOP_POLLING
    return response


def _version_context(request: HttpRequest, version: TaskVersion) -> dict[str, object]:
    is_author = can(request.user, Action.MANAGE_TASKS)
    ready = version.status == TaskVersion.Status.READY
    return {
        "task": version.task,
        "version": version,
        "tests": (version.manifest or {}).get("tests", []),
        "is_author": is_author,
        "is_published": version.task.published_version_id == version.pk,
        # The build log can quote hidden tests: only their author sees it (SPEC §1).
        "show_log": is_author,
        "publish_form": PublishForm(version=version) if is_author and ready else None,
    }


@require_POST
def version_publish(request: HttpRequest, pk: int, number: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    version = _version(request, pk, number)
    if version.status != TaskVersion.Status.READY:
        messages.error(request, "Faqat tayyor versiyani eʼlon qilish mumkin.")
        return redirect("tasks:version", pk, number)
    form = PublishForm(request.POST, version=version)
    if not form.is_valid():
        context = {**_version_context(request, version), "publish_form": form}
        return render(request, "tasks/version_detail.html", context, status=400)
    with transaction.atomic():
        version.time_limit_s = form.cleaned_data["time_limit_s"]
        version.save(update_fields=["time_limit_s"])
        version.task.published_version = version
        version.task.save(update_fields=["published_version", "updated_at"])
    messages.success(request, f"{version.number}-versiya eʼlon qilindi.")
    return redirect("tasks:task", pk)


def version_package(request: HttpRequest, pk: int, number: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)  # the package holds the solution and hidden tests
    version = _version(request, pk, number)
    return private_download(version.package, f"task-{pk}-v{number}.zip")


def version_starter(request: HttpRequest, pk: int, number: int) -> HttpResponse:
    require(request, Action.VIEW_TASKS)
    version = _version(request, pk, number)
    return private_download(version.starter, f"task-{pk}-v{number}-starter.zip")


def assign(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_TASKS)
    task = get_for_user_or_404(Task, request.user, pk=pk)
    if task.published_version_id is None:
        messages.error(request, "Avval topshiriqning tayyor versiyasini eʼlon qiling.")
        return redirect("tasks:task", task.pk)
    form = AssignmentForm(
        request.POST or None, instance=Assignment(task=task), teacher=request.user
    )
    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        messages.success(request, f"Topshiriq “{assignment.group.name}” guruhiga biriktirildi.")
        return redirect("tasks:task", task.pk)
    return render(
        request,
        "tasks/assignment_form.html",
        {"form": form, "task": task, "cancel_url": reverse("tasks:task", args=[task.pk])},
    )


@require_POST
def preview(request: HttpRequest) -> HttpResponse:
    """The statement as students will see it (the wizard's Ko'rish button, HTMX)."""
    require(request, Action.MANAGE_TASKS)
    return render(
        request,
        "tasks/_statement.html",
        {"statement": render_markdown(request.POST.get("statement_md", ""))},
    )
