"""PoC measurements: runs every example through the judge (make poc).

1. Verdicts: build each examples/<name>/ from scratch (cold), judge the starter and every
   submission in the warm image, compare with example.json. Times and peak memory.
2. Compile cache: the correct submission in the warm image and with the cache deleted.
3. Two slots at once: a heavy (Flutter) and a fast (Dart) check together vs alone.
4. Two-stage Flutter: does `dart test` run inside a Flutter project (SPEC §4)?

The report is Markdown, printed as it goes and saved with --output. The exit code is 1
when a verdict differs from the expected one.

    uv run python -m scripts.poc [--repeat N] [--output FILE] [EXAMPLE ...]
"""

import argparse
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import platform
import shlex
import statistics
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import docker
from docker.errors import ImageNotFound

from judge.config import REPO_ROOT, JudgeConfig, load_profile, read_env
from judge.core.profile import RunnerProfile
from judge.infra.image_builder import BuildResult, build_task_image, task_image_tag
from judge.infra.runner import JudgeResult, judge_zip
from judge.infra.sandbox import NodeSettings, Sandbox, SandboxLimits
from judge.packaging.submission import read_submission
from judge.packaging.task_package import read_task_package
from judge.packaging.zip_validator import ArchiveFile, validate_zip

EXAMPLES_DIR = REPO_ROOT / "examples"
STARTER = "starter"
# Where each profile keeps its compile cache inside a task image.
COMPILE_CACHES = {
    "dart": (".dart_tool/test", ".dart_tool/pub/bin"),
    "flutter": ("build/test_cache",),
}


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


class Report:
    """Markdown printed as it is written, and kept for --output."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str = "") -> None:
        print(line, flush=True)
        self.lines.append(line)

    def table(self, header: list[str], rows: list[list[str]]) -> None:
        self(f"| {' | '.join(header)} |")
        self(f"|{'---|' * len(header)}")
        for row in rows:
            self(f"| {' | '.join(row)} |")


@dataclass
class Built:
    example: Example
    profile: RunnerProfile
    build: BuildResult


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.poc", description=__doc__)
    parser.add_argument("examples", nargs="*", help="example folder names (default: all)")
    parser.add_argument("--repeat", type=int, default=3, help="runs per timing (median)")
    parser.add_argument("--output", type=Path, help="also save the report here")
    args = parser.parse_args(argv)

    config = JudgeConfig.from_env(read_env())
    node = dataclasses.replace(config.node, sample_memory=True)
    client = docker.from_env()
    examples = load_examples(args.examples or None)
    report = Report()
    _machine(report, client, config, examples)

    built: list[Built] = []
    mismatches = 0
    try:
        for example in examples:
            item, wrong = _verdicts(report, client, config, node, example)
            built.append(item)
            mismatches += wrong
        _compile_cache(report, client, config, node, built, args.repeat)
        _two_slots(report, config, node, built, args.repeat)
        if any(item.profile.slug == "flutter" for item in built):
            _two_stage(report, client, config, node)
    finally:
        for item in built:
            with contextlib.suppress(ImageNotFound):
                client.images.remove(item.build.task.image_tag, force=True)

    report()
    report("All verdicts as expected." if not mismatches else f"**{mismatches} unexpected!**")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(report.lines) + "\n")
        print(f"\nSaved to {args.output}", file=sys.stderr)
    return 1 if mismatches else 0


def _machine(
    report: Report, client: docker.DockerClient, config: JudgeConfig, examples: list[Example]
) -> None:
    info = client.info()
    images = sorted({config.base_image(load_profile(example.profile)) for example in examples})
    report("# PoC: judge measurements")
    report()
    report(f"- Date: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC")
    report(
        f"- Machine: {platform.machine()}, {os.cpu_count()} CPUs, "
        f"{info['MemTotal'] / 1024**3:.1f} GiB RAM"
    )
    report(
        f"- System: {info.get('OperatingSystem')}, kernel {info.get('KernelVersion')}, "
        f"cgroup v{info.get('CgroupVersion')}, Docker {info.get('ServerVersion')}"
    )
    report(f"- Images: {', '.join(images)}")
    report("- Peak RAM is sampled every 0.2 s, so very short spikes can be missed.")


def _verdicts(
    report: Report,
    client: docker.DockerClient,
    config: JudgeConfig,
    node: NodeSettings,
    example: Example,
) -> tuple[Built, int]:
    profile = load_profile(example.profile)
    data = example.task_zip()
    tag = task_image_tag(f"poc-{example.name}", hashlib.sha256(data).hexdigest())
    with contextlib.suppress(ImageNotFound):
        client.images.remove(tag, force=True)  # always measure a cold build

    package = read_task_package(validate_zip(io.BytesIO(data), config.task_limits).read())
    started = time.monotonic()
    build = build_task_image(
        client, package, profile, node, base_image=config.base_image(profile), tag=tag
    )
    build_s = time.monotonic() - started
    task = build.task
    report()
    report(f"## {example.name} ({example.profile})")
    report()
    report(
        f"Cold build {build_s:.1f} s; teacher's solution {build.solution_wall_ms / 1000:.1f} s "
        f"cold (peak {build.warm_up_peak_mb or '?'} MB), {build.warm_wall_ms / 1000:.1f} s warm. "
        f"Time limit {task.time_limit_s} s, "
        f"memory limit {profile.memory_mb} MB, {len(task.manifest.tests)} tests."
    )
    report()
    rows, mismatches = [], 0
    for name, expected in example.expected.items():
        archive = io.BytesIO(example.submission_zip(name))
        started = time.monotonic()
        result = judge_zip(client, task, profile, node, archive, config.submission_limits)
        total_s = time.monotonic() - started
        got = Expected(str(result.judgement.verdict), result.judgement.failed_test_index)
        mismatches += got != expected
        shown = got.verdict + (f" (test {got.failed_test})" if got.failed_test else "")
        mark = "✓" if got == expected else f"✗ {expected.verdict} {expected.failed_test or ''}"
        rows.append([name, shown, mark, *_run_columns(result, total_s)])
    report.table(["Submission", "Verdict", "Expected", "Tests run", "Total", "Peak RAM"], rows)
    return Built(example, profile, build), mismatches


def _compile_cache(
    report: Report,
    client: docker.DockerClient,
    config: JudgeConfig,
    node: NodeSettings,
    built: list[Built],
    repeat: int,
) -> None:
    report()
    report("## Compile cache")
    report()
    report(
        f"The correct submission in the warm image, and with the compile cache deleted first "
        f"(median of {repeat})."
    )
    report()
    rows = []
    for item in built:
        archive = validate_zip(
            io.BytesIO(item.example.submission_zip("ok")), config.submission_limits
        )
        files = read_submission(archive, item.profile.student_paths)
        caches = COMPILE_CACHES.get(item.profile.slug, ())
        test_command = shlex.join(item.profile.test_command)
        cold_command = f"rm -rf {' '.join(caches)} && {test_command}"
        warm = [_run_in_image(client, node, item, files, test_command) for _ in range(repeat)]
        cold = [_run_in_image(client, node, item, files, cold_command) for _ in range(repeat)]
        warm_s = statistics.median(seconds for seconds, _ in warm)
        cold_s = statistics.median(seconds for seconds, _ in cold)
        rows.append(
            [
                item.example.name,
                f"{warm_s:.1f} s, {_peak(warm)}",
                f"{cold_s:.1f} s, {_peak(cold)}",
                f"{cold_s / warm_s:.1f}x",
            ]
        )
    report.table(["Example", "Warm cache", "No cache", "Speed-up"], rows)


def _two_slots(
    report: Report, config: JudgeConfig, node: NodeSettings, built: list[Built], repeat: int
) -> None:
    heavy = next((item for item in built if item.profile.slug == "flutter"), None)
    fast = next((item for item in built if item.profile.slug == "dart"), None)
    if heavy is None or fast is None:
        return
    report()
    report("## Two slots at once")
    report()
    report(
        "The correct submission of each, alone and both at the same time (JUDGE_SLOTS="
        f"heavy:1,fast:1); median of {repeat}."
    )
    report()

    def judge(item: Built) -> float:
        client = docker.from_env()  # one client per thread
        archive = io.BytesIO(item.example.submission_zip("ok"))
        started = time.monotonic()
        judge_zip(client, item.build.task, item.profile, node, archive, config.submission_limits)
        return time.monotonic() - started

    alone = {item.example.name: [judge(item) for _ in range(repeat)] for item in (heavy, fast)}
    together: dict[str, list[float]] = {heavy.example.name: [], fast.example.name: []}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for _ in range(repeat):
            heavy_run, fast_run = pool.submit(judge, heavy), pool.submit(judge, fast)
            together[heavy.example.name].append(heavy_run.result())
            together[fast.example.name].append(fast_run.result())
    rows = []
    for name in (heavy.example.name, fast.example.name):
        alone_s, together_s = statistics.median(alone[name]), statistics.median(together[name])
        slowdown = f"{together_s / alone_s:.2f}x"
        rows.append([name, f"{alone_s:.1f} s", f"{together_s:.1f} s", slowdown])
    report.table(["Example", "Alone", "Together", "Slowdown"], rows)


TWO_STAGE_PUBSPEC = """name: probe
environment:
  sdk: ^3.0.0
dependencies:
  flutter:
    sdk: flutter
dev_dependencies:
  test: any
  flutter_test:
    sdk: flutter
"""
TWO_STAGE_FILES = {
    "pubspec.yaml": TWO_STAGE_PUBSPEC,
    "lib/logic.dart": "int add(int a, int b) => a + b;\n",
    "lib/with_flutter.dart": (
        "import 'package:flutter/widgets.dart';\n"
        "int twice(int x) => x * 2;\n"
        "Widget label(int x) => Text('$x', textDirection: TextDirection.ltr);\n"
    ),
    "test/logic_test.dart": (
        "import 'package:probe/logic.dart';\nimport 'package:test/test.dart';\n"
        "void main() { test('add', () => expect(add(2, 3), 5)); }\n"
    ),
    "test/with_flutter_test.dart": (
        "import 'package:probe/with_flutter.dart';\nimport 'package:test/test.dart';\n"
        "void main() { test('twice', () => expect(twice(2), 4)); }\n"
    ),
}
TWO_STAGE_SCRIPT = """
flutter pub get --offline > /dev/null 2>&1 || { echo "pub_get failed"; exit 1; }
t() {
    s=$(date +%s%N); "$@" > /dev/null 2>&1; c=$?
    echo "$c $(( ($(date +%s%N) - s) / 1000000 ))"
}
echo "dart_test_pure $(t dart test test/logic_test.dart)"
echo "dart_test_pure_again $(t dart test test/logic_test.dart)"
echo "flutter_test_pure $(t flutter test --no-pub test/logic_test.dart)"
echo "dart_test_importing_flutter $(t dart test test/with_flutter_test.dart)"
"""
TWO_STAGE_CHECKS = {
    "dart_test_pure": "`dart test`, logic without Flutter imports (first run)",
    "dart_test_pure_again": "`dart test`, the same again (cache warm)",
    "flutter_test_pure": "`flutter test`, the same logic test",
    "dart_test_importing_flutter": "`dart test`, logic in a file that imports Flutter",
}


def _two_stage(
    report: Report, client: docker.DockerClient, config: JudgeConfig, node: NodeSettings
) -> None:
    profile = load_profile("flutter")
    limits = SandboxLimits.for_profile(profile, node)
    files = [ArchiveFile(path, text.encode()) for path, text in TWO_STAGE_FILES.items()]
    command = ["bash", "-c", TWO_STAGE_SCRIPT]
    with Sandbox(client, config.base_image(profile), command, limits) as sandbox:
        sandbox.put_files(files)
        run = sandbox.run(600)
    results = dict(
        (parts[0], parts[1:]) for parts in (line.split() for line in run.stdout.splitlines())
    )
    report()
    report("## Two-stage Flutter: `dart test` inside a Flutter project")
    report()
    rows = []
    for key, label in TWO_STAGE_CHECKS.items():
        exit_code, millis = (results.get(key) or ["?", "0"])[:2]
        outcome = "passes" if exit_code == "0" else f"fails (exit {exit_code})"
        rows.append([label, outcome, f"{int(millis) / 1000:.1f} s"])
    report.table(["Check", "Result", "Time"], rows)


def _run_in_image(
    client: docker.DockerClient,
    node: NodeSettings,
    item: Built,
    files: list[ArchiveFile],
    command: str,
) -> tuple[float, int | None]:
    limits = SandboxLimits.for_profile(item.profile, node)
    with Sandbox(client, item.build.task.image_tag, ["sh", "-c", command], limits) as sandbox:
        sandbox.put_files(files)
        run = sandbox.run(item.profile.max_time_s)
    return run.wall_ms / 1000, run.peak_memory_mb


def _run_columns(result: JudgeResult, total_s: float) -> list[str]:
    peak = f"{result.peak_memory_mb} MB" if result.peak_memory_mb else "—"
    return [f"{result.wall_ms / 1000:.1f} s", f"{total_s:.1f} s", peak]


def _peak(runs: list[tuple[float, int | None]]) -> str:
    peaks = [peak for _, peak in runs if peak]
    return f"peak {max(peaks)} MB" if peaks else "peak ?"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
