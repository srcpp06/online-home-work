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
    label = BuildResult(TASK, solution_wall_ms=11_500, log="not in the label").label()

    assert set(label) == {BUILD_LABEL}
    assert "Savat boʻsh" in label[BUILD_LABEL]
    assert "not in the label" not in label[BUILD_LABEL]
