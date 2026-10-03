"""scripts/create-env.sh: a new .env with a fresh secret key, never overwriting one."""

import os
import re
import shutil
import subprocess
from pathlib import Path

from judge.env import REPO_ROOT

SECRET_LINE = re.compile(r"^DJANGO_SECRET_KEY=(.*)$", re.MULTILINE)


def run_script(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- our own script
        [str(root / "scripts" / "create-env.sh"), *args],
        capture_output=True,
        text=True,
        check=False,
        env=None if env is None else {**os.environ, **env},
    )


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "scripts" / "create-env.sh", tmp_path / "scripts")
    shutil.copy2(REPO_ROOT / ".env.example", tmp_path)
    return tmp_path


def secret_of(env_file: Path) -> str:
    match = SECRET_LINE.search(env_file.read_text())
    assert match is not None
    return match.group(1)


def test_creates_env_with_a_strong_secret_and_the_example_values(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = run_script(root)

    assert result.returncode == 0, result.stderr
    secret = secret_of(root / ".env")
    assert len(secret) >= 50
    assert re.fullmatch(r"[A-Za-z0-9]+", secret)
    example = (root / ".env.example").read_text()
    assert (root / ".env").read_text() == SECRET_LINE.sub(f"DJANGO_SECRET_KEY={secret}", example)


def test_each_env_gets_its_own_secret(tmp_path: Path) -> None:
    first, second = make_repo(tmp_path / "a"), make_repo(tmp_path / "b")
    run_script(first)
    run_script(second)

    assert secret_of(first / ".env") != secret_of(second / ".env")


def test_never_overwrites_an_existing_env(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / ".env").write_text("DJANGO_SECRET_KEY=mine\n")

    result = run_script(root)

    assert result.returncode == 1
    assert (root / ".env").read_text() == "DJANGO_SECRET_KEY=mine\n"


def values(env_file: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if line and not line.startswith("#")
    )


def test_production_fills_in_the_server_values(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = run_script(root, "--production", "ohw.example.uz", env={"DOCKER_GID": "988"})

    assert result.returncode == 0, result.stderr
    env = values(root / ".env")
    password = env["POSTGRES_PASSWORD"]
    assert len(password) >= 30 and password.isalnum()
    assert env["DATABASE_URL"] == f"postgres://ohw:{password}@db:5432/ohw"
    assert env["DJANGO_DEBUG"] == "false"
    assert env["DJANGO_ALLOWED_HOSTS"] == "ohw.example.uz"
    assert env["SITE_DOMAIN"] == "ohw.example.uz"
    assert env["MEDIA_ROOT"] == "/data/media"
    assert env["DOCKER_GID"] == "988"
    assert env["GUNICORN_CMD_ARGS"] == "--workers 3 --timeout 120"
    assert len(env["DJANGO_SECRET_KEY"]) >= 50
    assert len(env["ADMIN_GATE_SECRET"]) >= 50
    assert env["ADMIN_GATE_SECRET"] not in (env["DJANGO_SECRET_KEY"], password)
    # Everything else keeps the example's value.
    assert env["JUDGE_SLOTS"] == values(root / ".env.example")["JUDGE_SLOTS"]


def test_production_needs_a_domain(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = run_script(root, "--production", "not a domain", env={"DOCKER_GID": "988"})

    assert result.returncode == 1
    assert "domain" in result.stderr
    assert not (root / ".env").exists()
