"""A development warning when the built CSS is missing: pages would show unstyled."""

from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Warning, register

from judge.env import REPO_ROOT

APP_CSS = REPO_ROOT / "static" / "css" / "app.css"


@register()
def built_css_exists(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    if not settings.DEBUG or APP_CSS.is_file():
        return []
    return [
        Warning(
            f"{APP_CSS.relative_to(REPO_ROOT)} is missing, so pages show without styles.",
            hint="Build it with `make css`, or start the site with `make dev`, which also "
            "rebuilds it on every change.",
            id="ui.W001",
        )
    ]
