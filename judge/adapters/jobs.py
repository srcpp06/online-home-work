"""Running one job: the database rows in, the judge core and Docker in the middle.

The only place where Django models meet judge.infra (CLAUDE.md, "Arxitektura"): the site
puts jobs on the queue, the worker (judge.adapters.worker) hands them to these functions.
"""

import io

import docker
from django.db import transaction
from django.utils import timezone
from docker.errors import ImageNotFound

from apps.submissions.models import Submission, SubmissionTestResult
from apps.tasks.models import TaskVersion
from judge.config import JudgeConfig
from judge.core.events import EventType, RunEvent
from judge.core.manifest import Manifest
from judge.core.profile import RunnerProfile
from judge.infra.image_builder import BuildFailed, build_task_image, task_image_tag
from judge.infra.runner import TaskImage, judge_zip
from judge.packaging.dart_imports import ImportRules
from judge.packaging.task_package import PackageInvalid, TaskPackage, read_task_package
from judge.packaging.zip_validator import ZipRejected, validate_zip


def run_build(client: docker.DockerClient, config: JudgeConfig, version: TaskVersion) -> None:
    """Build a version's image; the teacher reads the result on the version page."""
    profile = version.task.profile.judge_profile()
    try:
        package = _read_package(version, config)
    except (ZipRejected, PackageInvalid) as error:
        errors = error.errors if isinstance(error, PackageInvalid) else [str(error)]
        _build_failed(version, errors, "")
        return

    def on_log(text: str) -> None:
        TaskVersion.objects.filter(pk=version.pk).update(build_log=text)

    base_image = config.base_image(profile)
    tag = task_image_tag(version.pk, version.sha256)
    try:
        result = build_task_image(
            client, package, profile, config.node, base_image=base_image, tag=tag, on_log=on_log
        )
    except BuildFailed as error:
        _build_failed(version, error.errors, error.log)
        return
    task = result.task
    version.status = TaskVersion.Status.READY
    version.image_tag = tag
    version.manifest = task.manifest.to_json_data()
    version.import_rules = task.import_rules.to_json_data() if task.import_rules else None
    version.solution_wall_ms = result.solution_wall_ms
    version.warm_wall_ms = result.warm_wall_ms
    version.time_limit_s = task.time_limit_s
    version.runtime_info = f"{version.task.profile.title} {base_image.rpartition(':')[2]}"
    version.build_log = result.log
    version.build_errors = []
    version.built_at = timezone.now()
    version.save()


def run_judge(client: docker.DockerClient, config: JudgeConfig, submission: Submission) -> None:
    """Judge a submission, saving each test's result the moment its event arrives."""
    version = submission.task_version
    profile = version.task.profile.judge_profile()
    _ensure_image(client, config, version, profile)
    task = _task_image(version)
    visibility = [test.visibility for test in task.manifest.tests]

    with transaction.atomic():
        submission.results.all().delete()  # a rejudge starts clean
        Submission.objects.filter(pk=submission.pk).update(
            status=Submission.Status.RUNNING, started_at=timezone.now()
        )

    def on_event(event: RunEvent) -> None:
        if event.type not in (EventType.PASS, EventType.FAIL) or event.index is None:
            return
        SubmissionTestResult.objects.create(
            submission=submission,
            index=event.index,
            name=event.name,
            stage=event.stage,
            visibility=visibility[event.index - 1],
            status=event.type.value,
            duration_ms=event.duration_ms,
            message=event.message,
        )

    with submission.archive.open("rb") as archive:
        result = judge_zip(
            client, task, profile, config.node, archive, config.submission_limits, on_event
        )
    judgement = result.judgement
    Submission.objects.filter(pk=submission.pk).update(
        status=Submission.Status.FINISHED,
        verdict=judgement.verdict.value,
        tests_total=judgement.tests_total,
        tests_passed=judgement.tests_passed,
        failed_test_index=judgement.failed_test_index,
        failed_test_name=judgement.failed_test_name,
        public_message=result.public_message,
        internal_log=result.log,
        wall_ms=result.wall_ms,
        finished_at=timezone.now(),
    )


def _task_image(version: TaskVersion) -> TaskImage:
    if version.status != TaskVersion.Status.READY or not version.manifest:
        raise RuntimeError(f"version {version.pk} has no ready image to judge with")
    return TaskImage(
        image_tag=version.image_tag,
        manifest=Manifest.from_json_data(version.manifest),
        time_limit_s=version.time_limit_s or 0,
        memory_limit_mb=version.memory_limit_mb,
        import_rules=ImportRules.from_json_data(version.import_rules)
        if version.import_rules
        else None,
    )


def _ensure_image(
    client: docker.DockerClient, config: JudgeConfig, version: TaskVersion, profile: RunnerProfile
) -> None:
    """Nodes keep no state (SPEC §3.3, step 7): a node without the image builds it again
    from the stored package, under the same tag. The database stays the source of truth."""
    try:
        client.images.get(version.image_tag)
        return
    except ImageNotFound:
        pass
    package = _read_package(version, config)
    build_task_image(
        client,
        package,
        profile,
        config.node,
        base_image=config.base_image(profile),
        tag=version.image_tag,
    )


def _read_package(version: TaskVersion, config: JudgeConfig) -> TaskPackage:
    with version.package.open("rb") as source:
        data = source.read()
    return read_task_package(validate_zip(io.BytesIO(data), config.task_limits).read())


def _build_failed(version: TaskVersion, errors: list[str], log: str) -> None:
    version.status = TaskVersion.Status.BUILD_FAILED
    version.build_errors = errors
    version.build_log = log
    version.built_at = timezone.now()
    version.save(update_fields=["status", "build_errors", "build_log", "built_at"])
