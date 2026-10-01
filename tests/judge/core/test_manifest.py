import pytest

from judge.core.manifest import Manifest, ManifestTest, Visibility

PUBLIC = Visibility.PUBLIC
HIDDEN = Visibility.HIDDEN


def test_two_stage_manifest_keeps_run_order() -> None:
    tests = (
        ManifestTest("savat bo'sh", 1, PUBLIC),
        ManifestTest("chegirma", 1, HIDDEN),
        ManifestTest("tugma", 2, PUBLIC),
        ManifestTest("ro'yxat", 2, HIDDEN),
    )

    assert Manifest(tests).tests == tests


def test_manifest_needs_at_least_one_test() -> None:
    with pytest.raises(ValueError, match="at least one test"):
        Manifest(())


@pytest.mark.parametrize(
    "tests",
    [
        pytest.param(
            (ManifestTest("b", 2, PUBLIC), ManifestTest("a", 1, PUBLIC)),
            id="stage-2-before-stage-1",
        ),
        pytest.param(
            (ManifestTest("b", 1, HIDDEN), ManifestTest("a", 1, PUBLIC)),
            id="hidden-before-public",
        ),
    ],
)
def test_manifest_rejects_wrong_order(tests: tuple[ManifestTest, ...]) -> None:
    with pytest.raises(ValueError, match="ordered by stage"):
        Manifest(tests)


def test_test_name_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="name"):
        ManifestTest("", 1, PUBLIC)


def test_test_stage_starts_at_one() -> None:
    with pytest.raises(ValueError, match="stage"):
        ManifestTest("a", 0, PUBLIC)


def test_json_round_trip() -> None:
    manifest = Manifest((ManifestTest("a", 1, PUBLIC), ManifestTest("b", 2, HIDDEN)))

    data = manifest.to_json_data()

    assert data == {
        "tests": [
            {"name": "a", "stage": 1, "visibility": "public"},
            {"name": "b", "stage": 2, "visibility": "hidden"},
        ]
    }
    assert Manifest.from_json_data(data) == manifest


def test_from_json_data_rejects_unknown_visibility() -> None:
    with pytest.raises(ValueError, match="secret"):
        Manifest.from_json_data({"tests": [{"name": "a", "stage": 1, "visibility": "secret"}]})
