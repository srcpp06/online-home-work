"""Runner profile: everything language-specific about running tests (SPEC §2, §3.1).

The core stays language-agnostic: a new language is a new profile (a Dockerfile and a
profile.json next to it), not new core code. Limits are configuration, not code.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self


class Lane(StrEnum):
    FAST = "fast"
    HEAVY = "heavy"


@dataclass(frozen=True)
class RunnerProfile:
    slug: str
    lane: Lane
    base_image: str  # e.g. "ohw-base-dart:${DART_VERSION}", filled in from the settings
    student_paths: tuple[str, ...]  # what is taken from a student's zip, e.g. ("lib",)
    install_command: tuple[str, ...]  # installs the teacher's libraries; the only networked step
    test_command: tuple[str, ...]
    test_import: str  # import that brings `group` into the combined test file
    parser: str
    static_check: str | None  # checker run on student files before the tests, e.g. "dart_imports"
    forbidden_imports: tuple[str, ...]  # e.g. ("dart:io", ...); what static_check rejects
    memory_mb: int
    cpus: float
    tmp_mb: int  # size of the /tmp tmpfs
    min_time_s: int
    max_time_s: int
    build_timeout_s: int  # for installing libraries

    def __post_init__(self) -> None:
        required = (self.slug, self.base_image, self.student_paths, self.install_command)
        if not (all(required) and self.test_command):
            raise ValueError(f"profile {self.slug!r} is missing a required field")
        if min(self.memory_mb, self.tmp_mb, self.min_time_s, self.build_timeout_s) < 1:
            raise ValueError(f"profile {self.slug!r}: limits must be positive")
        if self.cpus <= 0:
            raise ValueError(f"profile {self.slug!r}: cpus must be positive")
        if self.min_time_s > self.max_time_s:
            raise ValueError(f"profile {self.slug!r}: min_time_s is above max_time_s")

    @classmethod
    def from_json_data(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            slug=data["slug"],
            lane=Lane(data["lane"]),
            base_image=data["base_image"],
            student_paths=tuple(data["student_paths"]),
            install_command=tuple(data["install_command"]),
            test_command=tuple(data["test_command"]),
            test_import=data["test_import"],
            parser=data["parser"],
            static_check=data.get("static_check"),
            forbidden_imports=tuple(data.get("forbidden_imports", ())),
            memory_mb=data["memory_mb"],
            cpus=data["cpus"],
            tmp_mb=data["tmp_mb"],
            min_time_s=data["min_time_s"],
            max_time_s=data["max_time_s"],
            build_timeout_s=data["build_timeout_s"],
        )
