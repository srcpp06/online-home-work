"""Reading Django settings: every problem is reported with a way to fix it."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import CONN_MAX_AGE_S, POSTGRESQL, Env


def test_require_names_every_missing_setting_at_once() -> None:
    env = Env({"DJANGO_DEBUG": "true", "TIME_ZONE": "  "})

    with pytest.raises(ImproperlyConfigured) as error:
        env.require("DJANGO_SECRET_KEY", "DJANGO_DEBUG", "TIME_ZONE")

    assert str(error.value).startswith("missing settings: DJANGO_SECRET_KEY, TIME_ZONE.")
    assert "make setup" in str(error.value)


def test_text_of_a_missing_setting_says_which() -> None:
    with pytest.raises(ImproperlyConfigured, match="missing settings: MEDIA_ROOT"):
        Env({}).text("MEDIA_ROOT")


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("False", False)])
def test_flag_reads_true_and_false(value: str, expected: bool) -> None:
    assert Env({"DJANGO_DEBUG": value}).flag("DJANGO_DEBUG") is expected


@pytest.mark.parametrize("value", ["yes", "1", "on"])
def test_flag_rejects_anything_else(value: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_DEBUG must be true or false"):
        Env({"DJANGO_DEBUG": value}).flag("DJANGO_DEBUG")


def test_comma_list_strips_items() -> None:
    env = Env({"HOSTS": "localhost, 127.0.0.1"})

    assert env.comma_list("HOSTS") == ["localhost", "127.0.0.1"]


@pytest.mark.parametrize("value", ["localhost,", "a,,b"])
def test_comma_list_rejects_empty_items(value: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="HOSTS has an empty item"):
        Env({"HOSTS": value}).comma_list("HOSTS")


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_database_reads_a_postgres_url(scheme: str) -> None:
    env = Env({"DATABASE_URL": f"{scheme}://ohw:s%40cret@db:5432/ohw"})

    config = env.database("DATABASE_URL")

    assert config["ENGINE"] == POSTGRESQL
    assert (config["HOST"], config["PORT"], config["NAME"]) == ("db", 5432, "ohw")
    assert (config["USER"], config["PASSWORD"]) == ("ohw", "s@cret")
    assert config["CONN_MAX_AGE"] == CONN_MAX_AGE_S
    assert config["CONN_HEALTH_CHECKS"] is True


@pytest.mark.parametrize(
    ("url", "got"),
    [
        ("sqlite:///db.sqlite3", "got scheme 'sqlite'"),
        ("mysql://ohw:hunter2@db/ohw", "got scheme 'mysql'"),
        ("nosuchdb://ohw:hunter2@db/ohw", "got scheme 'nosuchdb'"),
        ("ohw:hunter2@db/ohw", "got no scheme"),
    ],
)
def test_database_rejects_anything_but_postgres_without_echoing_the_url(url: str, got: str) -> None:
    with pytest.raises(ImproperlyConfigured) as error:
        Env({"DATABASE_URL": url}).database("DATABASE_URL")

    assert str(error.value).startswith(f"DATABASE_URL must be a postgres:// URL, {got}:")
    assert "hunter2" not in str(error.value)
