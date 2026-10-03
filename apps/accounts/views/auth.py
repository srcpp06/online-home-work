"""Signing in and out, changing the password, and each role's home page."""

from typing import Any

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.forms import LoginForm, NewPasswordForm
from apps.accounts.models import Role


class LoginView(auth_views.LoginView):
    """The students' door (StaffLoginView is the staff's). The form shows even when someone
    is signed in: the page says who, and signing in with another login switches the
    account (a superadmin in /admin/ trying a teacher)."""

    template_name = "accounts/login.html"
    form_class = LoginForm
    for_staff = False

    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), "for_staff": self.for_staff}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        return {**super().get_context_data(**kwargs), "for_staff": self.for_staff}


class StaffLoginView(LoginView):
    """Teachers, managers and admins."""

    for_staff = True


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:home")

    def form_valid(self, form: NewPasswordForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, "Parol almashtirildi.")
        return response


@login_not_required
def home(request: HttpRequest) -> HttpResponse:
    """The landing page with the two doors; signed in, each role's own start page."""
    if not request.user.is_authenticated:
        next_url = request.GET.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            next_url = ""
        return render(request, "accounts/landing.html", {"next": next_url})
    match request.user.role:
        case Role.SUPERADMIN:
            return redirect("admin:index")
        case Role.CENTER_ADMIN | Role.CENTER_MANAGER:
            return redirect("accounts:teachers")
        case Role.TEACHER:
            return redirect("accounts:groups")
    return redirect("submissions:assignments")
