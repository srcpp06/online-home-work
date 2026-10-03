"""The superadmin panel is not on the internet (SPEC §5): in production /admin/ answers only
requests that came through the server's private door, which proves itself with a secret."""

from typing import Any

import pytest
from django.test import Client

SECRET = "gate-secret-1234567890"  # noqa: S105 -- a test value
GATE = {"HTTP_X_ADMIN_GATE": SECRET}


@pytest.fixture
def production(settings: Any) -> Any:
    settings.ADMIN_GATE_REQUIRED = True
    settings.ADMIN_GATE_SECRET = SECRET
    return settings


@pytest.mark.django_db
def test_the_panel_is_a_404_from_the_internet(client: Client, production: Any) -> None:
    assert client.get("/admin/login/").status_code == 404
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_a_wrong_secret_is_a_404(client: Client, production: Any) -> None:
    assert client.get("/admin/login/", HTTP_X_ADMIN_GATE="guess").status_code == 404


@pytest.mark.django_db
def test_the_private_door_opens_it(client: Client, production: Any) -> None:
    assert client.get("/admin/login/", **GATE).status_code == 200


@pytest.mark.django_db
def test_without_a_secret_the_panel_stays_closed(client: Client, production: Any) -> None:
    production.ADMIN_GATE_SECRET = ""

    assert client.get("/admin/login/", HTTP_X_ADMIN_GATE="").status_code == 404


@pytest.mark.django_db
def test_the_site_itself_is_not_gated(client: Client, production: Any) -> None:
    assert client.get("/").status_code == 200
    assert client.get("/login/").status_code == 200


@pytest.mark.django_db
def test_the_private_door_sets_no_hsts(client: Client, production: Any) -> None:
    """HSTS for "localhost" would force https onto every local site in the browser."""
    production.SECURE_HSTS_SECONDS = 3600

    public = client.get("/login/", secure=True)
    private = client.get("/admin/login/", secure=True, **GATE)

    assert "Strict-Transport-Security" in public
    assert "Strict-Transport-Security" not in private


@pytest.mark.django_db
def test_development_keeps_the_panel_open(client: Client, settings: Any) -> None:
    settings.ADMIN_GATE_REQUIRED = False

    assert client.get("/admin/login/").status_code == 200
