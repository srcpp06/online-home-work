"""One isolated container for untrusted code (SPEC §3.6).

Every container runs as uid 1000 with all capabilities dropped, no new privileges, memory
without swap, CPU and process limits, a size-limited /tmp, and no network unless asked
for. Files go in with put_archive (no bind mounts). Output is read as a stream while the
container runs, so the caller can stop it at the first failed test, and its size is capped.
The container is always removed.
"""

import contextlib
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from docker.types import LogConfig
from requests.exceptions import RequestException

from judge.core.profile import RunnerProfile
from judge.packaging.tar_archive import make_tar
from judge.packaging.zip_validator import ArchiveFile

HOME_DIR = "/home/ohw"
APP_DIR = f"{HOME_DIR}/app"
SANDBOX_USER = "1000:1000"


@dataclass(frozen=True)
class NodeSettings:
    """Judge settings of this server (SPEC §6), the same for every profile."""

    cpu_shares: int  # JUDGE_CPU_SHARES: the site and the database win CPU contention
    max_output_bytes: int  # JUDGE_MAX_OUTPUT_KB
    runtime: str = "runc"  # JUDGE_RUNTIME, later runsc (gVisor)
    pids_limit: int = 256


@dataclass(frozen=True)
class SandboxLimits:
    memory_mb: int
    cpus: float
    tmp_mb: int
    cpu_shares: int
    max_output_bytes: int
    runtime: str
    pids_limit: int

    @classmethod
    def for_profile(cls, profile: RunnerProfile, node: NodeSettings) -> Self:
        return cls(
            memory_mb=profile.memory_mb,
            cpus=profile.cpus,
            tmp_mb=profile.tmp_mb,
            cpu_shares=node.cpu_shares,
            max_output_bytes=node.max_output_bytes,
            runtime=node.runtime,
            pids_limit=node.pids_limit,
        )


@dataclass(frozen=True)
class ContainerRun:
    exit_code: int | None
    wall_ms: int
    timed_out: bool
    oom_killed: bool
    output_limit_exceeded: bool
    stopped_early: bool  # on_line asked to stop
    stdout: str
    stderr: str

    def describe(self) -> str:
        """Short status for logs, e.g. "exit 1, out of memory, 3.2 s"."""
        parts = ["timed out" if self.timed_out else f"exit {self.exit_code}"]
        if self.oom_killed:
            parts.append("out of memory")
        if self.output_limit_exceeded:
            parts.append("output limit exceeded")
        if self.stopped_early:
            parts.append("stopped at the first failure")
        return ", ".join([*parts, f"{self.wall_ms / 1000:.1f} s"])


# Called with every stdout line while the container runs; returning True kills it.
LineHandler = Callable[[str], bool]


class Sandbox:
    """Use as ``with Sandbox(...) as sandbox:``; the container is removed on exit."""

    def __init__(
        self,
        client: docker.DockerClient,
        image: str,
        command: Sequence[str],
        limits: SandboxLimits,
        *,
        network: bool = False,
    ) -> None:
        self._client = client
        self._image = image
        self._command = list(command)
        self._limits = limits
        self._network = network
        self._container: Container | None = None

    def __enter__(self) -> Self:
        limits = self._limits
        self._container = self._client.containers.create(
            self._image,
            self._command,
            user=SANDBOX_USER,
            working_dir=APP_DIR,
            network_mode=None if self._network else "none",
            mem_limit=f"{limits.memory_mb}m",
            memswap_limit=f"{limits.memory_mb}m",
            nano_cpus=int(limits.cpus * 1_000_000_000),
            cpu_shares=limits.cpu_shares,
            pids_limit=limits.pids_limit,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            tmpfs={"/tmp": f"rw,nosuid,nodev,size={limits.tmp_mb}m"},  # noqa: S108 -- in the container
            runtime=limits.runtime,
            # Output is read through attach; nothing is written to the host's disk.
            log_config=LogConfig(type="none"),
        )
        # Docker would create a missing working directory owned by root.
        self.put_files([])
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._container is not None:
            with contextlib.suppress(NotFound):
                self._container.remove(force=True)

    @property
    def container(self) -> Container:
        if self._container is None:
            raise RuntimeError("use Sandbox as a context manager")
        return self._container

    def put_files(self, files: Sequence[ArchiveFile]) -> None:
        """Place files under the app directory; they and their folders belong to uid 1000."""
        app = APP_DIR.removeprefix(f"{HOME_DIR}/")
        self.container.put_archive(HOME_DIR, make_tar(files, prefix=app))

    def run(self, timeout_s: float, on_line: LineHandler | None = None) -> ContainerRun:
        container = self.container
        limit = self._limits.max_output_bytes
        stream = container.attach(stdout=True, stderr=True, stream=True, logs=False, demux=True)
        timed_out = threading.Event()

        def on_timeout() -> None:
            timed_out.set()
            self._kill()

        # Kills happen off this thread: it must keep reading the stream meanwhile, or the
        # daemon blocks on writing and the kill waits for a container that can't finish.
        timer = threading.Timer(timeout_s, on_timeout)
        timer.daemon = True
        stdout, stderr, pending = bytearray(), bytearray(), b""
        output_limit_exceeded = stopped_early = False
        started = time.monotonic()
        container.start()
        timer.start()
        try:
            for out, err in stream:
                # After a kill the stream is still read to the end: if nobody reads it,
                # the daemon blocks on writing and can't finish the container.
                if output_limit_exceeded or stopped_early:
                    continue
                if len(stdout) + len(stderr) + len(out or b"") + len(err or b"") > limit:
                    output_limit_exceeded = True
                    self._kill_in_background()
                    continue
                stderr += err or b""
                stdout += out or b""
                if on_line is None or not out:
                    continue
                *lines, pending = (pending + out).split(b"\n")
                if any(on_line(_text(line)) for line in lines):
                    stopped_early = True
                    self._kill_in_background()
            if on_line is not None and pending and not (output_limit_exceeded or stopped_early):
                on_line(_text(pending))
        finally:
            timer.cancel()
        wall_ms = int((time.monotonic() - started) * 1000)

        exit_code = container.wait(timeout=60).get("StatusCode")
        container.reload()
        return ContainerRun(
            exit_code=exit_code,
            wall_ms=wall_ms,
            timed_out=timed_out.is_set(),
            oom_killed=bool(container.attrs["State"].get("OOMKilled")),
            output_limit_exceeded=output_limit_exceeded,
            stopped_early=stopped_early,
            stdout=_text(stdout),
            stderr=_text(stderr),
        )

    def commit(self, repository: str | None = None, tag: str | None = None) -> str:
        """Save the container's files as an image; returns the image id."""
        return self.container.commit(repository=repository, tag=tag).id

    def _kill_in_background(self) -> None:
        threading.Thread(target=self._kill, daemon=True).start()

    def _kill(self) -> None:
        # Fails when the container already stopped or the daemon is busy finishing it.
        with contextlib.suppress(APIError, RequestException):
            self.container.kill()


def _text(data: bytes | bytearray) -> str:
    return bytes(data).decode("utf-8", errors="replace")
