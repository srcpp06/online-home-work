"""The CSS tokens are the ones docs/UI.md §2 defines, value for value."""

import re

from apps.ui.tokens import color_tokens
from judge.env import REPO_ROOT

UI_ROW = re.compile(r"^\| `--(?P<name>[a-z0-9-]+)` \| `(?P<hex>#[0-9A-Fa-f]{6})` \|", re.MULTILINE)


def test_css_colours_match_ui_md() -> None:
    documented = {
        m["name"]: m["hex"].upper()
        for m in UI_ROW.finditer((REPO_ROOT / "docs" / "UI.md").read_text())
    }

    assert len(documented) == 10
    assert color_tokens() == documented
