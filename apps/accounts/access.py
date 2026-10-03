"""The permission layer's entry point for views (CLAUDE.md, "Hech qachon").

Objects are fetched by id only through get_for_user_or_404: it looks inside the user's
for_user() rows, so another centre's object is a 404, the same as a missing one. A 403
would tell the user that the id exists.
"""

from typing import TYPE_CHECKING, Any

from django.db import models
from django.shortcuts import get_object_or_404

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.models import User


def visible_to[M: models.Model](
    model: type[M], user: "User | AnonymousUser"
) -> "models.QuerySet[M]":
    """The model's rows the user may see. A model without for_user() is a programming error."""
    queryset = model._default_manager.all()
    for_user = getattr(queryset, "for_user", None)
    if for_user is None:
        raise TypeError(f"{model.__name__}'s queryset has no for_user(user)")
    return for_user(user)


def get_for_user_or_404[M: models.Model](
    model: type[M], user: "User | AnonymousUser", **lookups: Any
) -> M:
    return get_object_or_404(visible_to(model, user), **lookups)
