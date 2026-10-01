import io
import tarfile

from judge.packaging.tar_archive import make_tar
from judge.packaging.zip_validator import ArchiveFile


def members(data: bytes) -> list[tarfile.TarInfo]:
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        return tar.getmembers()


def read_file(data: bytes, name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        extracted = tar.extractfile(name)
        assert extracted is not None
        return extracted.read()


def test_files_and_their_folders_belong_to_the_sandbox_user() -> None:
    data = make_tar([ArchiveFile("lib/src/cart.dart", b"class Cart {}")], prefix="app")

    entries = members(data)

    assert [(m.name, m.isdir()) for m in entries] == [
        ("app", True),
        ("app/lib", True),
        ("app/lib/src", True),
        ("app/lib/src/cart.dart", False),
    ]
    assert {(m.uid, m.gid) for m in entries} == {(1000, 1000)}
    assert [m.mode for m in entries] == [0o755, 0o755, 0o755, 0o644]
    assert read_file(data, "app/lib/src/cart.dart") == b"class Cart {}"


def test_shared_folders_appear_once() -> None:
    data = make_tar([ArchiveFile("lib/a.dart", b"a"), ArchiveFile("lib/b.dart", b"b")])

    assert [m.name for m in members(data)] == ["lib", "lib/a.dart", "lib/b.dart"]


def test_files_are_stamped_with_the_current_time_by_default() -> None:
    data = make_tar([ArchiveFile("lib/a.dart", b"a")])

    assert all(m.mtime > 1_700_000_000 for m in members(data))


def test_mtime_can_be_fixed() -> None:
    data = make_tar([ArchiveFile("lib/a.dart", b"a")], mtime=1_234_567_890)

    assert {m.mtime for m in members(data)} == {1_234_567_890}


def test_unicode_names_survive() -> None:
    data = make_tar([ArchiveFile("lib/oʻquvchi.dart", b"// salom")])

    assert read_file(data, "lib/oʻquvchi.dart") == b"// salom"


def test_prefix_folder_is_created_even_without_files() -> None:
    entries = members(make_tar([], prefix="app"))

    assert [(m.name, m.isdir(), m.uid) for m in entries] == [("app", True, 1000)]
