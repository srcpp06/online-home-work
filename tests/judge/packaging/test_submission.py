import io
import zipfile

import pytest

from judge.packaging.submission import SubmissionInvalid, read_submission, select_student_files
from judge.packaging.zip_validator import ArchiveFile, ZipLimits, validate_zip

LIB = ["lib"]


def selected(*paths: str) -> dict[str, str]:
    return select_student_files(list(paths), LIB)


def test_lib_at_the_root_is_taken_as_is() -> None:
    assert selected("lib/main.dart", "lib/src/cart.dart") == {
        "lib/main.dart": "lib/main.dart",
        "lib/src/cart.dart": "lib/src/cart.dart",
    }


@pytest.mark.parametrize(
    "root",
    [
        pytest.param("cart", id="project-folder"),
        pytest.param("Downloads/cart", id="two-deep"),
        pytest.param("a/b/cart", id="three-deep"),
    ],
)
def test_lib_is_found_up_to_three_folders_deep(root: str) -> None:
    assert selected(f"{root}/lib/cart.dart") == {f"{root}/lib/cart.dart": "lib/cart.dart"}


def test_lib_deeper_than_three_folders_is_not_found() -> None:
    with pytest.raises(SubmissionInvalid):
        selected("a/b/c/cart/lib/cart.dart")


def test_whole_project_gives_only_lib() -> None:
    result = selected(
        "cart/pubspec.yaml",
        "cart/pubspec.lock",
        "cart/test/public/01_cart_test.dart",
        "cart/lib/cart.dart",
        "cart/build/app.dill",
        "cart/.dart_tool/package_config.json",
        "__MACOSX/cart/lib/._cart.dart",
        "cart/lib/.DS_Store",
    )

    assert result == {"cart/lib/cart.dart": "lib/cart.dart"}


def test_shallowest_lib_wins() -> None:
    result = selected("cart/lib/cart.dart", "cart/example/lib/main.dart", "cart/test/lib/fake.dart")

    assert result == {"cart/lib/cart.dart": "lib/cart.dart"}


def test_two_projects_side_by_side_are_rejected() -> None:
    with pytest.raises(SubmissionInvalid, match="bir nechta lib/ papkasi bor: a/lib/, b/lib/"):
        selected("a/lib/cart.dart", "b/lib/cart.dart")


@pytest.mark.parametrize(
    "paths",
    [
        pytest.param([], id="empty-zip"),
        pytest.param(["cart.dart", "pubspec.yaml"], id="files-without-lib"),
        pytest.param(["lib"], id="lib-is-a-file"),
        pytest.param(["__MACOSX/lib/._cart.dart"], id="only-mac-leftovers"),
        pytest.param(["build/lib/cart.dart"], id="only-in-build"),
    ],
)
def test_missing_lib_is_explained(paths: list[str]) -> None:
    with pytest.raises(SubmissionInvalid) as error:
        select_student_files(paths, LIB)

    assert str(error.value) == (
        "Zip ichida lib/ papkasi topilmadi. Loyihangizning lib/ papkasini zip qilib qayta yuklang."
    )


def test_every_student_path_is_taken_from_the_same_root() -> None:
    result = select_student_files(
        ["app/lib/main.dart", "app/assets/logo.png", "app/README.md", "assets/other.png"],
        ["lib", "assets"],
    )

    assert result == {
        "app/lib/main.dart": "lib/main.dart",
        "app/assets/logo.png": "assets/logo.png",
    }


def test_read_submission_decompresses_only_student_files() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cart/build/huge.bin", b"\0" * (5 * 1024 * 1024))
        archive.writestr("cart/pubspec.yaml", b"name: hacked")
        archive.writestr("cart/lib/cart.dart", b"class Cart {}")
    limits = ZipLimits(max_zip_bytes=1024 * 1024, max_unpacked_bytes=1024, max_files=5)

    files = read_submission(validate_zip(buffer, limits), LIB)

    assert files == [ArchiveFile("lib/cart.dart", b"class Cart {}")]
