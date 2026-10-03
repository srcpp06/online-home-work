"""Typed reading of the Django settings (SPEC §6), with messages that say how to fix them.

Every value comes from .env or the environment; there are no defaults in code.
"""

from collections.abc import Mapping
from typing import Any

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

POSTGRESQL = "django.db.backends.postgresql"
# Persistent connections, checked before reuse: the worker and gunicorn keep them for 60 s.
CONN_MAX_AGE_S = 60


class Env:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = values

    def require(self, *names: str) -> None:
        """All missing settings in one message, instead of one per restart."""
        missing = [name for name in names if not self._values.get(name, "").strip()]
        if missing:
            raise ImproperlyConfigured(
                f"missing settings: {', '.join(missing)}. Add them to .env from .env.example "
                "(an old .env: delete it and run `make setup`, which creates a new one)."
            )

    def text(self, name: str) -> str:
        value = self._values.get(name, "").strip()
        if not value:
            self.require(name)
        return value

    def flag(self, name: str) -> bool:
        value = self.text(name).lower()
        if value not in ("true", "false"):
            raise ImproperlyConfigured(f"{name} must be true or false, got {value!r}")
        return value == "true"

    def positive_int(self, name: str) -> int:
        value = self.text(name)
        if not value.isdigit() or int(value) < 1:
            raise ImproperlyConfigured(f"{name} must be a whole number above 0, got {value!r}")
        return int(value)

    def comma_list(self, name: str) -> list[str]:
        items = [item.strip() for item in self.text(name).split(",")]
        if not all(items):
            raise ImproperlyConfigured(f"{name} has an empty item: {self.text(name)!r}")
        return items

    def database(self, name: str) -> dict[str, Any]:
        """A PostgreSQL database URL. The URL is never echoed back: it holds the password."""
        url = self.text(name)
        scheme, separator, _ = url.partition("://")
        got = f"scheme {scheme!r}" if separator else "no scheme"
        try:
            config = dj_database_url.parse(
                url, conn_max_age=CONN_MAX_AGE_S, conn_health_checks=True
            )
        except ValueError:
            config = {}
        if config.get("ENGINE") != POSTGRESQL:
            raise ImproperlyConfigured(
                f"{name} must be a postgres:// URL, got {got}: "
                "the job queue needs PostgreSQL (SKIP LOCKED)"
            )
        return dict(config)
