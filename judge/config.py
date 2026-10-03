"""Judge settings from .env and the environment (SPEC §6), and runner profiles.

Django-free: the CLI reads them here; .env itself is read by judge.env, which the Django
settings share. There are no defaults in code: .env.example is where values live.
"""

import json
import re
import string
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from judge.core.profile import RunnerProfile
from judge.env import REPO_ROOT, ConfigError
from judge.env import read_env as read_env  # re-exported: the CLI and tools import it here
from judge.infra.sandbox import NodeSettings
from judge.packaging.zip_validator import ZipLimits

PROFILES_DIR = REPO_ROOT / "profiles"
REQUIRED = (
    "JUDGE_CPU_SHARES",
    "JUDGE_MAX_OUTPUT_KB",
    "JUDGE_RUNTIME",
    "SUBMISSION_MAX_ZIP_MB",
    "SUBMISSION_MAX_UNPACKED_MB",
    "SUBMISSION_MAX_FILES",
    "TASK_MAX_ZIP_MB",
    "TASK_MAX_UNPACKED_MB",
    "TASK_MAX_FILES",
)
_MB = 1024 * 1024
_PROFILE_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


@dataclass(frozen=True)
class JudgeConfig:
    node: NodeSettings
    submission_limits: ZipLimits
    task_limits: ZipLimits
    values: Mapping[str, str]  # every setting, for ${NAME} in profile.json

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        missing = [name for name in REQUIRED if not env.get(name)]
        if missing:
            raise ConfigError(
                f"missing settings: {', '.join(missing)}. "
                "Add them to .env from .env.example (`make setup` creates .env if it is missing)."
            )

        def number(name: str) -> int:
            try:
                value = int(env[name])
            except ValueError:
                raise ConfigError(f"{name} must be a whole number, got {env[name]!r}") from None
            if value < 1:
                raise ConfigError(f"{name} must be positive, got {value}")
            return value

        return cls(
            node=NodeSettings(
                cpu_shares=number("JUDGE_CPU_SHARES"),
                max_output_bytes=number("JUDGE_MAX_OUTPUT_KB") * 1024,
                runtime=env["JUDGE_RUNTIME"],
            ),
            submission_limits=ZipLimits(
                max_zip_bytes=number("SUBMISSION_MAX_ZIP_MB") * _MB,
                max_unpacked_bytes=number("SUBMISSION_MAX_UNPACKED_MB") * _MB,
                max_files=number("SUBMISSION_MAX_FILES"),
            ),
            task_limits=ZipLimits(
                max_zip_bytes=number("TASK_MAX_ZIP_MB") * _MB,
                max_unpacked_bytes=number("TASK_MAX_UNPACKED_MB") * _MB,
                max_files=number("TASK_MAX_FILES"),
            ),
            values=dict(env),
        )

    def base_image(self, profile: RunnerProfile) -> str:
        """The profile's base image tag, e.g. ohw-base-dart:${DART_VERSION} filled in."""
        try:
            return string.Template(profile.base_image).substitute(self.values)
        except KeyError as error:
            name = error.args[0]
            raise ConfigError(f"profile {profile.slug!r} needs the setting {name}") from None


def load_profile(slug: str, directory: Path = PROFILES_DIR) -> RunnerProfile:
    available = sorted(path.parent.name for path in directory.glob("*/profile.json"))
    if not _PROFILE_SLUG.fullmatch(slug) or slug not in available:
        raise ConfigError(f"unknown profile {slug!r}; available: {', '.join(available)}")
    return RunnerProfile.from_json_data(json.loads((directory / slug / "profile.json").read_text()))
