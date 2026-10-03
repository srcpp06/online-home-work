"""Every URL that takes an id gets an IDOR test (SPEC §1).

Add each such URL to IDOR_URLS with a function that builds its address for centre b's
object; the test signs in as each role of centre a and expects a 404. A URL left out
fails test_every_url_with_an_id_has_an_idor_case.
"""

from collections.abc import Callable, Iterator

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, include, path, re_path

from tests.apps.world import World

# URL name -> the address of centre b's object.
IDOR_URLS: dict[str, Callable[[World], str]] = {}
VIEWERS = ("admin", "teacher", "student")
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


@pytest.mark.parametrize("viewer", VIEWERS)
@pytest.mark.parametrize("name", sorted(IDOR_URLS))
def test_another_centres_object_is_404(
    client: Client, world: World, name: str, viewer: str
) -> None:
    client.force_login(getattr(world.a, viewer))

    assert client.get(IDOR_URLS[name](world)).status_code == 404
