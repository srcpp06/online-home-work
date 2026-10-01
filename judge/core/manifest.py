"""Ordered list of the tests a task version runs (SPEC §3.3, §3.7)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self


class Visibility(StrEnum):
    PUBLIC = "public"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class ManifestTest:
    name: str
    stage: int
    visibility: Visibility

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("test name must not be empty")
        if self.stage < 1:
            raise ValueError(f"stage must be >= 1, got {self.stage}")


@dataclass(frozen=True)
class Manifest:
    """Tests in run order: by stage, and inside a stage public tests before hidden ones.

    A run is trusted only when it reports exactly these tests in exactly this order.
    """

    tests: tuple[ManifestTest, ...]

    def __post_init__(self) -> None:
        if not self.tests:
            raise ValueError("a manifest needs at least one test")
        order = [(test.stage, test.visibility == Visibility.HIDDEN) for test in self.tests]
        if order != sorted(order):
            raise ValueError("tests must be ordered by stage, public before hidden in a stage")

    def to_json_data(self) -> dict[str, Any]:
        return {
            "tests": [
                {"name": test.name, "stage": test.stage, "visibility": str(test.visibility)}
                for test in self.tests
            ]
        }

    @classmethod
    def from_json_data(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            tuple(
                ManifestTest(
                    name=item["name"],
                    stage=item["stage"],
                    visibility=Visibility(item["visibility"]),
                )
                for item in data["tests"]
            )
        )
