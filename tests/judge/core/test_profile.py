import json
from pathlib import Path
from typing import Any

import pytest

from judge.core.profile import Lane, RunnerProfile

PROFILES_DIR = Path(__file__).resolve().parents[3] / "profiles"


def profile_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "slug": "dart",
        "lane": "fast",
        "student_paths": ["lib"],
        "install_command": ["dart", "pub", "get"],
        "test_command": ["dart", "test"],
        "test_import": "package:test/test.dart",
        "parser": "dart_json",
        "memory_mb": 1024,
        "cpus": 1.0,
        "tmp_mb": 256,
        "min_time_s": 20,
        "max_time_s": 120,
        "build_timeout_s": 300,
    }
    return {**data, **overrides}


def test_profile_reads_json_data() -> None:
    profile = RunnerProfile.from_json_data(profile_data())

    assert profile.lane == Lane.FAST
    assert profile.student_paths == ("lib",)
    assert profile.test_command == ("dart", "test")


@pytest.mark.parametrize("slug", ["dart", "flutter"])
def test_shipped_profiles_are_valid(slug: str) -> None:
    data = json.loads((PROFILES_DIR / slug / "profile.json").read_text())

    profile = RunnerProfile.from_json_data(data)

    assert profile.slug == slug
    assert profile.test_command[-1] == "test/_ohw_all_test.dart"
    assert "json" in profile.test_command


def test_flutter_runs_in_the_heavy_lane() -> None:
    data = json.loads((PROFILES_DIR / "flutter" / "profile.json").read_text())

    assert RunnerProfile.from_json_data(data).lane == Lane.HEAVY


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        pytest.param({"lane": "slow"}, "slow", id="unknown-lane"),
        pytest.param({"test_command": []}, "missing a required field", id="no-test-command"),
        pytest.param({"student_paths": []}, "missing a required field", id="no-student-paths"),
        pytest.param({"memory_mb": 0}, "positive", id="no-memory"),
        pytest.param({"cpus": 0}, "cpus", id="no-cpu"),
        pytest.param({"min_time_s": 200}, "min_time_s", id="min-above-max"),
    ],
)
def test_invalid_profile_is_rejected(overrides: dict[str, Any], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        RunnerProfile.from_json_data(profile_data(**overrides))
