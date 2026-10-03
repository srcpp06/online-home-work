"""The client's IP address for login lockouts (django-axes)."""

from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str:
    """Caddy's X-Forwarded-For, else the socket address.

    In production web is reachable only through Caddy, which replaces any X-Forwarded-For a
    client sends with the address it sees, so the last entry is the real client. Without
    it every student would share Caddy's address, and one lockout would lock a whole class.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    last = forwarded.rsplit(",", 1)[-1].strip()
    return last or request.META.get("REMOTE_ADDR", "")
