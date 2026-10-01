"""Command-line judge without Django, for the PoC and for debugging.

    python -m judge.cli build TASK_ZIP --profile dart [--rebuild]
    python -m judge.cli run TASK_ZIP SUBMISSION_ZIP --profile dart [--json] [--log]

Settings come from .env and the environment (see .env.example). A task image is tagged
from the zip, the profile and the base image, and describes itself in its label, so
`run` builds only when that exact image is missing.
"""

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException

from judge.config import ConfigError, JudgeConfig, load_profile, read_env
from judge.core.events import EventType, RunEvent
from judge.core.manifest import Visibility
from judge.core.profile import RunnerProfile
from judge.infra.image_builder import (
    BuildFailed,
    BuildResult,
    build_task_image,
    load_build_result,
    task_image_tag,
)
from judge.infra.runner import JudgeResult, judge_zip
from judge.packaging.task_package import PackageInvalid, read_task_package
from judge.packaging.zip_validator import ZipRejected, validate_zip


class CliError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = JudgeConfig.from_env(read_env())
        profile = load_profile(args.profile)
        client = _docker()
        build = _ensure_build(client, config, profile, args.task, args.rebuild, args.json)
        if args.command == "run":
            _run(client, config, profile, build, args)
    except (ConfigError, CliError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m judge.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build the image of a task")
    run = commands.add_parser("run", help="judge a student's zip (builds the task if needed)")
    for command in (build, run):
        command.add_argument("task", type=Path, help="the teacher's task zip")
    run.add_argument("submission", type=Path, help="the student's zip")
    for command in (build, run):
        command.add_argument("--profile", required=True, help="runner profile, e.g. dart, flutter")
        command.add_argument(
            "--rebuild", action="store_true", help="build even if the image exists"
        )
    build.set_defaults(json=False)
    run.add_argument("--json", action="store_true", help="print the result as JSON")
    run.add_argument("--log", action="store_true", help="print the teacher's log too")
    return parser


def _docker() -> docker.DockerClient:
    try:
        client = docker.from_env()
        client.ping()
    except DockerException as error:
        raise CliError(f"Docker is not available: {error}") from None
    return client


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CliError(f"can't read {path}: {error.strerror}") from None


def _ensure_build(
    client: docker.DockerClient,
    config: JudgeConfig,
    profile: RunnerProfile,
    task_zip: Path,
    rebuild: bool,
    quiet: bool,
) -> BuildResult:
    # Progress goes to stderr when stdout is reserved for JSON.
    report = sys.stderr if quiet else sys.stdout
    data = _read(task_zip)
    base_image = config.base_image(profile)
    digest = hashlib.sha256(data + b"\0" + base_image.encode()).hexdigest()
    tag = task_image_tag(f"local-{profile.slug}", digest)
    existing = None if rebuild else load_build_result(client, tag)
    if existing is not None:
        print(f"Using {tag}", file=report)
        return existing

    try:
        package = read_task_package(validate_zip(io.BytesIO(data), config.task_limits).read())
    except ZipRejected as error:
        raise CliError(f"{task_zip}: {error}") from None
    except PackageInvalid as error:
        raise CliError(f"{task_zip}:\n" + "\n".join(f"  - {e}" for e in error.errors)) from None

    print(f"Building {tag} from {base_image} ...", file=report)
    started = time.monotonic()
    try:
        result = build_task_image(
            client, package, profile, config.node, base_image=base_image, tag=tag
        )
    except BuildFailed as error:
        print(error.log, file=sys.stderr)
        raise CliError("build failed:\n" + "\n".join(f"  - {e}" for e in error.errors)) from None
    task = result.task
    print(f"Built {tag} in {time.monotonic() - started:.1f} s", file=report)
    print(
        f"Solution: {result.solution_wall_ms / 1000:.1f} s, time limit: {task.time_limit_s} s",
        file=report,
    )
    print(f"Tests ({len(task.manifest.tests)}):", file=report)
    for index, test in enumerate(task.manifest.tests, start=1):
        print(f"  {index:>2}. {test.name}  ({test.visibility})", file=report)
    return result


def _run(
    client: docker.DockerClient,
    config: JudgeConfig,
    profile: RunnerProfile,
    build: BuildResult,
    args: argparse.Namespace,
) -> None:
    hidden = {
        index
        for index, test in enumerate(build.task.manifest.tests, start=1)
        if test.visibility == Visibility.HIDDEN
    }

    def show(event: RunEvent) -> None:
        if event.type not in (EventType.PASS, EventType.FAIL):
            return
        mark = "✓" if event.type == EventType.PASS else "✗"
        where = "  [hidden]" if event.index in hidden else ""
        print(f"  {mark} {event.index:>2}. {event.name}  ({event.duration_ms} ms){where}")
        for line in event.message.splitlines():
            print(f"         {line}")

    archive = io.BytesIO(_read(args.submission))
    result = judge_zip(
        client,
        build.task,
        profile,
        config.node,
        archive,
        config.submission_limits,
        on_event=None if args.json else show,
    )
    if args.json:
        print(json.dumps(_as_json(result, build), ensure_ascii=False, indent=2))
    else:
        _print_summary(result)
    if args.log:
        print(result.log, file=sys.stderr if args.json else sys.stdout)


def _print_summary(result: JudgeResult) -> None:
    judgement = result.judgement
    line = f"Verdict: {judgement.verdict}"
    if judgement.failed_test_index:
        line += (
            f" — test {judgement.failed_test_index} of {judgement.tests_total}"
            f" ({judgement.failed_test_name})"
        )
    print(f"{line}\nPassed: {judgement.tests_passed}/{judgement.tests_total}")
    print(f"Time: {result.wall_ms / 1000:.1f} s")
    for text in (result.public_message, result.compile_error, judgement.detail):
        if text:
            print(text)


def _as_json(result: JudgeResult, build: BuildResult) -> dict[str, Any]:
    judgement = result.judgement
    return {
        "verdict": str(judgement.verdict),
        "tests_total": judgement.tests_total,
        "tests_passed": judgement.tests_passed,
        "failed_test_index": judgement.failed_test_index,
        "failed_test_name": judgement.failed_test_name,
        "wall_ms": result.wall_ms,
        "public_message": result.public_message,
        "compile_error": result.compile_error,
        "detail": judgement.detail,
        "results": [
            {
                "index": event.index,
                "name": event.name,
                "status": str(event.type),
                "duration_ms": event.duration_ms,
                "message": event.message,
            }
            for event in result.results
        ],
        "task": {
            "image_tag": build.task.image_tag,
            "time_limit_s": build.task.time_limit_s,
            "solution_wall_ms": build.solution_wall_ms,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
