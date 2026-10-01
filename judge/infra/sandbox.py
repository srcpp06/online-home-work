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
from typing import Any, Self

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
    sample_memory: bool = False  # poll docker stats for the peak; for measurements


@dataclass(frozen=True)
class SandboxLimits:
    memory_mb: int
    cpus: float
    tmp_mb: int
    cpu_shares: int
    max_output_bytes: int
    runtime: str
    pids_limit: int
    sample_memory: bool = False

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
            sample_memory=node.sample_memory,
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
    peak_memory_mb: int | None = None  # only when the limits ask for memory sampling

    def describe(self) -> str:
        """Short status for logs, e.g. "exit 1, out of memory, 3.2 s"."""
        parts = ["timed out" if self.timed_out else f"exit {self.exit_code}"]
        if self.oom_killed:
            parts.append("out of memory")
        if self.output_limit_exceeded:
            parts.append("output limit exceeded")
        if self.stopped_early:
            parts.append("stopped at the first failure")
        if self.peak_memory_mb is not None:
            parts.append(f"peak {self.peak_memory_mb} MB")
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
        sampler = _MemorySampler(container) if self._limits.sample_memory else None
        started = time.monotonic()
        container.start()
        timer.start()
        if sampler is not None:
            sampler.start()
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
            if sampler is not None:
                sampler.stop()
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
            peak_memory_mb=sampler.peak_mb if sampler is not None else None,
        )

    def commit(
        self,
        repository: str | None = None,
        tag: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> str:
        """Save the container's files as an image; returns the image id."""
        conf = {"Labels": labels} if labels else None
        return self.container.commit(repository=repository, tag=tag, conf=conf).id

    def _kill_in_background(self) -> None:
        threading.Thread(target=self._kill, daemon=True).start()

    def _kill(self) -> None:
        # Fails when the container already stopped or the daemon is busy finishing it.
        with contextlib.suppress(APIError, RequestException):
            self.container.kill()


class _MemorySampler:
    """Polls docker stats while the container runs and keeps the highest memory use.

    Sampling can miss a spike shorter than the interval; good enough for measurements.
    """

    INTERVAL_S = 0.2

    def __init__(self, container: Container) -> None:
        self._container = container
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._peak_bytes = 0

    @property
    def peak_mb(self) -> int | None:
        return self._peak_bytes // (1024 * 1024) if self._peak_bytes else None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=5)

    def _poll(self) -> None:
        while not self._stopped.is_set():
            with contextlib.suppress(APIError, RequestException, KeyError, TypeError):
                stats = self._container.stats(stream=False, one_shot=True)
                self._peak_bytes = max(self._peak_bytes, _used_bytes(stats["memory_stats"]))
            self._stopped.wait(self.INTERVAL_S)


def _used_bytes(memory: dict[str, Any]) -> int:
    """Like `docker stats`: usage minus the inactive page cache (cgroup v2 or v1 names)."""
    cache = memory.get("stats", {})
    inactive = cache.get("inactive_file", cache.get("total_inactive_file", 0))
    return max(0, memory.get("usage", 0) - inactive)


def _text(data: bytes | bytearray) -> str:
    return bytes(data).decode("utf-8", errors="replace")
