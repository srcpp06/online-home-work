"""Sandbox isolation against a real Docker daemon (marker: docker)."""

import dataclasses

import docker
import pytest
from docker.errors import NotFound

from judge.infra.sandbox import ContainerRun, Sandbox, SandboxLimits
from judge.packaging.zip_validator import ArchiveFile

pytestmark = pytest.mark.docker

LIMITS = SandboxLimits(
    memory_mb=128,
    cpus=0.5,
    tmp_mb=16,
    cpu_shares=512,
    max_output_bytes=64 * 1024,
    runtime="runc",
    pids_limit=256,
)


def run_shell(
    client: docker.DockerClient,
    image: str,
    script: str,
    timeout_s: float = 30,
    limits: SandboxLimits = LIMITS,
    files: list[ArchiveFile] | None = None,
    stop_at: str | None = None,
) -> tuple[ContainerRun, list[str]]:
    lines: list[str] = []

    def on_line(line: str) -> bool:
        lines.append(line)
        return line == stop_at

    with Sandbox(client, image, ["bash", "-c", script], limits) as sandbox:
        if files:
            sandbox.put_files(files)
        return sandbox.run(timeout_s, on_line=on_line), lines


def test_runs_as_sandbox_user_in_the_app_folder(docker_client, dart_base_image) -> None:
    run, lines = run_shell(docker_client, dart_base_image, "id -u; id -g; pwd")

    assert run.exit_code == 0
    assert lines == ["1000", "1000", "/home/ohw/app"]


def test_put_files_are_owned_by_the_sandbox_user(docker_client, dart_base_image) -> None:
    files = [ArchiveFile("lib/src/cart.dart", b"class Cart {}")]

    run, lines = run_shell(
        docker_client,
        dart_base_image,
        "cat lib/src/cart.dart; echo; stat -c %u:%g . lib lib/src lib/src/cart.dart; touch lib/new",
        files=files,
    )

    assert run.exit_code == 0
    assert lines == ["class Cart {}", "1000:1000", "1000:1000", "1000:1000", "1000:1000"]


def test_has_no_network(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "curl -sS --max-time 5 https://pub.dev")

    assert run.exit_code != 0
    assert "Could not resolve host" in run.stderr


def test_has_no_capabilities(docker_client, dart_base_image) -> None:
    script = "grep -E '^Cap(Eff|Prm):' /proc/self/status"

    _, lines = run_shell(docker_client, dart_base_image, script)

    assert lines == ["CapPrm:\t0000000000000000", "CapEff:\t0000000000000000"]


def test_limits_reach_the_container(docker_client, dart_base_image) -> None:
    """Read back from Docker itself: the same on cgroup v1 and v2 hosts."""
    with Sandbox(docker_client, dart_base_image, ["true"], LIMITS) as sandbox:
        sandbox.container.reload()
        host = sandbox.container.attrs["HostConfig"]
        config = sandbox.container.attrs["Config"]

    assert config["User"] == "1000:1000"
    assert host["NetworkMode"] == "none"
    assert host["Memory"] == host["MemorySwap"] == 128 * 1024 * 1024
    assert host["NanoCpus"] == 500_000_000
    assert host["CpuShares"] == 512
    assert host["PidsLimit"] == 256
    assert host["CapDrop"] == ["ALL"]
    assert host["SecurityOpt"] == ["no-new-privileges"]
    assert host["Tmpfs"] == {"/tmp": "rw,nosuid,nodev,size=16m"}  # noqa: S108
    assert host["LogConfig"]["Type"] == "none"
    assert host["Runtime"] == "runc"


def test_memory_limit_has_no_swap(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "head -c 200M /dev/zero | tail")

    assert run.oom_killed


def test_app_folder_is_writable_without_files(docker_client, dart_base_image) -> None:
    run, lines = run_shell(docker_client, dart_base_image, "touch made && stat -c %u:%g . made")

    assert run.exit_code == 0
    assert lines == ["1000:1000", "1000:1000"]


def test_tmp_is_writable_and_small(docker_client, dart_base_image) -> None:
    run, _ = run_shell(
        docker_client, dart_base_image, "echo ok > /tmp/a && head -c 32M /dev/zero > /tmp/big"
    )

    assert run.exit_code != 0
    assert "No space left on device" in run.stderr


def test_stdout_and_stderr_are_kept_apart(docker_client, dart_base_image) -> None:
    run, lines = run_shell(docker_client, dart_base_image, "echo out; echo err >&2; printf last")

    assert lines == ["out", "last"]
    assert run.stdout == "out\nlast"
    assert run.stderr == "err\n"


def test_wall_clock_timeout_kills_the_container(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "sleep 30", timeout_s=1)

    assert run.timed_out
    assert run.wall_ms < 10_000


def test_running_out_of_memory_is_detected(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "head -c 512M /dev/zero | tail")

    assert run.oom_killed
    assert not run.timed_out


def test_output_flood_is_cut_off(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "yes flood")

    assert run.output_limit_exceeded
    assert len(run.stdout) <= LIMITS.max_output_bytes
    assert run.wall_ms < 10_000  # once the kill blocked the reader and hung for 60 s


def test_line_handler_can_stop_the_run(docker_client, dart_base_image) -> None:
    run, lines = run_shell(
        docker_client,
        dart_base_image,
        "for i in 1 2 3 4 5 6 7 8 9 10; do echo $i; sleep 0.3; done",
        stop_at="3",
    )

    assert run.stopped_early
    assert lines == ["1", "2", "3"]
    assert run.wall_ms < 2_500


def test_container_is_removed_even_after_an_error(docker_client, dart_base_image) -> None:
    sandbox = Sandbox(docker_client, dart_base_image, ["true"], LIMITS)
    with pytest.raises(RuntimeError), sandbox:
        container_id = sandbox.container.id
        raise RuntimeError("boom")

    with pytest.raises(NotFound):
        docker_client.containers.get(container_id)


def test_commit_saves_the_files(docker_client, dart_base_image) -> None:
    with Sandbox(docker_client, dart_base_image, ["bash", "-c", "echo hi > made"], LIMITS) as s:
        s.run(30)
        image_id = s.commit()
    try:
        _, lines = run_shell(docker_client, image_id, "cat made")
        assert lines == ["hi"]
    finally:
        docker_client.images.remove(image_id, force=True)


def test_peak_memory_is_sampled_when_asked(docker_client, dart_base_image) -> None:
    limits = dataclasses.replace(LIMITS, memory_mb=512, sample_memory=True)
    hold_150_mb = "x=$(head -c 150M /dev/zero | tr '\\0' a); sleep 1.5; echo ${#x}"

    run, lines = run_shell(docker_client, dart_base_image, hold_150_mb, limits=limits)

    assert lines == [str(150 * 1024 * 1024)]
    assert run.peak_memory_mb is not None
    assert 140 <= run.peak_memory_mb <= 512
    assert f"peak {run.peak_memory_mb} MB" in run.describe()


def test_memory_is_not_sampled_by_default(docker_client, dart_base_image) -> None:
    run, _ = run_shell(docker_client, dart_base_image, "true")

    assert run.peak_memory_mb is None
