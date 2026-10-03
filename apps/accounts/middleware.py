"""The first sign-in ends on the password change page (SPEC §1); the superadmin panel
answers only through the server's private door (SPEC §5)."""

from collections.abc import Callable

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import constant_time_compare

ADMIN_GATE_HEADER = "X-Admin-Gate"


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


class AdminGateMiddleware:
    """/admin/ is not on the internet: in production it answers only requests from Caddy's
    private door (127.0.0.1:8443 on the server, reached with an SSH tunnel), which adds
    the ADMIN_GATE_SECRET header. The public site strips that header, so it can't be
    forged from outside; without a secret the panel stays closed. Everyone else gets 404,
    as if there were no panel at all.

    First in MIDDLEWARE: a refused request touches nothing else, and the HSTS header the
    security middleware adds is taken off again for the private door (HSTS for
    "localhost" would force https onto every local site in the browser).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith(reverse("admin:index")) or not settings.ADMIN_GATE_REQUIRED:
            return self.get_response(request)
        secret = settings.ADMIN_GATE_SECRET
        given = request.headers.get(ADMIN_GATE_HEADER, "")
        if not secret or not constant_time_compare(given, secret):
            raise Http404
        response = self.get_response(request)
        del response["Strict-Transport-Security"]
        return response
