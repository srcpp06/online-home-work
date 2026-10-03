import json

from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.infra.image_builder import BUILD_LABEL, BuildResult
from judge.infra.runner import TaskImage
from judge.packaging.dart_imports import ImportRules

TASK = TaskImage(
    image_tag="ohw-task:7-0123456789ab",
    manifest=Manifest(
        (
            ManifestTest("Savat boʻsh", 1, Visibility.PUBLIC),
            ManifestTest("Chegirma", 1, Visibility.HIDDEN),
        )
    ),
    time_limit_s=29,
    memory_limit_mb=512,
    import_rules=ImportRules("cart", frozenset({"cart", "equatable"}), frozenset({"io"})),
)


def test_task_image_survives_json() -> None:
    data = json.loads(json.dumps(TASK.to_json_data()))

    assert TaskImage.from_json_data(data) == TASK


def test_task_image_without_import_rules_survives_json() -> None:
    task = TaskImage(TASK.image_tag, TASK.manifest, time_limit_s=20)

    assert TaskImage.from_json_data(task.to_json_data()) == task


def test_build_label_keeps_uzbek_text_readable() -> None:
    label = BuildResult(
        TASK, solution_wall_ms=11_500, warm_wall_ms=1_500, log="not in the label"
    ).label()

    assert set(label) == {BUILD_LABEL}
    assert json.loads(label[BUILD_LABEL])["warm_wall_ms"] == 1_500
    assert "Savat boʻsh" in label[BUILD_LABEL]
    assert "not in the label" not in label[BUILD_LABEL]


def test_build_log_tells_the_watcher_each_step() -> None:
    from judge.infra.image_builder import _BuildLog
    from judge.infra.sandbox import ContainerRun

    seen: list[str] = []
    log = _BuildLog(seen.append)
    run = ContainerRun(
        exit_code=0,
        timed_out=False,
        oom_killed=False,
        output_limit_exceeded=False,
        stopped_early=False,
        wall_ms=1200,
        stdout="",
        stderr="",
    )

    log.running("dart pub get")
    log.add("dart pub get", run, "Got dependencies!")

    assert seen[0].endswith("$ dart pub get  (running)\n")
    assert "Got dependencies!" in seen[1]
    assert "(running)" not in seen[1]
