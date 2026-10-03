"""Design system tags: {% icon %} and {% status_badge %} (docs/UI.md §5)."""

import re
from functools import cache
from pathlib import Path

from django import template
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

from apps.ui.status import status_look

register = template.Library()

ICONS_DIR = Path(__file__).resolve().parent.parent / "icons"
_ICON_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.DOTALL)


@cache
def _icon_body(name: str) -> str:
    """The SVG's inner markup; the outer tag is rebuilt so callers set its class."""
    if not _ICON_NAME.fullmatch(name):
        raise ValueError(f"bad icon name {name!r}")
    path = ICONS_DIR / f"{name}.svg"
    if not path.is_file():
        raise ValueError(f"no icon {name!r} in {ICONS_DIR}")
    svg = path.read_text()
    opening = _SVG_OPEN.search(svg)
    if opening is None:
        raise ValueError(f"{path} is not an SVG")
    return svg[opening.end() : svg.rindex("</svg>")].strip()


@register.simple_tag
def icon(name: str, css_class: str = "size-5") -> SafeString:
    """A Lucide icon inlined in the page; decorative, so screen readers skip it."""
    return mark_safe(  # noqa: S308 -- our own SVG files; the class is escaped
        f'<svg class="{escape(css_class)}" xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
        f'focusable="false">{_icon_body(name)}</svg>'
    )


@register.simple_tag
def status_badge(status: str, failed_test: int | None = None) -> SafeString:
    look = status_look(status, failed_test)
    return render_to_string(
        "ui/components/status_badge.html", {"look": look, "icon_svg": icon(look.icon, "size-5")}
    )
