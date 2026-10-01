"""Tar archives for Docker's put_archive (SPEC §3.4, step 3)."""

import io
import tarfile
import time
from collections.abc import Sequence

from judge.packaging.zip_validator import ArchiveFile

SANDBOX_UID = 1000
SANDBOX_GID = 1000


def make_tar(files: Sequence[ArchiveFile], prefix: str = "", mtime: float | None = None) -> bytes:
    """Pack files owned by the sandbox user (uid/gid 1000).

    Every parent directory gets its own entry; otherwise Docker creates it owned by root
    and the tests can't write next to the files. ``mtime`` defaults to now: compile caches
    in the image must see the files as newer than the cache, never older.
    """
    stamp = time.time() if mtime is None else mtime
    prefix = prefix.strip("/")
    buffer = io.BytesIO()
    written: set[str] = set()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for directory in _folders(prefix, files):
            if directory not in written:
                written.add(directory)
                tar.addfile(_entry(directory, tarfile.DIRTYPE, 0o755, stamp))
        for file in files:
            info = _entry(_join(prefix, file.path), tarfile.REGTYPE, 0o644, stamp)
            info.size = len(file.data)
            tar.addfile(info, io.BytesIO(file.data))
    return buffer.getvalue()


def _join(prefix: str, path: str) -> str:
    return f"{prefix}/{path}" if prefix else path


def _folders(prefix: str, files: Sequence[ArchiveFile]) -> list[str]:
    """The prefix and every parent folder of the files, parents before children."""
    paths = [prefix] if prefix else []
    paths += [_join(prefix, file.path).rpartition("/")[0] for file in files]
    folders: list[str] = []
    for path in filter(None, paths):
        parts = path.split("/")
        folders += ["/".join(parts[:depth]) for depth in range(1, len(parts) + 1)]
    return folders


def _entry(name: str, kind: bytes, mode: int, mtime: float) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.mode = mode
    info.mtime = mtime
    info.uid, info.gid = SANDBOX_UID, SANDBOX_GID
    info.uname = info.gname = "ohw"
    return info
