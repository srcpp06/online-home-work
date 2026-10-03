"""The first sign-in ends on the password change page (SPEC §1)."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class PasswordChangeRequiredMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            # The change page, signing out and the files those pages need stay open.
            allowed = (reverse("accounts:password_change"), reverse("accounts:logout"))
            if request.path not in allowed and not request.path.startswith(settings.STATIC_URL):
                return redirect("accounts:password_change")
        return self.get_response(request)
