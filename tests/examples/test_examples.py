"""Every example submission gets the verdict its example.json promises (marker: docker).

The examples double as teacher templates, so this also proves each template builds and
that each starter compiles against its tests.
"""

import contextlib
import dataclasses
import hashlib
import io
from collections.abc import Iterator

import docker
import pytest
from docker.errors import ImageNotFound

from judge.config import REPO_ROOT, JudgeConfig, load_profile, read_env
from judge.infra.image_builder import BuildResult, build_task_image, task_image_tag
from judge.infra.runner import judge_zip
from judge.packaging.task_package import read_task_package
from judge.packaging.zip_validator import validate_zip
from scripts.poc import Example, Expected, load_examples

pytestmark = pytest.mark.docker

EXAMPLES = load_examples()
CASES = [(example, name) for example in EXAMPLES for name in example.expected]
# A timeout case waits for the time limit; a short one keeps the test quick.
TIMEOUT_LIMIT_S = 10


def config() -> JudgeConfig:
    return JudgeConfig.from_env(read_env(REPO_ROOT / ".env.example"))


@pytest.fixture(scope="module")
def builds(docker_client: docker.DockerClient) -> Iterator[dict[str, BuildResult]]:
    built: dict[str, BuildResult] = {}
    yield built
    for build in built.values():
        with contextlib.suppress(ImageNotFound):
            docker_client.images.remove(build.task.image_tag, force=True)


def build_of(
    client: docker.DockerClient, builds: dict[str, BuildResult], example: Example
) -> BuildResult:
    if example.name not in builds:
        settings, profile = config(), load_profile(example.profile)
        base_image = settings.base_image(profile)
        try:
            client.images.get(base_image)
        except ImageNotFound:
            pytest.skip(f"{base_image} is not built: run `make base-images`")
        data = example.task_zip()
        tag = task_image_tag(f"test-{example.name}", hashlib.sha256(data).hexdigest())
        package = read_task_package(validate_zip(io.BytesIO(data), settings.task_limits).read())
        builds[example.name] = build_task_image(
            client, package, profile, settings.node, base_image=base_image, tag=tag
        )
    return builds[example.name]


def test_examples_are_found() -> None:
    assert {example.name for example in EXAMPLES} >= {"dart-cart", "flutter-todo"}
    assert all("ok" in example.expected for example in EXAMPLES)


@pytest.mark.parametrize(
    ("example", "submission"), CASES, ids=[f"{e.name}-{name}" for e, name in CASES]
)
def test_submission_gets_the_expected_verdict(
    docker_client: docker.DockerClient,
    builds: dict[str, BuildResult],
    example: Example,
    submission: str,
) -> None:
    expected = example.expected[submission]
    task = build_of(docker_client, builds, example).task
    if expected.verdict == "time_limit":
        task = dataclasses.replace(task, time_limit_s=TIMEOUT_LIMIT_S)
    settings = config()

    result = judge_zip(
        docker_client,
        task,
        load_profile(example.profile),
        settings.node,
        io.BytesIO(example.submission_zip(submission)),
        settings.submission_limits,
    )

    judgement = result.judgement
    assert Expected(str(judgement.verdict), judgement.failed_test_index) == expected, result.log
