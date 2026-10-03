import io
import zipfile

from judge.packaging.starter import package_checklist, starter_files, starter_zip
from judge.packaging.zip_validator import ArchiveFile

PACKAGE = [
    ArchiveFile("cart/pubspec.yaml", b"name: cart\n"),
    ArchiveFile("cart/ohw.yaml", b"allow_dart_io: false\n"),
    ArchiveFile("cart/solution/lib/cart.dart", b"// the answer"),
    ArchiveFile("cart/test/public/cart_test.dart", b"// open"),
    ArchiveFile("cart/test/hidden/discount_test.dart", b"// hidden"),
    ArchiveFile("cart/starter/lib/cart.dart", b"// TODO"),
    ArchiveFile("cart/assets/prices.json", b"[]"),
    ArchiveFile("cart/.dart_tool/cache", b"junk"),
]


def test_starter_has_no_solution_hidden_tests_or_settings() -> None:
    paths = [file.path for file in starter_files(PACKAGE)]

    assert paths == [
        "assets/prices.json",
        "lib/cart.dart",
        "pubspec.yaml",
        "test/public/cart_test.dart",
    ]


def test_starter_code_takes_the_place_of_the_lib_folder() -> None:
    files = {file.path: file.data for file in starter_files(PACKAGE)}

    assert files["lib/cart.dart"] == b"// TODO"


def test_starter_zip_is_one_folder_and_always_the_same_bytes() -> None:
    first, second = starter_zip(PACKAGE, "cart"), starter_zip(PACKAGE, "cart")

    assert first == second
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert all(name.startswith("cart/") for name in archive.namelist())
        assert archive.read("cart/lib/cart.dart") == b"// TODO"


def test_checklist_says_what_is_there_and_what_is_missing() -> None:
    items = package_checklist([f for f in PACKAGE if "hidden" not in f.path])

    assert [(i.label, i.found, i.detail) for i in items] == [
        ("pubspec.yaml", True, "bor"),
        ("solution/lib", True, "1 ta .dart fayl"),
        ("test/public", True, "1 ta test fayli"),
        ("test/hidden", False, "topilmadi"),
        ("starter/ (ixtiyoriy)", True, "1 ta fayl"),
    ]
