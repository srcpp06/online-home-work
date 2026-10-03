"""Every Docker connection waits long enough for the slowest API call."""

import re
from pathlib import Path

import pytest

from judge.infra import docker_client

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_the_client_waits_for_a_slow_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Committing a Flutter container took over the SDK's default 60 s on a slow disk."""
    seen: dict[str, object] = {}

    class FakeClient:
        def ping(self) -> bool:
            return True

    def from_env(**kwargs: object) -> FakeClient:
        seen.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(docker_client.docker, "from_env", from_env)

    docker_client.connect()

    assert seen["timeout"] == docker_client.API_TIMEOUT_S >= 600


def test_nothing_else_opens_its_own_connection() -> None:
    direct = re.compile(r"\bdocker\.(from_env|DockerClient)\(")
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for folder in ("judge", "apps", "tests")
        for path in (REPO_ROOT / folder).rglob("*.py")
        if path.name != "test_docker_client.py"
        and path != REPO_ROOT / "judge/infra/docker_client.py"
        and direct.search(path.read_text())
    ]

    assert offenders == []
