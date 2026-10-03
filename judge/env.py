"""Settings from .env and the environment (SPEC §6), shared by the judge and Django.

No imports from the rest of the project: Django settings read this without loading the
Docker SDK. There are no defaults in code: .env.example is the one place where values live.
"""

import os
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Settings are missing or wrong; the message says which."""


def read_env(
    path: Path = REPO_ROOT / ".env", environ: Mapping[str, str] = os.environ
) -> dict[str, str]:
    """Values from the .env file (if there is one), overridden by the environment."""
    values: dict[str, str] = {}
    if path.is_file():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if not separator or not name.strip():
                raise ConfigError(f"{path}:{number}: expected NAME=value")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[name.strip()] = value
    return {**values, **environ}
