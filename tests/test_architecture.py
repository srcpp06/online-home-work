"""Dependency rules between judge layers (CLAUDE.md, "Arxitektura").

Dependencies point inwards: core depends on nothing else in judge, parsers and
packaging use only core, Docker lives only in infra and Django only in adapters.
judge/env.py imports nothing from the project: the Django settings read .env through it.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGE_DIR = REPO_ROOT / "judge"

_OUTER = ("judge.infra", "judge.adapters", "judge.cli")
# The Django project: only the adapters may use it.
_WEB = ("django", "config", "apps")

# Layer (first package under judge) -> module prefixes it must never import.
LAYER_RULES: dict[str, tuple[str, ...]] = {
    "core": (*_WEB, "docker", "judge.parsers", "judge.packaging", *_OUTER),
    "parsers": (*_WEB, "docker", "judge.packaging", *_OUTER),
    "packaging": (*_WEB, "docker", "judge.parsers", *_OUTER),
    "infra": (*_WEB, "judge.adapters", "judge.cli"),
    "adapters": (),
}
# judge/__init__.py, judge/cli.py, judge/config.py, judge/env.py: they run without Django.
DEFAULT_RULE = (*_WEB, "judge.adapters")


def module_name(path: Path) -> str:
    parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(source: str, module: str, is_package: bool) -> set[tuple[str, int]]:
    """Return absolute names of everything the source imports, with line numbers."""
    package = module if is_package else module.rpartition(".")[0]
    found: set[tuple[str, int]] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*base_parts, node.module] if node.module else base_parts)
            else:
                base = node.module or ""
            found.add((base, node.lineno))
            # `from judge import infra` imports a submodule, not just a name.
            found.update((f"{base}.{alias.name}", node.lineno) for alias in node.names)
    return found


def forbidden_for(module: str) -> tuple[str, ...]:
    parts = module.split(".")
    if len(parts) > 1 and parts[1] in LAYER_RULES:
        return LAYER_RULES[parts[1]]
    return DEFAULT_RULE


def matches(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def judge_files() -> list[Path]:
    return sorted(JUDGE_DIR.rglob("*.py"))


@pytest.mark.parametrize("path", judge_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_judge_module_respects_layer_rules(path: Path) -> None:
    module = module_name(path)
    imports = imported_modules(path.read_text(), module, path.name == "__init__.py")
    violations = sorted(
        f"line {line}: imports {name}"
        for name, line in imports
        for prefix in forbidden_for(module)
        if matches(name, prefix)
    )
    assert not violations, f"{module} breaks the dependency rule:\n" + "\n".join(violations)


def test_every_judge_layer_has_a_rule() -> None:
    layers = {p.name for p in JUDGE_DIR.iterdir() if (p / "__init__.py").exists()}
    assert layers == set(LAYER_RULES)


@pytest.mark.parametrize(
    ("source", "module", "is_package", "expected"),
    [
        ("import docker.errors", "judge.core.x", False, "docker.errors"),
        ("from django.db import models", "judge.parsers.x", False, "django.db"),
        ("from ..infra import runner", "judge.core.x", False, "judge.infra.runner"),
        ("from .. import adapters", "judge.core.x", False, "judge.adapters"),
        ("from ..adapters.repo import Repo", "judge.core", True, "judge.adapters.repo"),
        ("from . import verdict", "judge.core", True, "judge.core.verdict"),
    ],
)
def test_imported_modules_resolves_absolute_and_relative_imports(
    source: str, module: str, is_package: bool, expected: str
) -> None:
    names = {name for name, _ in imported_modules(source, module, is_package)}
    assert expected in names


def test_env_module_imports_nothing_from_the_project() -> None:
    path = JUDGE_DIR / "env.py"
    imports = imported_modules(path.read_text(), "judge.env", is_package=False)
    project = sorted(
        name for name, _ in imports if name.split(".")[0] in ("judge", "config", "apps")
    )
    assert not project, f"judge.env must stay dependency-free: {project}"
