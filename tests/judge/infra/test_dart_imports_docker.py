"""The import checker against the real Dart compiler (marker: docker).

Every case hides dart:io in a different way. Running it with Dart shows what Dart really
does with it (recorded below, so a Dart upgrade that changes it is noticed); whatever
Dart does, the checker must reject every case.
"""

import docker
import pytest

from judge.infra.sandbox import Sandbox, SandboxLimits
from judge.packaging.dart_imports import ImportRules, find_forbidden_imports
from judge.packaging.zip_validator import ArchiveFile

pytestmark = pytest.mark.docker

USES_IO = "void main() { print('COMPILED'); stdout.write('ESCAPED'); }"
USES_OUTSIDE = "void main() { print('COMPILED'); print(outside()); }"
# A file next to lib/, like the task's tests: student code must never reach it.
OUTSIDE_LIB = ArchiveFile("outside.dart", b"String outside() => 'ESCAPED';\n")
NO_IO = "void main() { print('COMPILED'); }"
ESCAPES, COMPILES, REJECTED_BY_DART = "COMPILED ESCAPED", "COMPILED", ""

# name: (directive, main, what Dart 3.13 does with it)
CASES = {
    "plain": ("import 'dart:io';", USES_IO, ESCAPES),
    "adjacent_strings": ("import 'dart:' 'io';", USES_IO, ESCAPES),
    "comment_inside": ("import /* x */ 'dart:io';", USES_IO, ESCAPES),
    "after_nested_comment": ("/* a /* b */ c */ import 'dart:io';", USES_IO, ESCAPES),
    "hex_escape": (r"import 'dart:\x69o';", USES_IO, ESCAPES),
    "unicode_escape": (r"import 'dart:io';", USES_IO, ESCAPES),
    "unicode_braces_escape": (r"import 'dart:\u{69}o';", USES_IO, ESCAPES),
    "needless_escape": (r"import 'dart:i\o';", USES_IO, ESCAPES),
    "raw_string": ("import r'dart:io';", USES_IO, ESCAPES),
    "triple_quotes": ("import '''dart:io''';", USES_IO, ESCAPES),
    "triple_quotes_first_line": ("import '''\ndart:io''';", USES_IO, ESCAPES),
    "percent_escape": ("import 'dart:i%6F';", USES_IO, ESCAPES),
    "upper_case_scheme": ("import 'DART:io';", USES_IO, ESCAPES),
    "conditional": ("import 'dart:core' if (dart.library.io) 'dart:io';", USES_IO, ESCAPES),
    "annotation_interpolation": (
        """@Deprecated('${"}"}') import 'dart:io';""",
        USES_IO,
        ESCAPES,
    ),
    "export": ("export 'dart:io';", NO_IO, COMPILES),
    "triple_quotes_indented": ("import '''\n  dart:io''';", USES_IO, REJECTED_BY_DART),
    "spaces": ("import ' dart:io';", USES_IO, REJECTED_BY_DART),
    "upper_case_library": ("import 'dart:IO';", USES_IO, REJECTED_BY_DART),
    "dart_subpath": ("import 'dart:io/x';", USES_IO, REJECTED_BY_DART),
    "augment": ("import augment 'dart:io';", NO_IO, REJECTED_BY_DART),
    "percent_dots": ("import '%2E%2E/outside.dart';", USES_OUTSIDE, ESCAPES),
    "plain_dots": ("import '../outside.dart';", USES_OUTSIDE, ESCAPES),
    "dart_ffi": ("import 'dart:ffi';", NO_IO, COMPILES),
    "dart_isolate": ("import 'dart:isolate';", NO_IO, COMPILES),
    "dart_mirrors": ("import 'dart:mirrors';", NO_IO, COMPILES),
}
LEGITIMATE = {
    "dart_math": ("import 'dart:math';", "void main() { print(max(1, 2)); }"),
    "io_in_a_comment": ("// import 'dart:io';", "void main() { print('2'); }"),
    "io_in_a_string": ("const s = \"import 'dart:io';\";", "void main() { print(s.length); }"),
}
RULES = ImportRules(
    package_name="cases",
    allowed_packages=frozenset({"cases"}),
    forbidden_dart=frozenset({"io", "ffi", "isolate", "mirrors", "cli"}),
)


def source(directive: str, main: str) -> bytes:
    return f"{directive}\n{main}\n".encode()


@pytest.fixture(scope="module")
def dart_output(docker_client: docker.DockerClient, dart_base_image: str) -> dict[str, str]:
    """What `dart run` prints for every case, run offline in the sandbox."""
    every = {name: (d, m) for name, (d, m, _) in CASES.items()} | LEGITIMATE
    files = [ArchiveFile(f"lib/{name}.dart", source(*code)) for name, code in every.items()]
    files.append(OUTSIDE_LIB)
    script = (
        'for f in lib/*.dart; do echo "$(basename "$f" .dart)|'
        '$(dart run "$f" 2>/dev/null | tr "\\n" " " | sed "s/ $//")"; done'
    )
    limits = SandboxLimits(
        memory_mb=1024,
        cpus=2.0,
        tmp_mb=64,
        cpu_shares=512,
        max_output_bytes=1024 * 1024,
        runtime="runc",
        pids_limit=256,
    )
    with Sandbox(docker_client, dart_base_image, ["bash", "-c", script], limits) as sandbox:
        sandbox.put_files(files)
        run = sandbox.run(600)
    return dict(line.split("|", 1) for line in run.stdout.splitlines() if "|" in line)


@pytest.mark.parametrize("name", CASES)
def test_dart_does_what_we_recorded(dart_output: dict[str, str], name: str) -> None:
    assert dart_output[name] == CASES[name][2]


@pytest.mark.parametrize("name", CASES)
def test_checker_rejects_every_way_of_writing_it(name: str) -> None:
    directive, main, _ = CASES[name]

    files = [ArchiveFile("lib/case.dart", source(directive, main))]

    problems = find_forbidden_imports(files, RULES)

    assert problems, f"{name} slipped through"


@pytest.mark.parametrize("name", LEGITIMATE)
def test_legitimate_code_runs_and_passes_the_checker(
    dart_output: dict[str, str], name: str
) -> None:
    files = [ArchiveFile("lib/case.dart", source(*LEGITIMATE[name]))]

    assert dart_output[name] != ""
    assert find_forbidden_imports(files, RULES) == []
