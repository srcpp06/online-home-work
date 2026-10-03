"""A centre's teachers, students and managers (SPEC §1, docs/UI.md §6).

The centre admin manages them; the centre manager and teachers only look. The superadmin
works in Django admin, so these pages send them there.
"""

from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, ProtectedError, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.access import get_for_user_or_404, visible_to
from apps.accounts.forms import PersonForm
from apps.accounts.models import Group, Role, User
from apps.accounts.passwords import temporary_password
from apps.accounts.permissions import Action, can
from apps.accounts.views._guard import require

# Role -> (list title, list URL name, add button, empty state).
KINDS: dict[str, tuple[str, str, str, str]] = {
    Role.TEACHER: (
        "Oʻqituvchilar",
        "accounts:teachers",
        "Oʻqituvchi qoʻshish",
        "Hali oʻqituvchi yoʻq.",
    ),
    Role.STUDENT: ("Oʻquvchilar", "accounts:students", "Oʻquvchi qoʻshish", "Hali oʻquvchi yoʻq."),
    Role.CENTER_MANAGER: (
        "Menejerlar",
        "accounts:managers",
        "Menejer qoʻshish",
        "Hali menejer yoʻq.",
    ),
}
_NEW_PASSWORD = "accounts.new_password"  # noqa: S105 -- a session key


def _admin_users(role: str = "") -> HttpResponse:
    url = reverse("admin:accounts_user_changelist")
    return redirect(f"{url}?role__exact={role}" if role else url)


def _managed(request: HttpRequest, pk: int) -> User:
    """Someone the user may manage: never themselves (their own password has its page)."""
    require(request, Action.MANAGE_PEOPLE)
    person = get_for_user_or_404(User, request.user, pk=pk)
    if person.pk == request.user.pk:
        raise PermissionDenied
    return person


def people_list(request: HttpRequest, role: str) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return _admin_users(role)
    require(request, Action.VIEW_PEOPLE)
    if role == Role.CENTER_MANAGER:
        require(request, Action.MANAGE_PEOPLE)
    title, _, add_label, empty = KINDS[role]
    people = (
        visible_to(User, request.user)
        .filter(role=role)
        .annotate(
            group_count=Count("teaching_groups", distinct=True)
            + Count("study_groups", distinct=True)
        )
        .order_by("last_name", "first_name", "username")
    )
    return render(
        request,
        "accounts/people_list.html",
        {
            "title": title,
            "role": role,
            "people": people,
            "add_url": reverse(f"accounts:{role.removeprefix('center_')}_add")
            if can(request.user, Action.MANAGE_PEOPLE)
            else "",
            "add_label": add_label,
            "empty": empty,
        },
    )


def person_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_user_change", pk)
    require(request, Action.VIEW_PEOPLE)
    person = get_for_user_or_404(User, request.user, pk=pk)
    groups = (
        visible_to(Group, request.user)
        .filter(Q(teacher=person) | Q(students=person))
        .select_related("teacher")
        .distinct()
    )
    return render(
        request,
        "accounts/person_detail.html",
        {
            "person": person,
            "groups": groups,
            "list_url": reverse(KINDS[person.role][1]) if person.role in KINDS else "",
            "can_manage": can(request.user, Action.MANAGE_PEOPLE) and person.pk != request.user.pk,
        },
    )


def person_create(request: HttpRequest, role: str) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_user_add")
    require(request, Action.MANAGE_PEOPLE)
    person = User(role=role, center=request.user.center, must_change_password=True)
    form = PersonForm(request.POST or None, instance=person, creating=True)
    if request.method == "POST" and form.is_valid():
        password = temporary_password()
        person = form.save(commit=False)
        person.set_password(password)
        person.save()
        _remember_password(request, person, password)
        return redirect("accounts:person_new_password", person.pk)
    _, list_name, add_label, _ = KINDS[role]
    return render(
        request,
        "accounts/person_form.html",
        {"form": form, "title": add_label, "cancel_url": reverse(list_name), "submit": add_label},
    )


def person_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if request.user.role == Role.SUPERADMIN:
        return redirect("admin:accounts_user_change", pk)
    person = _managed(request, pk)
    form = PersonForm(request.POST or None, instance=person, creating=False)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oʻzgarishlar saqlandi.")
        return redirect("accounts:person", person.pk)
    return render(
        request,
        "accounts/person_form.html",
        {
            "form": form,
            "title": f"{person.display_name}: tahrirlash",
            "cancel_url": reverse("accounts:person", args=[person.pk]),
            "submit": "Saqlash",
        },
    )


def person_reset_password(request: HttpRequest, pk: int) -> HttpResponse:
    person = _managed(request, pk)
    if request.method == "POST":
        password = temporary_password()
        person.set_password(password)  # also signs them out everywhere
        person.must_change_password = True
        person.save(update_fields=["password", "must_change_password"])
        _remember_password(request, person, password)
        return redirect("accounts:person_new_password", person.pk)
    return render(
        request,
        "accounts/confirm.html",
        {
            "title": "Parolni tiklash",
            "text": f"{person.display_name} uchun yangi vaqtinchalik "
            "parol yaratiladi. Eski parol ishlamay qoladi; foydalanuvchi birinchi kirishda "
            "uni almashtiradi.",
            "submit": "Parolni tiklash",
            "danger": False,
            "cancel_url": reverse("accounts:person", args=[person.pk]),
        },
    )


def person_new_password(request: HttpRequest, pk: int) -> HttpResponse:
    """The temporary password, shown once: it lives in the session until this page reads it."""
    person = _managed(request, pk)
    remembered: dict[str, Any] = request.session.get(_NEW_PASSWORD) or {}
    if remembered.get("user") != person.pk:
        messages.info(
            request,
            "Vaqtinchalik parol faqat bir marta koʻrsatiladi. Kerak boʻlsa, parolni qayta tiklang.",
        )
        return redirect("accounts:person", person.pk)
    del request.session[_NEW_PASSWORD]
    response = render(
        request,
        "accounts/person_new_password.html",
        {"person": person, "password": remembered["password"]},
    )
    response["Cache-Control"] = "no-store"  # never from the browser's cache or history
    return response


def person_delete(request: HttpRequest, pk: int) -> HttpResponse:
    person = _managed(request, pk)
    name = person.display_name
    if request.method == "POST":
        list_name = KINDS[person.role][1]
        try:
            person.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{name} bilan bogʻliq maʼlumotlar bor (guruh, topshiriq yoki yechimlar). "
                "Ularni saqlab qolish uchun oʻchirish oʻrniga hisobni nofaol qiling.",
            )
            return redirect("accounts:person", person.pk)
        messages.success(request, f"{name} oʻchirildi.")
        return redirect(list_name)
    return render(
        request,
        "accounts/confirm.html",
        {
            "title": "Foydalanuvchini oʻchirish",
            "text": f"{name} butunlay oʻchiriladi. Buni qaytarib boʻlmaydi; vaqtincha toʻxtatish "
            "uchun tahrirlash sahifasida hisobni nofaol qiling.",
            "submit": "Oʻchirish",
            "danger": True,
            "cancel_url": reverse("accounts:person", args=[person.pk]),
        },
    )


def _remember_password(request: HttpRequest, person: User, password: str) -> None:
    # The session lives in the database; the next page shows the password and drops it.
    request.session[_NEW_PASSWORD] = {"user": person.pk, "password": password}
