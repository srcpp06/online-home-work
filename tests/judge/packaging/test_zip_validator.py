"""Zip validator against hostile zips. Every zip is built in the test, so each case is readable."""

import io
import random
import stat
import struct
import warnings
import zipfile

import pytest

from judge.packaging.zip_validator import (
    ArchiveFile,
    ValidatedZip,
    ZipLimits,
    ZipProblem,
    ZipRejected,
    validate_zip,
)

LIMITS = ZipLimits(max_zip_bytes=1024 * 1024, max_unpacked_bytes=64 * 1024, max_files=10)

Entry = tuple[str | zipfile.ZipInfo, bytes]


def make_zip(*entries: Entry, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # zipfile warns about duplicate names
        with zipfile.ZipFile(buffer, "w", compression) as archive:
            for name, data in entries:
                archive.writestr(name, data)
    return buffer.getvalue()


def unix_entry(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def patch_header_field(data: bytes, local_offset: int, central_offset: int, value: int) -> bytes:
    """Overwrite a 2-byte field of the first entry, both in its local and central header."""
    patched = bytearray(data)
    central = patched.find(b"PK\x01\x02")
    struct.pack_into("<H", patched, local_offset, value)
    struct.pack_into("<H", patched, central + central_offset, value)
    return bytes(patched)


def validate(data: bytes, limits: ZipLimits = LIMITS) -> ValidatedZip:
    return validate_zip(io.BytesIO(data), limits)


def rejected(data: bytes, limits: ZipLimits = LIMITS) -> ZipRejected:
    with pytest.raises(ZipRejected) as error:
        validate(data, limits).read()
    return error.value


def test_valid_zip_is_read_in_order_without_directories() -> None:
    data = make_zip(
        ("lib/", b""),
        ("lib/main.dart", b"void main() {}"),
        ("lib/src/cart.dart", b"class Cart {}"),
    )

    archive = validate(data)

    assert archive.paths == ["lib/main.dart", "lib/src/cart.dart"]
    assert archive.read() == [
        ArchiveFile("lib/main.dart", b"void main() {}"),
        ArchiveFile("lib/src/cart.dart", b"class Cart {}"),
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("lib\\main.dart", "lib/main.dart", id="windows-backslashes"),
        pytest.param("./lib/main.dart", "lib/main.dart", id="dot-prefix"),
        pytest.param("lib//main.dart", "lib/main.dart", id="double-slash"),
        pytest.param("lib/oʻquvchi.dart", "lib/oʻquvchi.dart", id="unicode"),
    ],
)
def test_paths_are_normalized(name: str, expected: str) -> None:
    assert validate(make_zip((name, b"x"))).paths == [expected]


@pytest.mark.parametrize(
    "compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA]
)
def test_common_compression_methods_are_supported(compression: int) -> None:
    data = make_zip(("lib/main.dart", b"x" * 100), compression=compression)

    assert validate(data).read() == [ArchiveFile("lib/main.dart", b"x" * 100)]


def test_too_large_zip_is_rejected_before_it_is_parsed() -> None:
    not_even_a_zip = b"\0" * 2048
    limits = ZipLimits(max_zip_bytes=1024, max_unpacked_bytes=1024, max_files=1)

    error = rejected(not_even_a_zip, limits)

    assert error.problem == ZipProblem.TOO_LARGE
    assert str(error).startswith("Zip hajmi juda katta")


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="empty-file"),
        pytest.param(b"this is not a zip", id="not-a-zip"),
        pytest.param(make_zip(("lib/main.dart", b"x" * 1000))[:-30], id="truncated"),
    ],
)
def test_broken_zip_is_rejected(data: bytes) -> None:
    assert rejected(data).problem == ZipProblem.BROKEN


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("../evil.dart", id="parent"),
        pytest.param("lib/../../evil.dart", id="parent-in-the-middle"),
        pytest.param("..\\evil.dart", id="parent-with-backslash"),
        pytest.param("/etc/passwd", id="absolute"),
        pytest.param("\\etc\\passwd", id="absolute-with-backslash"),
        pytest.param("C:/Windows/evil.dart", id="drive-letter"),
        pytest.param("C:evil.dart", id="drive-relative"),
        pytest.param("lib/evil\n.dart", id="newline"),
        pytest.param("lib/\x1b[31mevil.dart", id="terminal-escape"),
    ],
)
def test_zip_slip_paths_are_rejected(name: str) -> None:
    error = rejected(make_zip(("lib/main.dart", b"ok"), (name, b"evil")))

    assert error.problem == ZipProblem.UNSAFE_PATH
    assert "\n" not in str(error)
    assert "\x1b" not in str(error)


@pytest.mark.parametrize(
    ("mode", "word"),
    [
        pytest.param(stat.S_IFLNK | 0o777, "symlink", id="symlink"),
        pytest.param(stat.S_IFIFO | 0o644, "oddiy boʻlmagan", id="fifo"),
        pytest.param(stat.S_IFCHR | 0o644, "oddiy boʻlmagan", id="device"),
    ],
)
def test_links_and_special_files_are_rejected(mode: int, word: str) -> None:
    data = make_zip(("lib/main.dart", b"ok"), (unix_entry("lib/link.dart", mode), b"/etc/passwd"))

    error = rejected(data)

    assert error.problem == ZipProblem.NOT_A_REGULAR_FILE
    assert word in str(error)
    assert "lib/link.dart" in str(error)


def test_regular_unix_files_and_directories_are_fine() -> None:
    data = make_zip(
        (unix_entry("lib/", stat.S_IFDIR | 0o755), b""),
        (unix_entry("lib/main.dart", stat.S_IFREG | 0o644), b"ok"),
    )

    assert validate(data).paths == ["lib/main.dart"]


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param(0x1, id="encrypted"),
        pytest.param(0x40, id="strong-encryption"),  # found by the fuzz test
    ],
)
def test_encrypted_entry_is_rejected(flags: int) -> None:
    data = patch_header_field(make_zip(("lib/main.dart", b"x")), 6, 8, flags)

    assert rejected(data).problem == ZipProblem.ENCRYPTED


def test_unsupported_compression_is_rejected() -> None:
    deflate64 = 9
    data = patch_header_field(make_zip(("lib/main.dart", b"x")), 8, 10, deflate64)

    assert rejected(data).problem == ZipProblem.UNSUPPORTED


def test_patched_data_entry_is_unsupported() -> None:
    """Found by the fuzz test: zipfile raised a bare NotImplementedError."""
    patched_data_flag = 0x20
    data = patch_header_field(make_zip(("lib/main.dart", b"x")), 6, 8, patched_data_flag)

    assert rejected(data).problem == ZipProblem.UNSUPPORTED


def test_unknown_zip_version_is_a_broken_zip() -> None:
    """Found by the fuzz test: zipfile raised a bare NotImplementedError."""
    data = patch_header_field(make_zip(("lib/main.dart", b"x")), 4, 6, 255)  # version 25.5

    assert rejected(data).problem == ZipProblem.BROKEN


@pytest.mark.parametrize(
    "second_name",
    [
        pytest.param("lib/main.dart", id="same-name"),
        pytest.param("lib\\main.dart", id="same-after-backslash"),
        pytest.param("./lib/main.dart", id="same-after-dot"),
    ],
)
def test_duplicate_files_are_rejected(second_name: str) -> None:
    data = make_zip(("lib/main.dart", b"one"), (second_name, b"two"))

    assert rejected(data).problem == ZipProblem.DUPLICATE


@pytest.mark.parametrize(
    "entries",
    [
        pytest.param([("lib", b"file"), ("lib/main.dart", b"x")], id="file-then-folder"),
        pytest.param([("lib/main.dart", b"x"), ("lib", b"file")], id="folder-then-file"),
        pytest.param([("lib/", b""), ("lib", b"file")], id="folder-entry-and-file"),
    ],
)
def test_same_path_as_file_and_folder_is_rejected(entries: list[Entry]) -> None:
    assert rejected(make_zip(*entries)).problem == ZipProblem.PATH_CONFLICT


def test_too_many_files_are_rejected() -> None:
    limits = ZipLimits(max_zip_bytes=1024 * 1024, max_unpacked_bytes=1024, max_files=2)
    data = make_zip(("lib/", b""), ("lib/a.dart", b"a"), ("lib/b.dart", b"b"), ("lib/c.dart", b"c"))

    assert rejected(data, limits).problem == ZipProblem.TOO_MANY_FILES


def test_zip_bomb_is_rejected_before_decompressing() -> None:
    bomb = make_zip(("lib/zeros.dart", b"\0" * (10 * 1024 * 1024)))
    assert len(bomb) < 20 * 1024  # 10 MB of zeros squeezes into a few KB

    error = rejected(bomb)

    assert error.problem == ZipProblem.TOO_LARGE_UNPACKED
    assert "0.0625 MB" in str(error)


def test_unpacked_limit_counts_all_files_together() -> None:
    limits = ZipLimits(max_zip_bytes=1024 * 1024, max_unpacked_bytes=1000, max_files=10)
    data = make_zip(("lib/a.dart", b"a" * 600), ("lib/b.dart", b"b" * 600))

    assert rejected(data, limits).problem == ZipProblem.TOO_LARGE_UNPACKED


def test_zip_that_lies_about_its_size_is_never_read_past_the_lie() -> None:
    data = bytearray(make_zip(("lib/zeros.dart", b"\0" * 100_000)))
    central = data.find(b"PK\x01\x02")
    struct.pack_into("<I", data, 22, 10)  # local header: uncompressed size
    struct.pack_into("<I", data, central + 24, 10)  # central directory: uncompressed size

    assert rejected(bytes(data)).problem == ZipProblem.BROKEN


def test_negative_header_offset_is_a_broken_zip() -> None:
    """Found by the fuzz test: zipfile raised a bare ValueError (negative seek)."""
    data = bytearray(make_zip(("lib/main.dart", b"x")))
    end_record = data.rfind(b"PK\x05\x06")
    offset = struct.unpack_from("<I", data, end_record + 16)[0]
    struct.pack_into("<I", data, end_record + 16, offset + 1000)  # central directory offset

    assert rejected(bytes(data)).problem == ZipProblem.BROKEN


def test_only_kept_files_are_decompressed_and_counted() -> None:
    data = make_zip(
        ("build/huge.bin", b"\0" * (10 * 1024 * 1024)),
        ("lib/main.dart", b"void main() {}"),
    )

    archive = validate(data)

    assert archive.paths == ["build/huge.bin", "lib/main.dart"]
    assert archive.read(keep=lambda path: path.startswith("lib/")) == [
        ArchiveFile("lib/main.dart", b"void main() {}")
    ]


def test_metadata_checks_cover_files_that_are_not_kept() -> None:
    data = make_zip(("lib/main.dart", b"ok"), ("build/../../evil", b"x"))

    with pytest.raises(ZipRejected) as error:
        validate(data)

    assert error.value.problem == ZipProblem.UNSAFE_PATH


def test_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        ZipLimits(max_zip_bytes=0, max_unpacked_bytes=1, max_files=1)


def test_corrupted_bytes_never_escape_as_other_errors() -> None:
    """Flip random bytes of a valid zip: the result is either read or ZipRejected."""
    original = make_zip(
        ("lib/main.dart", b"void main() { print('salom'); }" * 20),
        ("lib/src/cart.dart", b"class Cart {}" * 30),
        compression=zipfile.ZIP_DEFLATED,
    )
    rng = random.Random(20261001)  # fixed seed: the same cases on every run

    for _ in range(500):
        corrupted = bytearray(original)
        for _ in range(rng.randint(1, 4)):
            corrupted[rng.randrange(len(corrupted))] = rng.randrange(256)
        try:
            files = validate(bytes(corrupted)).read()
        except ZipRejected:
            continue
        assert sum(len(f.data) for f in files) <= LIMITS.max_unpacked_bytes
