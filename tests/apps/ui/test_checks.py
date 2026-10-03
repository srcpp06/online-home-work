"""ui.W001: developers hear about a missing app.css instead of seeing unstyled pages."""

from pathlib import Path
from typing import Any

import pytest

from apps.ui import checks


@pytest.fixture
def missing_css(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checks, "APP_CSS", checks.REPO_ROOT / "static" / "css" / "no-such.css")


def test_missing_css_is_a_warning_in_development(missing_css: None, settings: Any) -> None:
    settings.DEBUG = True

    [warning] = checks.built_css_exists()

    assert warning.id == "ui.W001"
    assert "make css" in warning.hint


def test_production_does_not_warn(missing_css: None, settings: Any) -> None:
    settings.DEBUG = False

    assert checks.built_css_exists() == []


def test_built_css_is_fine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings: Any) -> None:
    css = tmp_path / "app.css"
    css.write_text("")
    monkeypatch.setattr(checks, "APP_CSS", css)
    settings.DEBUG = True

    assert checks.built_css_exists() == []
