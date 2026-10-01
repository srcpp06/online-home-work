"""Fixtures for tests that need a Docker daemon and the profile base images."""

import os
from pathlib import Path

import docker
import pytest
from docker.errors import DockerException, ImageNotFound

REPO_ROOT = Path(__file__).resolve().parents[3]


def pinned_version(name: str) -> str:
    """A version from the environment, else the pinned default in .env.example."""
    if os.environ.get(name):
        return os.environ[name]
    for line in (REPO_ROOT / ".env.example").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    raise LookupError(f"{name} is not in .env.example")


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as error:
        pytest.skip(f"Docker is not available: {error}")
    return client


def base_image(client: docker.DockerClient, profile: str, version_name: str) -> str:
    tag = f"ohw-base-{profile}:{pinned_version(version_name)}"
    try:
        client.images.get(tag)
    except ImageNotFound:
        pytest.skip(f"{tag} is not built: run `make base-images PROFILES={profile}`")
    return tag


@pytest.fixture(scope="session")
def dart_base_image(docker_client: docker.DockerClient) -> str:
    return base_image(docker_client, "dart", "DART_VERSION")


@pytest.fixture(scope="session")
def flutter_base_image(docker_client: docker.DockerClient) -> str:
    return base_image(docker_client, "flutter", "FLUTTER_VERSION")
