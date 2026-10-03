"""A centre's study groups (SPEC §1): the centre admin manages them, others look."""

from django.contrib import messages
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.forms import GroupForm
from apps.accounts.models import Group, Role
from apps.accounts.permissions import Action, can
from apps.accounts.views._guard import require


def group_list(request: HttpRequest) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_group_changelist")
    require(request, Action.VIEW_GROUPS)
    groups = (
        visible_to(Group, request.user)
        .select_related("teacher")
        .annotate(student_count=Count("students"))
        .order_by("name")
    )
    teacher = request.user.role == Role.TEACHER
    return render(
        request,
        "accounts/group_list.html",
        {
            "title": "Guruhlarim" if teacher else "Guruhlar",
            "groups": groups,
            "can_manage": can(request.user, Action.MANAGE_GROUPS),
            "empty": "Sizga hali guruh biriktirilmagan." if teacher else "Hali guruh yoʻq.",
        },
    )


def group_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_group_change", pk)
    require(request, Action.VIEW_GROUPS)
    group = get_for_user_or_404(Group, request.user, pk=pk)
    return render(
        request,
        "accounts/group_detail.html",
        {
            "group": group,
            "students": group.students.order_by("last_name", "first_name", "username"),
            "can_manage": can(request.user, Action.MANAGE_GROUPS),
            "can_open_people": can(request.user, Action.VIEW_PEOPLE),
        },
    )


def group_create(request: HttpRequest) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_group_add")
    require(request, Action.MANAGE_GROUPS)
    form = GroupForm(request.POST or None, instance=Group(center=request.user.center))
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, f"“{group.name}” guruhi yaratildi.")
        return redirect("accounts:group", group.pk)
    return render(
        request,
        "accounts/group_form.html",
        {
            "form": form,
            "title": "Guruh yaratish",
            "submit": "Guruh yaratish",
            "cancel_url": reverse("accounts:groups"),
        },
    )


def group_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_group_change", pk)
    require(request, Action.MANAGE_GROUPS)
    group = get_for_user_or_404(Group, request.user, pk=pk)
    form = GroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oʻzgarishlar saqlandi.")
        return redirect("accounts:group", group.pk)
    return render(
        request,
        "accounts/group_form.html",
        {
            "form": form,
            "title": f"{group.name}: tahrirlash",
            "submit": "Saqlash",
            "cancel_url": reverse("accounts:group", args=[group.pk]),
        },
    )


def group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    require(request, Action.MANAGE_GROUPS)
    group = get_for_user_or_404(Group, request.user, pk=pk)
    if request.method == "POST":
        group.delete()
        messages.success(request, f"“{group.name}” guruhi oʻchirildi.")
        return redirect("accounts:groups")
    return render(
        request,
        "accounts/confirm.html",
        {
            "title": "Guruhni oʻchirish",
            "text": f"“{group.name}” guruhi oʻchiriladi. "
            "Oʻqituvchi va oʻquvchilarning hisoblari qoladi.",
            "submit": "Oʻchirish",
            "danger": True,
            "cancel_url": reverse("accounts:group", args=[group.pk]),
        },
    )
