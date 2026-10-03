"""The side menu for each role (docs/UI.md §5, §6)."""

from dataclasses import dataclass

from django.http import HttpRequest
from django.urls import reverse

from apps.accounts.models import Role


@dataclass(frozen=True)
class NavItem:
    label: str
    url: str
    active: bool


# Role -> (label, URL name). Pages arrive task by task (docs/ROADMAP.md).
MENUS: dict[str, tuple[tuple[str, str], ...]] = {
    Role.SUPERADMIN: (("Admin panel", "admin:index"),),
    Role.CENTER_ADMIN: (
        ("Oʻqituvchilar", "accounts:teachers"),
        ("Oʻquvchilar", "accounts:students"),
        ("Menejerlar", "accounts:managers"),
        ("Guruhlar", "accounts:groups"),
        ("Topshiriqlar", "tasks:tasks"),
    ),
    Role.CENTER_MANAGER: (
        ("Oʻqituvchilar", "accounts:teachers"),
        ("Oʻquvchilar", "accounts:students"),
        ("Guruhlar", "accounts:groups"),
        ("Topshiriqlar", "tasks:tasks"),
    ),
    Role.TEACHER: (("Guruhlarim", "accounts:groups"), ("Topshiriqlar", "tasks:tasks")),
    Role.STUDENT: (("Topshiriqlarim", "accounts:home"),),
}


def navigation(request: HttpRequest) -> dict[str, list[NavItem]]:
    """Context processor: nav_items for the signed-in user's role."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"nav_items": []}
    items = []
    for label, name in MENUS.get(user.role, ()):
        url = reverse(name)
        active = request.path == url or (url != "/" and request.path.startswith(url))
        items.append(NavItem(label, url, active))
    return {"nav_items": items}
