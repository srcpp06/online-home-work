import random

import pytest

from judge.core.profile import RunnerProfile
from judge.packaging.dart_imports import ImportRules, find_forbidden_imports
from judge.packaging.task_package import TaskPackage, read_task_package
from judge.packaging.zip_validator import ArchiveFile

FORBIDDEN = frozenset({"io", "ffi", "isolate", "mirrors", "cli"})
RULES = ImportRules(
    package_name="cart",
    allowed_packages=frozenset({"cart", "collection", "flutter"}),
    forbidden_dart=FORBIDDEN,
)


def check(
    source: str | bytes, path: str = "lib/cart.dart", rules: ImportRules = RULES
) -> list[str]:
    data = source.encode() if isinstance(source, str) else source
    return find_forbidden_imports([ArchiveFile(path, data)], rules)


def test_message_names_the_import_and_where_it_is() -> None:
    problems = check("// Savat\n\nimport 'dart:io';\n")

    assert problems == [
        "Taqiqlangan import: dart:io — bu topshiriqda ruxsat etilmagan (lib/cart.dart:3)"
    ]


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import 'dart:io';", id="plain"),
        pytest.param('import "dart:io";', id="double-quotes"),
        pytest.param("import 'dart:io' as io show stdout;", id="prefix-and-show"),
        pytest.param("import /* hidden */ 'dart:io';", id="comment-inside"),
        pytest.param("import // hidden\n  'dart:io';", id="line-comment-inside"),
        pytest.param("import 'dart:' 'io';", id="adjacent-strings"),
        pytest.param("import 'dart:' \"io\";", id="adjacent-mixed-quotes"),
        pytest.param("import 'da' 'rt:' r'io';", id="three-pieces"),
        pytest.param(r"import 'dart:\x69o';", id="hex-escape"),
        pytest.param(r"import 'dart:\u0069o';", id="unicode-escape"),
        pytest.param(r"import 'dart:\u{69}o';", id="unicode-braces-escape"),
        pytest.param(r"import 'dart:i\o';", id="needless-escape"),
        pytest.param("import r'dart:io';", id="raw-string"),
        pytest.param("import '''dart:io''';", id="triple-quotes"),
        pytest.param("import '''\n  dart:io''';", id="triple-quotes-first-line-dropped"),
        pytest.param("import ' dart:io ';", id="spaces"),
        pytest.param("import 'dart:i%6F';", id="percent-escape"),
        pytest.param("import 'DART:io';", id="upper-case-scheme"),
        pytest.param("import 'dart:IO';", id="upper-case-library"),
        pytest.param("export 'dart:io';", id="export"),
        pytest.param("part 'dart:io';", id="part"),
        pytest.param("import augment 'dart:io';", id="augment"),
        pytest.param("import 'src/stub.dart' if (dart.library.io) 'dart:io';", id="conditional"),
        pytest.param("@Deprecated('x')\nimport 'dart:io';", id="annotation"),
        pytest.param(r"""@Foo('${"}"}') import 'dart:io';""", id="interpolation-with-brace"),
        pytest.param("/* a /* nested */ still a comment */ import 'dart:io';", id="nested-comment"),
        pytest.param("#!/usr/bin/env dart\nimport 'dart:io';", id="script-tag"),
        pytest.param("\ufeffimport 'dart:io';", id="byte-order-mark"),
        pytest.param("import 'dart:ffi';", id="ffi"),
        pytest.param("import 'dart:isolate';", id="isolate"),
        pytest.param("import 'dart:mirrors';", id="mirrors"),
        pytest.param("import 'dart:cli';", id="cli"),
    ],
)
def test_forbidden_dart_library_is_found_however_it_is_written(source: str) -> None:
    problems = check(source)

    assert len(problems) == 1, problems
    assert "Taqiqlangan import" in problems[0]


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        pytest.param("import 'package:http/http.dart';", "roʻyxatida yoʻq", id="unknown-package"),
        pytest.param("import 'package:test/test.dart';", "roʻyxatida yoʻq", id="dev-dependency"),
        pytest.param("import 'package:cart/../x.dart';", "ruxsat etilmagan", id="package-dots"),
        pytest.param("import 'package:cart//x.dart';", "ruxsat etilmagan", id="package-empty"),
        pytest.param("import 'package:cart/notes.txt';", ".dart fayllarni", id="package-not-dart"),
        pytest.param(
            "import '../test/hidden/02_discount_test.dart';", "lib/ papkasidan", id="tests"
        ),
        pytest.param("import '/etc/passwd.dart';", "lib/ papkasidan", id="absolute-path"),
        pytest.param("import '//host/x.dart';", "lib/ papkasidan", id="network-path"),
        pytest.param("import 'file:///home/ohw/app/x.dart';", "faqat dart:", id="file-scheme"),
        pytest.param("import 'data:application/dart,main(){}';", "faqat dart:", id="data-uri"),
        pytest.param("import 'https://example.com/x.dart';", "faqat dart:", id="http"),
        pytest.param("import 'C:/x.dart';", "faqat dart:", id="drive-letter"),
        pytest.param("import 'notes.txt';", ".dart fayllarni", id="not-a-dart-file"),
        pytest.param("import 'notes.txt?.dart';", "? yoki #", id="query"),
        pytest.param("import 'x.dart#y';", "? yoki #", id="fragment"),
        pytest.param(r"import 'src\\helper.dart';", "? yoki #", id="backslash"),
        pytest.param("import 'dart:${name}';", "$ ishlatib", id="interpolation"),
        pytest.param(r"import 'dart:i\no';", "boʻsh joy", id="control-character"),
        pytest.param("import 'dart:io/x';", "ruxsat etilmagan", id="dart-subpath"),
        pytest.param("import 'dart:io.dart';", "ruxsat etilmagan", id="dart-odd-name"),
    ],
)
def test_other_forbidden_imports_are_explained(source: str, reason: str) -> None:
    problems = check(source)

    assert len(problems) == 1, problems
    assert reason in problems[0]


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import 'dart:math';", id="dart-math"),
        pytest.param("import 'dart:async';\nimport 'dart:collection';", id="more-dart"),
        pytest.param("import 'dart:convert' show jsonEncode;", id="show"),
        pytest.param("import 'dart:ui';", id="dart-ui-for-flutter"),
        pytest.param("import 'package:collection/collection.dart';", id="dependency"),
        pytest.param("import 'package:flutter/material.dart';", id="flutter"),
        pytest.param("import 'package:cart/src/money.dart';", id="own-package"),
        pytest.param("import 'src/helper.dart';", id="relative"),
        pytest.param("import 'src/a.dart' if (dart.library.ui) 'src/b.dart';", id="conditional"),
        pytest.param("part 'src/part.dart';", id="part"),
        pytest.param("part of 'cart.dart';", id="part-of"),
        pytest.param("library cart;", id="library"),
        pytest.param("// import 'dart:io';", id="line-comment"),
        pytest.param("/// Never import 'dart:io';", id="doc-comment"),
        pytest.param("/* import 'dart:io'; */", id="block-comment"),
        pytest.param("/* /* import 'dart:io'; */ */", id="nested-block-comment"),
        pytest.param("const code = \"import 'dart:io';\";", id="in-a-string"),
        pytest.param("const code = '''\nimport 'dart:io';\n''';", id="in-a-multiline-string"),
        pytest.param("var import = 'dart:io';", id="variable-named-import"),
        pytest.param("final part = 'dart:io'; void f() => print(part);", id="variable-named-part"),
        pytest.param("final s = 'a${'}'}b'; final t = r'$x';", id="tricky-strings"),
        pytest.param("final s = 'x is \\$5';", id="escaped-dollar"),
        pytest.param("", id="empty-file"),
    ],
)
def test_legitimate_code_passes(source: str) -> None:
    path = "lib/src/helper.dart" if "part of" in source else "lib/cart.dart"

    assert check(source, path) == []


def test_relative_import_from_a_subfolder_stays_inside_lib() -> None:
    assert check("import '../cart.dart';", "lib/src/money.dart") == []
    assert check("import '../../pubspec.dart';", "lib/src/money.dart") != []


def test_every_import_in_every_file_is_reported() -> None:
    files = [
        ArchiveFile("lib/a.dart", b"import 'dart:io';\nimport 'dart:ffi';"),
        ArchiveFile("lib/src/b.dart", b"export 'dart:mirrors';"),
        ArchiveFile("lib/notes.txt", b"import 'dart:io';"),  # never compiled unless imported
    ]

    problems = find_forbidden_imports(files, RULES)

    assert [p.rsplit("(", 1)[1] for p in problems] == [
        "lib/a.dart:1)",
        "lib/a.dart:2)",
        "lib/src/b.dart:1)",
    ]


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import 'dart:io;\n", id="unterminated-string"),
        pytest.param("/* never closed import 'dart:io';", id="unterminated-comment"),
        pytest.param("final s = 'a $ b';", id="lone-dollar"),
        pytest.param(r"final s = '\x6';", id="short-hex-escape"),
        pytest.param(r"final s = '\u{110000}';", id="code-point-too-big"),
        pytest.param("final s = '${'x';", id="unterminated-interpolation"),
    ],
)
def test_code_the_checker_cannot_read_is_rejected(source: str) -> None:
    problems = check(source)

    assert len(problems) == 1
    assert "tekshirib boʻlmadi" in problems[0]


def test_file_that_is_not_utf8_is_rejected() -> None:
    problems = check(b"import 'dart:\xffio';")

    assert problems == [
        "lib/cart.dart: fayl UTF-8 kodlashida emas. Faylni UTF-8 da saqlab qayta yuklang."
    ]


def test_messages_never_carry_control_characters() -> None:
    problems = check("import 'dart:io\\n\\x1b[31m';")

    assert problems and all(char not in problems[0] for char in "\n\x1b")


def test_random_input_never_crashes_the_checker() -> None:
    alphabet = ["'", '"', "r", "$", "\\", "{", "}", "/", "*", "\n", " ", "import ", "dart:io", ";"]
    rng = random.Random(20261001)
    for _ in range(3000):
        source = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        assert isinstance(check(source), list)


def profile(forbidden: list[str]) -> RunnerProfile:
    return RunnerProfile.from_json_data(
        {
            "slug": "dart",
            "lane": "fast",
            "student_paths": ["lib"],
            "install_command": ["dart", "pub", "get"],
            "test_command": ["dart", "test"],
            "test_import": "package:test/test.dart",
            "parser": "dart_json",
            "static_check": "dart_imports",
            "forbidden_imports": forbidden,
            "memory_mb": 1024,
            "cpus": 1.0,
            "tmp_mb": 64,
            "min_time_s": 20,
            "max_time_s": 120,
            "build_timeout_s": 300,
        }
    )


def package(ohw_yaml: bytes | None = None) -> TaskPackage:
    files = {
        "pubspec.yaml": b"name: cart\ndependencies:\n  collection: any\n"
        b"dev_dependencies:\n  test: any\n",
        "solution/lib/cart.dart": b"class Cart {}",
        "test/public/a_test.dart": b"",
        "test/hidden/b_test.dart": b"",
    }
    if ohw_yaml is not None:
        files["ohw.yaml"] = ohw_yaml
    return read_task_package([ArchiveFile(path, data) for path, data in files.items()])


def test_rules_come_from_the_task_and_the_profile() -> None:
    rules = ImportRules.for_task(package(), profile(["dart:io", "dart:ffi"]))

    assert rules == ImportRules(
        package_name="cart",
        allowed_packages=frozenset({"cart", "collection"}),
        forbidden_dart=frozenset({"io", "ffi"}),
    )


def test_allow_dart_io_lifts_only_dart_io() -> None:
    allowing_io = package(b"allow_dart_io: true\n")
    rules = ImportRules.for_task(allowing_io, profile(["dart:io", "dart:ffi"]))

    assert check("import 'dart:io';", rules=rules) == []
    assert check("import 'dart:ffi';", rules=rules) != []
