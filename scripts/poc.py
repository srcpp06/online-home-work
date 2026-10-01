"""Runs every example through the judge and prints timings as Markdown (make poc).

For each examples/<name>/: build the task image from scratch (cold), then judge the
starter and every submission in the warm image, and compare each verdict with
example.json. The output is ready for docs/poc-results.md; the exit code is 1 when a
verdict differs from the expected one.

    uv run python -m scripts.poc [EXAMPLE ...]
"""

import contextlib
import hashlib
import io
import json
import os
import platform
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import docker
from docker.errors import ImageNotFound

from judge.config import REPO_ROOT, JudgeConfig, load_profile, read_env
from judge.infra.image_builder import build_task_image, task_image_tag
from judge.infra.runner import judge_zip
from judge.packaging.task_package import read_task_package
from judge.packaging.zip_validator import validate_zip

EXAMPLES_DIR = REPO_ROOT / "examples"
STARTER = "starter"


@dataclass(frozen=True)
class Expected:
    verdict: str
    failed_test: int | None = None


@dataclass(frozen=True)
class Example:
    name: str
    path: Path
    profile: str
    expected: dict[str, Expected]  # "starter" and every submission

    def task_zip(self) -> bytes:
        return zip_folder(self.path / "task")

    def submission_zip(self, name: str) -> bytes:
        if name == STARTER:
            return zip_folder(self.path / "task" / "starter")
        return zip_folder(self.path / "submissions" / name)


def zip_folder(folder: Path) -> bytes:
    """A zip of the folder's files with fixed timestamps: the same files, the same bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(folder).as_posix(), (2026, 1, 1, 0, 0, 0))
            archive.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def load_examples(names: list[str] | None = None) -> list[Example]:
    examples = []
    for path in sorted(EXAMPLES_DIR.glob("*/example.json")):
        if names and path.parent.name not in names:
            continue
        data = json.loads(path.read_text())
        expected = {STARTER: Expected(**data["starter"])}
        expected |= {name: Expected(**value) for name, value in data["submissions"].items()}
        examples.append(Example(path.parent.name, path.parent, data["profile"], expected))
    return examples


def main(argv: list[str]) -> int:
    config = JudgeConfig.from_env(read_env())
    client = docker.from_env()
    examples = load_examples(argv or None)
    info = client.info()
    images = sorted({config.base_image(load_profile(example.profile)) for example in examples})
    print("# PoC: judge timings\n")
    print(f"- Date: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC")
    print(
        f"- Machine: {platform.machine()}, {os.cpu_count()} CPUs, "
        f"{info['MemTotal'] / 1024**3:.1f} GiB RAM, Docker {info['ServerVersion']}"
    )
    print(f"- Images: {', '.join(images)}")
    mismatches = 0
    for example in examples:
        mismatches += _run_example(client, config, example)
    print(f"\n{'All verdicts as expected.' if not mismatches else f'{mismatches} unexpected!'}")
    return 1 if mismatches else 0


def _run_example(client: docker.DockerClient, config: JudgeConfig, example: Example) -> int:
    profile = load_profile(example.profile)
    data = example.task_zip()
    tag = task_image_tag(f"poc-{example.name}", hashlib.sha256(data).hexdigest())
    with contextlib.suppress(ImageNotFound):
        client.images.remove(tag, force=True)  # always measure a cold build

    package = read_task_package(validate_zip(io.BytesIO(data), config.task_limits).read())
    started = time.monotonic()
    build = build_task_image(
        client, package, profile, config.node, base_image=config.base_image(profile), tag=tag
    )
    build_s = time.monotonic() - started
    task = build.task
    print(f"\n## {example.name} ({example.profile})\n")
    print(
        f"Cold build: {build_s:.1f} s (teacher's solution {build.solution_wall_ms / 1000:.1f} s), "
        f"time limit {task.time_limit_s} s, {len(task.manifest.tests)} tests\n"
    )
    print("| Submission | Verdict | Expected | Tests run | Total |")
    print("|---|---|---|---|---|")
    mismatches = 0
    try:
        for name, expected in example.expected.items():
            archive = io.BytesIO(example.submission_zip(name))
            started = time.monotonic()
            result = judge_zip(
                client, task, profile, config.node, archive, config.submission_limits
            )
            total_s = time.monotonic() - started
            judgement = result.judgement
            got = Expected(str(judgement.verdict), judgement.failed_test_index)
            mismatches += got != expected
            shown = got.verdict + (f" (test {got.failed_test})" if got.failed_test else "")
            mark = "✓" if got == expected else f"✗ {expected.verdict} {expected.failed_test or ''}"
            run_s = result.wall_ms / 1000
            print(f"| {name} | {shown} | {mark} | {run_s:.1f} s | {total_s:.1f} s |")
    finally:
        with contextlib.suppress(ImageNotFound):
            client.images.remove(tag, force=True)
    return mismatches


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
