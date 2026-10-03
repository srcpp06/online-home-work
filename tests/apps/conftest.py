from typing import Any

import pytest

from tests.apps.world import World, make_world


@pytest.fixture(autouse=True)
def fast_password_hashing(settings: Any) -> None:
    """Django's real hasher is slow on purpose (~0.1 s a password); tests make dozens."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def world(db: None) -> World:
    return make_world()
