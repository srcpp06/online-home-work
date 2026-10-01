"""python -m judge.cli: error paths without Docker, the whole flow with it (marker: docker)."""

import contextlib
import json
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

import docker
import pytest
from docker.errors import ImageNotFound

from judge import cli
from judge.config import REPO_ROOT, read_env
from judge.packaging.zip_validator import ArchiveFile
from tests.judge.infra.support import cart_lib, cart_project


def example_env() -> dict[str, str]:
    return read_env(REPO_ROOT / ".env.example", environ={})


def write_zip(path: Path, files: list[ArchiveFile], folder: str = "") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for file in files:
            archive.writestr(folder + file.path, file.data)
    return path


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI reads .env.example values, whatever the developer's .env says."""
    monkeypatch.setattr(cli, "read_env", example_env)


def test_missing_settings_stop_the_cli(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, "read_env", dict)

    assert cli.main(["build", "task.zip", "--profile", "dart"]) == 1
    assert "missing settings" in capsys.readouterr().err


def test_unknown_profile_stops_the_cli(settings: None, capsys) -> None:
    assert cli.main(["build", "task.zip", "--profile", "cobol"]) == 1
    assert "unknown profile 'cobol'" in capsys.readouterr().err


def test_profile_is_required(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["build", "task.zip"])

    assert exit_info.value.code == 2
    assert "--profile" in capsys.readouterr().err


@pytest.fixture(scope="module")
def zips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    folder = tmp_path_factory.mktemp("zips")
    solution = [ArchiveFile(f"solution/{f.path}", f.data) for f in cart_lib("pass")]
    task_files = [*cart_project(), *solution]
    return {
        "task": write_zip(folder / "task.zip", task_files, "cart_task/"),
        "pass": write_zip(folder / "pass.zip", cart_lib("pass"), "cart/"),
        "fail": write_zip(folder / "fail.zip", cart_lib("fail_public"), "cart/"),
        "forbidden": write_zip(
            folder / "forbidden.zip",
            [ArchiveFile("lib/cart.dart", b"import 'dart:' 'io';\nclass Cart {}\n")],
        ),
        "no_hidden": write_zip(
            folder / "no_hidden.zip",
            [f for f in task_files if not f.path.startswith("test/hidden/")],
        ),
    }


@pytest.fixture(scope="module")
def built_tags() -> Iterator[list[str]]:
    tags: list[str] = []
    yield tags
    client = docker.from_env()
    for tag in tags:
        with contextlib.suppress(ImageNotFound):
            client.images.remove(tag, force=True)


@pytest.mark.docker
def test_cli_builds_once_and_judges(
    dart_base_image: str,
    settings: None,
    zips: dict[str, Path],
    built_tags: list[str],
    capsys,
) -> None:
    task = str(zips["task"])

    assert cli.main(["build", task, "--profile", "dart"]) == 0
    built = capsys.readouterr().out
    built_tags += re.findall(r"Built (\S+)", built)
    assert "Tests (4):" in built
    assert "3. Chegirma 10% chegirma qoʻllanadi  (hidden)" in built

    assert cli.main(["build", task, "--profile", "dart"]) == 0
    assert capsys.readouterr().out.startswith("Using ohw-task:local-dart-")

    assert cli.main(["run", task, str(zips["pass"]), "--profile", "dart"]) == 0
    output = capsys.readouterr().out
    assert "✓  4. Chegirma 0% chegirmada narx oʻzgarmaydi" in output
    assert "Verdict: accepted\nPassed: 4/4" in output


@pytest.mark.docker
def test_cli_json_result(
    dart_base_image: str, settings: None, zips: dict[str, Path], built_tags: list[str], capsys
) -> None:
    args = ["run", str(zips["task"]), str(zips["fail"]), "--profile", "dart", "--json"]

    assert cli.main(args) == 0
    captured = capsys.readouterr()
    built_tags += re.findall(r"Built (\S+)", captured.err)
    result = json.loads(captured.out)

    assert (result["verdict"], result["failed_test_index"]) == ("wrong_answer", 2)
    assert [r["status"] for r in result["results"]] == ["pass", "fail"]
    assert result["results"][1]["message"] == "Expected: <4000>\n  Actual: <2500>"


@pytest.mark.docker
def test_cli_shows_the_rejection(
    dart_base_image: str, settings: None, zips: dict[str, Path], built_tags: list[str], capsys
) -> None:
    assert cli.main(["run", str(zips["task"]), str(zips["forbidden"]), "--profile", "dart"]) == 0
    output = capsys.readouterr().out
    built_tags += re.findall(r"Built (\S+)", output)

    assert "Verdict: rejected" in output
    assert "Taqiqlangan import: dart:io — bu topshiriqda ruxsat etilmagan" in output


@pytest.mark.docker
def test_cli_explains_a_bad_task_and_a_missing_file(
    dart_base_image: str, settings: None, zips: dict[str, Path], capsys
) -> None:
    assert cli.main(["build", str(zips["no_hidden"]), "--profile", "dart"]) == 1
    assert "test/hidden papkasida test fayli" in capsys.readouterr().err

    missing = str(zips["task"].with_name("nope.zip"))
    assert cli.main(["run", str(zips["task"]), missing, "--profile", "dart"]) == 1
    assert "can't read" in capsys.readouterr().err
