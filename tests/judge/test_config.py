from pathlib import Path

import pytest

from judge.config import (
    REPO_ROOT,
    REQUIRED,
    ConfigError,
    JudgeConfig,
    load_profile,
    read_env,
)
from judge.infra.sandbox import NodeSettings
from judge.packaging.zip_validator import ZipLimits

MB = 1024 * 1024


def example_env() -> dict[str, str]:
    """The settings every developer starts from."""
    return read_env(REPO_ROOT / ".env.example", environ={})


def test_env_file_is_read_and_the_environment_wins(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nJUDGE_RUNTIME=runc\nQUOTED='a b'\nDOUBLE=\"c\"\nEMPTY=\nSPACED = x \n"
    )

    values = read_env(env_file, environ={"JUDGE_RUNTIME": "runsc"})

    assert values == {
        "JUDGE_RUNTIME": "runsc",
        "QUOTED": "a b",
        "DOUBLE": "c",
        "EMPTY": "",
        "SPACED": "x",
    }


def test_missing_env_file_is_fine(tmp_path: Path) -> None:
    assert read_env(tmp_path / ".env", environ={"A": "1"}) == {"A": "1"}


def test_broken_env_line_is_reported(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("JUDGE_RUNTIME=runc\nnot a setting\n")

    with pytest.raises(ConfigError, match=r"\.env:2: expected NAME=value"):
        read_env(env_file, environ={})


def test_env_example_gives_a_complete_config() -> None:
    config = JudgeConfig.from_env(example_env())

    assert config.node == NodeSettings(cpu_shares=512, max_output_bytes=512 * 1024, runtime="runc")
    assert config.submission_limits == ZipLimits(5 * MB, 20 * MB, 500)
    assert config.task_limits == ZipLimits(50 * MB, 200 * MB, 5000)


def test_every_missing_setting_is_named_at_once() -> None:
    with pytest.raises(ConfigError) as error:
        JudgeConfig.from_env({"JUDGE_RUNTIME": "runc"})

    message = str(error.value)
    assert all(name in message for name in REQUIRED if name != "JUDGE_RUNTIME")
    assert ".env.example" in message


@pytest.mark.parametrize(
    ("value", "problem"),
    [("five", "whole number"), ("2.5", "whole number"), ("0", "positive"), ("-1", "positive")],
)
def test_bad_numbers_are_reported(value: str, problem: str) -> None:
    with pytest.raises(ConfigError, match=f"SUBMISSION_MAX_FILES must be .*{problem}"):
        JudgeConfig.from_env({**example_env(), "SUBMISSION_MAX_FILES": value})


def test_base_image_is_filled_in_from_the_settings() -> None:
    config = JudgeConfig.from_env({**example_env(), "DART_VERSION": "9.9.9"})

    assert config.base_image(load_profile("dart")) == "ohw-base-dart:9.9.9"
    assert config.base_image(load_profile("flutter")).startswith("ohw-base-flutter:")


def test_base_image_without_its_setting_is_reported() -> None:
    env = {name: value for name, value in example_env().items() if name != "FLUTTER_VERSION"}

    with pytest.raises(ConfigError, match="needs the setting FLUTTER_VERSION"):
        JudgeConfig.from_env(env).base_image(load_profile("flutter"))


@pytest.mark.parametrize("slug", ["dart", "flutter"])
def test_shipped_profiles_load(slug: str) -> None:
    assert load_profile(slug).slug == slug


@pytest.mark.parametrize("slug", ["python", "../profiles/dart", "Dart", ""])
def test_unknown_profile_lists_the_available_ones(slug: str) -> None:
    with pytest.raises(ConfigError, match="available: dart, flutter"):
        load_profile(slug)
