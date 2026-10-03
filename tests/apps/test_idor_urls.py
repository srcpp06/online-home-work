"""Every URL that takes an id gets an IDOR test (SPEC §1).

Add each such URL to IDOR_URLS with a function that builds its addresses for centre b's
objects. Each role of centre a then tries them with GET and POST: the answer must be a 404
(get_for_user_or_404) or a 403 (the role may not do this at all, refused before the object
is looked up), and centre b's data must be unchanged. A URL left out fails
test_every_url_with_an_id_has_an_idor_case.
"""

from collections.abc import Callable, Iterator

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, include, path, re_path, reverse

from apps.accounts.models import Group, User
from tests.apps.world import World


def _people(name: str) -> Callable[[World], list[str]]:
    """The URL for every person of centre b."""
    return lambda w: [
        reverse(name, args=[u.pk]) for u in (w.b.admin, w.b.manager, w.b.teacher, w.b.student)
    ]


def _group(name: str) -> Callable[[World], list[str]]:
    return lambda w: [reverse(name, args=[w.b.group.pk])]


# URL name -> the addresses of centre b's objects.
IDOR_URLS: dict[str, Callable[[World], list[str]]] = {
    "accounts:person": _people("accounts:person"),
    "accounts:person_edit": _people("accounts:person_edit"),
    "accounts:person_password": _people("accounts:person_password"),
    "accounts:person_new_password": _people("accounts:person_new_password"),
    "accounts:person_delete": _people("accounts:person_delete"),
    "accounts:group": _group("accounts:group"),
    "accounts:group_edit": _group("accounts:group_edit"),
    "accounts:group_delete": _group("accounts:group_delete"),
}
DENIED = (403, 404)
VIEWERS = ("admin", "manager", "teacher", "student")
# Django admin is the superadmin's: no other role gets in (tests/apps/accounts/test_admin.py).
SKIPPED_NAMESPACES = ("admin",)


def urls_with_parameters(
    patterns: list[URLPattern | URLResolver] | None = None, prefix: str = "", namespace: str = ""
) -> Iterator[tuple[str, str]]:
    """(name, route) of every URL that takes a value from its path."""
    for pattern in get_resolver().url_patterns if patterns is None else patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            if pattern.namespace in SKIPPED_NAMESPACES:
                continue
            inner = ":".join(filter(None, (namespace, pattern.namespace)))
            yield from urls_with_parameters(pattern.url_patterns, route, inner)
        elif "<" in route or pattern.pattern.regex.groups:
            name = ":".join(filter(None, (namespace, pattern.name or "")))
            yield name or f"(unnamed) {route}", route


def view(request: HttpRequest, **kwargs: object) -> HttpResponse:
    return HttpResponse()


def test_urls_with_parameters_finds_every_kind_of_parameter() -> None:
    patterns = [
        path("about/", view, name="about"),
        path("groups/<int:pk>/", view, name="group"),
        re_path(r"^files/(?P<slug>[a-z]+)/$", view, name="file"),
        path("c/<slug:center>/", include(([path("", view, name="home")], "center"))),
        path("admin/", include(([path("<int:pk>/", view, name="x")], "admin"))),
    ]

    assert list(urls_with_parameters(patterns)) == [
        ("group", "groups/<int:pk>/"),
        ("file", "^files/(?P<slug>[a-z]+)/$"),
        ("center:home", "c/<slug:center>/"),
    ]


def test_every_url_with_an_id_has_an_idor_case() -> None:
    missing = [
        f"{name}: {route}" for name, route in urls_with_parameters() if name not in IDOR_URLS
    ]

    assert not missing, "add these to IDOR_URLS:\n" + "\n".join(missing)


def snapshot(world: World) -> list[tuple[object, ...]]:
    """Centre b's people and group, as stored."""
    b = world.b
    people = User.objects.filter(center=b.center).order_by("pk")
    groups = Group.objects.filter(center=b.center).order_by("pk")
    return [
        *people.values_list("pk", "username", "first_name", "password", "is_active"),
        *groups.values_list("pk", "name", "teacher_id"),
        *Group.students.through.objects.filter(group__center=b.center)
        .order_by("pk")
        .values_list("group_id", "user_id"),
    ]


@pytest.mark.parametrize("viewer", VIEWERS)
@pytest.mark.parametrize("name", sorted(IDOR_URLS))
def test_another_centres_object_is_out_of_reach(
    client: Client, world: World, name: str, viewer: str
) -> None:
    before = snapshot(world)
    client.force_login(getattr(world.a, viewer))
    # Data that would change something if a view accepted it.
    data = {"first_name": "Hacked", "last_name": "Hacked", "username": "hacked", "name": "Hacked"}

    for url in IDOR_URLS[name](world):
        assert client.get(url).status_code in DENIED, url
        assert client.post(url, data).status_code in DENIED, url

    assert snapshot(world) == before
