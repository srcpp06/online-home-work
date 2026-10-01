"""Shared helpers for the Docker tests: fixture packages, profiles, builds."""

import contextlib
from pathlib import Path

import docker
from docker.errors import ImageNotFound

from judge import config
from judge.core.profile import RunnerProfile
from judge.infra.image_builder import BuildResult, build_task_image, task_image_tag
from judge.infra.runner import TaskImage
from judge.infra.sandbox import NodeSettings
from judge.packaging.task_package import TaskPackage, read_task_package
from judge.packaging.zip_validator import ArchiveFile

REPO_ROOT = Path(__file__).resolve().parents[3]
DART_FIXTURES = REPO_ROOT / "tests" / "judge" / "parsers" / "fixtures" / "dart_json"
INFRA_FIXTURES = Path(__file__).parent / "fixtures"
FLUTTER_FIXTURES = INFRA_FIXTURES / "flutter_counter"
NODE = NodeSettings(cpu_shares=512, max_output_bytes=512 * 1024)


def load_profile(slug: str) -> RunnerProfile:
    return config.load_profile(slug)


def files_under(folder: Path, prefix: str = "") -> list[ArchiveFile]:
    return [
        ArchiveFile(prefix + path.relative_to(folder).as_posix(), path.read_bytes())
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    ]


def cart_lib(name: str) -> list[ArchiveFile]:
    """A student lib/ for the cart task: recorded parser solutions or runner extras."""
    for solutions in (DART_FIXTURES / "solutions", INFRA_FIXTURES / "cart_solutions"):
        if (solutions / name).is_dir():
            return files_under(solutions / name / "lib", prefix="lib/")
    raise LookupError(name)


def cart_project() -> list[ArchiveFile]:
    """The cart task without a solution; the builder generates its own combined file."""
    return [
        file
        for file in files_under(DART_FIXTURES / "project")
        if file.path != "test/_ohw_all_test.dart"
    ]


def dart_package(solution: str, pubspec: bytes | None = None) -> TaskPackage:
    project = cart_project()
    if pubspec is not None:
        project = [f for f in project if f.path != "pubspec.yaml"]
        project.append(ArchiveFile("pubspec.yaml", pubspec))
    solution_files = [
        ArchiveFile(f"solution/{file.path}", file.data) for file in cart_lib(solution)
    ]
    return read_task_package([*project, *solution_files])


def flutter_lib(name: str) -> list[ArchiveFile]:
    return files_under(FLUTTER_FIXTURES / "solutions" / name / "lib", prefix="lib/")


def flutter_package() -> TaskPackage:
    solution = [ArchiveFile(f"solution/{f.path}", f.data) for f in flutter_lib("pass")]
    return read_task_package([*files_under(FLUTTER_FIXTURES / "package"), *solution])


def build(
    client: docker.DockerClient, package: TaskPackage, slug: str, base_image: str, name: str
) -> BuildResult:
    tag = task_image_tag(0, f"test{name}".ljust(12, "0"))
    return build_task_image(
        client, package, load_profile(slug), NODE, base_image=base_image, tag=tag
    )


def task_image(result: BuildResult) -> TaskImage:
    return result.task


def remove_image(client: docker.DockerClient, tag: str) -> None:
    with contextlib.suppress(ImageNotFound):
        client.images.remove(tag, force=True)
