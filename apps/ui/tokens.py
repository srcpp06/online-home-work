"""The colour tokens as written in assets/source.css (docs/UI.md §2)."""

import re
from pathlib import Path

SOURCE_CSS = Path(__file__).resolve().parents[2] / "assets" / "source.css"
_ROOT_BLOCK = re.compile(r"^:root\s*\{(?P<body>[^}]*)\}", re.MULTILINE)
_COLOR = re.compile(r"--(?P<name>[a-z0-9-]+):\s*(?P<hex>#[0-9a-fA-F]{6})\s*;")


def color_tokens(source: Path = SOURCE_CSS) -> dict[str, str]:
    """Token name (without --) -> hex in upper case, in file order."""
    match = _ROOT_BLOCK.search(source.read_text())
    if match is None:
        raise ValueError(f"{source} has no :root block")
    return {m["name"]: m["hex"].upper() for m in _COLOR.finditer(match["body"])}
