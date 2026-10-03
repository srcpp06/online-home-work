"""The base layout and the development-only styleguide."""

from typing import Any

import pytest
from django.test import Client

from apps.ui.status import STATUSES
from judge.env import REPO_ROOT


@pytest.mark.django_db
def test_styleguide_is_hidden_outside_development(client: Client, settings: Any) -> None:
    settings.DEBUG = False

    assert client.get("/ui/").status_code == 404


@pytest.mark.django_db
def test_styleguide_shows_the_design_system(client: Client, settings: Any) -> None:
    settings.DEBUG = True

    response = client.get("/ui/")

    html = response.content.decode()
    assert response.status_code == 200
    assert '<html lang="uz">' in html
    assert 'class="notebook' in html
    assert 'aria-live="polite"' in html
    assert "--pen-red" in html
    for look in STATUSES.values():
        if "N-testda" not in look.label:
            assert look.label in html
    assert "3-testda xato" in html


@pytest.mark.django_db
def test_base_layout_loads_self_hosted_assets(client: Client, settings: Any) -> None:
    settings.DEBUG = True

    html = client.get("/ui/").content.decode()

    assert '<link rel="stylesheet" href="/static/css/app.css">' in html
    assert '<script src="/static/vendor/htmx-2.0.11.min.js" defer></script>' in html
    assert (REPO_ROOT / "static" / "vendor" / "htmx-2.0.11.min.js").is_file()
    assert "http://" not in html.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert "https://" not in html


@pytest.mark.django_db
def test_htmx_requests_carry_the_csrf_token(client: Client, settings: Any) -> None:
    settings.DEBUG = True

    html = client.get("/ui/").content.decode()

    assert 'hx-headers=\'{"X-CSRFToken": "' in html
