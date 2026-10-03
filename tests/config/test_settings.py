"""The Django project against the development PostgreSQL (`make db`)."""

import os
import secrets
import subprocess
import sys

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client

from apps.accounts.models import User
from judge.env import REPO_ROOT

POSTGRES_MAJOR = 17  # CLAUDE.md, "Qat'iy qarorlar"


def manage(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """manage.py in a fresh process: settings are read once, at start."""
    return subprocess.run(  # noqa: S603 -- our own manage.py with fixed arguments
        [sys.executable, "manage.py", *args],
        cwd=REPO_ROOT,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.django_db
def test_database_is_postgresql() -> None:
    assert connection.vendor == "postgresql"
    assert connection.pg_version // 10_000 == POSTGRES_MAJOR


def test_user_model_is_the_projects_own() -> None:
    assert get_user_model() is User


@pytest.mark.django_db
def test_migrations_match_the_models() -> None:
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


@pytest.mark.django_db
def test_admin_login_page_opens(client: Client) -> None:
    assert client.get("/admin/login/").status_code == 200


@pytest.mark.django_db
def test_admin_needs_a_login(client: Client) -> None:
    response = client.get("/admin/")

    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")


def test_production_settings_pass_the_deploy_check() -> None:
    result = manage(
        "check",
        "--deploy",
        "--fail-level",
        "WARNING",
        DJANGO_DEBUG="false",
        DJANGO_ALLOWED_HOSTS="ohw.example.uz",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(50),
    )

    assert result.returncode == 0, result.stderr
    assert "System check identified no issues" in result.stdout


def test_missing_settings_stop_the_start_with_one_message() -> None:
    result = manage("check", DJANGO_SECRET_KEY="", DJANGO_DEBUG="")

    assert result.returncode != 0
    assert "missing settings: DJANGO_SECRET_KEY, DJANGO_DEBUG." in result.stderr
