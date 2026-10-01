"""judge_zip before anything runs: every rejection happens without Docker."""

import io
import zipfile
from collections.abc import Sequence

import pytest

from judge.core.manifest import Manifest, ManifestTest, Visibility
from judge.core.verdict import Verdict
from judge.infra import runner
from judge.infra.runner import JudgeResult, TaskImage, judge_zip
from judge.packaging.dart_imports import ImportRules
from judge.packaging.zip_validator import ArchiveFile, ZipLimits
from tests.judge.infra.support import NODE, load_profile

DART = load_profile("dart")
LIMITS = ZipLimits(max_zip_bytes=64 * 1024, max_unpacked_bytes=64 * 1024, max_files=20)
TASK = TaskImage(
    image_tag="ohw-task:test-000000000000",
    manifest=Manifest(
        (
            ManifestTest("Savat boʻsh", 1, Visibility.PUBLIC),
            ManifestTest("Chegirma", 1, Visibility.HIDDEN),
        )
    ),
    time_limit_s=20,
    import_rules=ImportRules("cart", frozenset({"cart"}), frozenset({"io", "ffi"})),
)


class NoDocker:
    """Fails the test if judge_zip tries to run anything."""

    def __getattr__(self, name: str) -> None:
        raise AssertionError("Docker must not be used for a rejected zip")


def zip_of(**files: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, data in files.items():
            archive.writestr(path.replace("__", "/"), data)
    buffer.seek(0)
    return buffer


def judged(archive: io.BytesIO, task: TaskImage = TASK) -> JudgeResult:
    return judge_zip(NoDocker(), task, DART, NODE, archive, LIMITS)  # type: ignore[arg-type]


def assert_rejected(result: JudgeResult, message: str) -> None:
    assert result.judgement.verdict == Verdict.REJECTED
    assert not result.judgement.verdict.counts_as_attempt
    assert (result.judgement.tests_total, result.judgement.tests_passed) == (2, 0)
    assert message in result.public_message
    assert result.results == ()


def test_file_that_is_not_a_zip_is_rejected() -> None:
    assert_rejected(judged(io.BytesIO(b"not a zip")), "Fayl zip emas yoki buzilgan")


def test_zip_slip_is_rejected() -> None:
    assert_rejected(judged(zip_of(**{"..__evil.dart": b"x"})), "xavfli yoʻl")


def test_zip_without_lib_is_rejected() -> None:
    result = judged(zip_of(**{"main.dart": b"void main() {}"}))

    assert_rejected(result, "Zip ichida lib/ papkasi topilmadi.")


def test_forbidden_import_is_rejected_with_every_problem() -> None:
    source = b"import 'dart:io';\nimport 'dart:ffi';\nclass Cart {}\n"

    result = judged(zip_of(**{"cart__lib__cart.dart": source}))

    assert_rejected(result, "Taqiqlangan import: dart:io — bu topshiriqda ruxsat etilmagan")
    assert "dart:ffi" in result.public_message


def test_public_message_is_capped() -> None:
    many = b"".join(b"import 'dart:io';\n" for _ in range(200))

    result = judged(zip_of(**{"lib__cart.dart": many}))

    assert len(result.public_message) == runner.MAX_PUBLIC_MESSAGE


def test_task_without_rules_for_a_checked_profile_is_a_bug() -> None:
    task = TaskImage(TASK.image_tag, TASK.manifest, TASK.time_limit_s)

    with pytest.raises(ValueError, match="no import rules"):
        judged(zip_of(**{"lib__cart.dart": b"class Cart {}"}), task)


def test_clean_zip_goes_to_the_runner_with_only_student_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Sequence[ArchiveFile]] = []

    def fake_judge_submission(*args: object) -> str:
        seen.append(args[4])  # type: ignore[arg-type]
        return "ran"

    monkeypatch.setattr(runner, "judge_submission", fake_judge_submission)
    archive = zip_of(
        **{
            "cart__lib__cart.dart": b"import 'dart:math';\nclass Cart {}",
            "cart__pubspec.yaml": b"name: hacked",
            "cart__test__public__fake_test.dart": b"void main() {}",
        }
    )

    assert judged(archive) == "ran"  # type: ignore[comparison-overlap]
    assert seen == [[ArchiveFile("lib/cart.dart", b"import 'dart:math';\nclass Cart {}")]]
