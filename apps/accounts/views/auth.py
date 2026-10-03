"""Signing in and out, changing the password, and each role's home page."""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.accounts.forms import LoginForm, NewPasswordForm
from apps.accounts.models import Role


class LoginView(auth_views.LoginView):
    """The form shows even when someone is signed in: the page says who, and signing in
    with another login switches the account (a superadmin in /admin/ trying a teacher)."""

    template_name = "accounts/login.html"
    form_class = LoginForm


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:home")

    def form_valid(self, form: NewPasswordForm) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(self.request, "Parol almashtirildi.")
        return response


def home(request: HttpRequest) -> HttpResponse:
    """Where each role starts: the superadmin in Django admin, the others on their pages."""
    match request.user.role:
        case Role.SUPERADMIN:
            return redirect("admin:index")
        case Role.CENTER_ADMIN | Role.CENTER_MANAGER:
            return redirect("accounts:teachers")
        case Role.TEACHER:
            return redirect("accounts:groups")
    # Students: assignments come with the tasks (docs/ROADMAP.md); until then, the empty state.
    return render(request, "accounts/home_student.html")
