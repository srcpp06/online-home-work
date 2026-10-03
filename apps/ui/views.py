from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from apps.ui.status import STATUSES
from apps.ui.tokens import color_tokens


@login_not_required  # development only, and it shows no data
def styleguide(request: HttpRequest) -> HttpResponse:
    """Every design system piece on one page, to check against docs/UI.md. Development only."""
    if not settings.DEBUG:
        raise Http404
    return render(
        request,
        "ui/styleguide.html",
        {
            "colors": list(color_tokens().items()),
            "statuses": [s for s in STATUSES if s != "wrong_answer"],
            "nav_items": [
                {"label": "Guruhlarim", "url": "#", "active": True},
                {"label": "Topshiriqlar", "url": "#", "active": False},
                {"label": "Jurnal", "url": "#", "active": False},
            ],
        },
    )
