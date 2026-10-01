import pytest

from judge.core.manifest import Visibility
from judge.packaging.task_package import (
    PackageInvalid,
    TaskPackage,
    is_junk,
    read_task_package,
    visibility_of,
)
from judge.packaging.zip_validator import ArchiveFile

VALID = {
    "pubspec.yaml": b"name: cart",
    "solution/lib/cart.dart": b"class Cart {}",
    "test/public/01_cart_test.dart": b"void main() {}",
    "test/hidden/02_discount_test.dart": b"void main() {}",
}


def files(entries: dict[str, bytes]) -> list[ArchiveFile]:
    return [ArchiveFile(path, data) for path, data in entries.items()]


def read(entries: dict[str, bytes]) -> TaskPackage:
    return read_task_package(files(entries))


def errors_of(entries: dict[str, bytes]) -> list[str]:
    with pytest.raises(PackageInvalid) as error:
        read(entries)
    return error.value.errors


def test_valid_package_is_split_into_image_files_solution_and_tests() -> None:
    package = read(VALID)

    assert [f.path for f in package.project_files] == [
        "pubspec.yaml",
        "test/public/01_cart_test.dart",
        "test/hidden/02_discount_test.dart",
    ]
    assert package.solution_files == (ArchiveFile("lib/cart.dart", b"class Cart {}"),)
    assert package.test_files == ("public/01_cart_test.dart", "hidden/02_discount_test.dart")


def test_tests_run_public_first_then_by_file_name() -> None:
    package = read(
        {
            **VALID,
            "test/hidden/01_a_test.dart": b"",
            "test/public/02_b_test.dart": b"",
            "test/public/sub/00_c_test.dart": b"",
        }
    )

    assert package.test_files == (
        "public/01_cart_test.dart",
        "public/02_b_test.dart",
        "public/sub/00_c_test.dart",
        "hidden/01_a_test.dart",
        "hidden/02_discount_test.dart",
    )


def test_settings_starter_and_extra_solution_files_stay_out_of_the_image() -> None:
    package = read(
        {
            **VALID,
            "ohw.yaml": b"allow_dart_io: false",
            "starter/lib/cart.dart": b"class Cart {}",
            "solution/README.md": b"how I solved it",
        }
    )

    paths = [f.path for f in package.project_files]
    assert "ohw.yaml" not in paths
    assert not any(p.startswith(("starter/", "solution/")) for p in paths)
    assert [f.path for f in package.solution_files] == ["lib/cart.dart"]


def test_helpers_and_assets_go_into_the_image() -> None:
    package = read(
        {**VALID, "test/helpers/fake_api.dart": b"", "assets/logo.png": b"png", "pubspec.lock": b""}
    )

    paths = {f.path for f in package.project_files}
    assert {"test/helpers/fake_api.dart", "assets/logo.png", "pubspec.lock"} <= paths


def test_zipped_folder_is_read_from_inside() -> None:
    package = read({f"cart_task/{path}": data for path, data in VALID.items()})

    assert package.test_files == ("public/01_cart_test.dart", "hidden/02_discount_test.dart")
    assert "pubspec.yaml" in {f.path for f in package.project_files}


def test_junk_is_left_out() -> None:
    package = read(
        {
            **VALID,
            "__MACOSX/._pubspec.yaml": b"",
            ".dart_tool/package_config.json": b"",
            "build/test_cache/x.dill": b"",
            "test/.DS_Store": b"",
        }
    )

    assert len(package.project_files) == 3


@pytest.mark.parametrize(
    ("path", "junk"),
    [
        ("build/app.dill", True),
        ("a/.git/config", True),
        ("test/.DS_Store", True),
        ("test/public/build_test.dart", False),
        ("lib/build.dart", False),
    ],
)
def test_is_junk(path: str, junk: bool) -> None:
    assert is_junk(path) is junk


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("pubspec.yaml", "pubspec.yaml topilmadi"),
        ("solution/lib/cart.dart", "solution/lib papkasida .dart fayl yoʻq"),
        ("test/public/01_cart_test.dart", "test/public papkasida test fayli"),
        ("test/hidden/02_discount_test.dart", "test/hidden papkasida test fayli"),
    ],
)
def test_missing_required_part_is_reported(missing: str, message: str) -> None:
    entries = {path: data for path, data in VALID.items() if path != missing}

    errors = errors_of(entries)

    assert len(errors) == 1
    assert message in errors[0]


def test_all_problems_are_reported_at_once() -> None:
    errors = errors_of({"README.md": b""})

    assert len(errors) == 4


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        pytest.param("lib/cart.dart", "Ildizdagi lib/ papkasi ishlatilmaydi", id="lib-at-root"),
        pytest.param(
            "test/foo_test.dart", "test/public yoki test/hidden", id="test-outside-folders"
        ),
        pytest.param(
            "test/other/foo_test.dart", "test/public yoki test/hidden", id="test-in-other-folder"
        ),
        pytest.param("test/_ohw_all_test.dart", "platforma uchun band", id="reserved-name"),
        pytest.param("test/public/it's_test.dart", "ruxsat etilmagan belgi", id="quote-in-name"),
        pytest.param("test/public/$x_test.dart", "ruxsat etilmagan belgi", id="dollar-in-name"),
    ],
)
def test_misplaced_or_unsafe_files_are_reported(extra: str, message: str) -> None:
    errors = errors_of({**VALID, extra: b""})

    assert len(errors) == 1
    assert message in errors[0]


@pytest.mark.parametrize(
    ("test_file", "visibility"),
    [
        ("public/01_cart_test.dart", Visibility.PUBLIC),
        ("hidden/02_discount_test.dart", Visibility.HIDDEN),
        ("something/else_test.dart", Visibility.HIDDEN),
    ],
)
def test_visibility_comes_from_the_folder(test_file: str, visibility: Visibility) -> None:
    assert visibility_of(test_file) == visibility
