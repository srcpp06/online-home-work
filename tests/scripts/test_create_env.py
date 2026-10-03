"""scripts/create-env.sh: a new .env with a fresh secret key, never overwriting one."""

import re
import shutil
import subprocess
from pathlib import Path

from judge.env import REPO_ROOT

SECRET_LINE = re.compile(r"^DJANGO_SECRET_KEY=(.*)$", re.MULTILINE)


def run_script(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- our own script
        [str(root / "scripts" / "create-env.sh")], capture_output=True, text=True, check=False
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
