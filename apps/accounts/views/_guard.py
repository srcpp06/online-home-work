"""Checks every page in this app starts with."""

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts.permissions import Action, can


def require(request: HttpRequest, action: Action) -> None:
    """The role may do this kind of thing at all, or 403.

    Checked before any object is looked up, so a refusal says nothing about whether an id
    exists. Which objects the user reaches is then get_for_user_or_404's job (another
    centre's object is a 404).
    """
    if not can(request.user, action):
        raise PermissionDenied
