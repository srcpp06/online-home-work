"""The judge worker (SPEC §3.9): slots per lane, each taking jobs from the queue table.

JUDGE_SLOTS=heavy:1,fast:1 starts one thread per slot. A thread takes a job of its lanes
(SLOT_LANES, SKIP LOCKED), keeps its lease alive while it runs, and marks it done or
failed. The main thread returns the jobs of dead workers (the reaper) and keeps this
node's heartbeat.
Scaling is configuration only: more slots, or another worker on another server.
"""

import logging
import os
import platform
import threading
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Self

import docker
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.system import queue
from apps.system.models import Job, WorkerNode
from apps.tasks.models import RunnerProfile
from judge.adapters.jobs import run_build, run_judge
from judge.config import ConfigError, JudgeConfig
from judge.core.profile import Lane

log = logging.getLogger("judge.worker")

# What each kind of slot takes, in order: a heavy slot with no heavy job waiting helps the
# fast lane, a fast slot never takes a heavy job it has no memory for (SPEC §3.9).
SLOT_LANES: dict[str, tuple[str, ...]] = {
    Lane.HEAVY: (Lane.HEAVY, Lane.FAST),
    Lane.FAST: (Lane.FAST,),
}


@dataclass(frozen=True)
class WorkerSettings:
    node_name: str
    slots: dict[str, int]  # lane -> parallel jobs
    poll_interval_s: float
    lease_s: int
    reserved_memory_mb: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        missing = [
            name
            for name in (
                "JUDGE_NODE_NAME",
                "JUDGE_SLOTS",
                "JUDGE_POLL_INTERVAL_S",
                "JUDGE_LEASE_S",
                "JUDGE_RESERVED_MEMORY_MB",
            )
            if not env.get(name)
        ]
        if missing:
            raise ConfigError(f"missing settings: {', '.join(missing)}")
        try:
            poll, lease, reserved = (
                float(env["JUDGE_POLL_INTERVAL_S"]),
                int(env["JUDGE_LEASE_S"]),
                int(env["JUDGE_RESERVED_MEMORY_MB"]),
            )
        except ValueError as error:
            raise ConfigError(f"JUDGE_* number settings: {error}") from None
        if poll <= 0 or lease < 10 or reserved < 0:
            raise ConfigError(
                "JUDGE_POLL_INTERVAL_S > 0, JUDGE_LEASE_S >= 10, JUDGE_RESERVED_MEMORY_MB >= 0"
            )
        return cls(env["JUDGE_NODE_NAME"], parse_slots(env["JUDGE_SLOTS"]), poll, lease, reserved)


def parse_slots(text: str) -> dict[str, int]:
    """ "heavy:1,fast:2" -> {"heavy": 1, "fast": 2}."""
    slots: dict[str, int] = {}
    for part in text.split(","):
        lane, _, count = part.strip().partition(":")
        if lane not in set(Lane) or not count.isdigit() or lane in slots:
            raise ConfigError(
                f"JUDGE_SLOTS: expected lane:count pairs of {', '.join(Lane)}, got {text!r}"
            )
        slots[lane] = int(count)
    if not any(slots.values()):
        raise ConfigError(f"JUDGE_SLOTS has no slots: {text!r}")
    return slots


def check_memory(
    slots: Mapping[str, int], lane_memory_mb: Mapping[str, int], total_mb: int, reserved_mb: int
) -> None:
    """Every slot running its largest possible job at once must fit next to the site and the
    database (JUDGE_RESERVED_MEMORY_MB). Refusing to start beats the kernel killing them."""
    per_slot = {
        lane: max(lane_memory_mb.get(taken, 0) for taken in SLOT_LANES[lane]) for lane in slots
    }
    needed = sum(count * per_slot[lane] for lane, count in slots.items())
    available = total_mb - reserved_mb
    if needed > available:
        parts = ", ".join(f"{lane} {count} x {per_slot[lane]} MB" for lane, count in slots.items())
        raise ConfigError(
            f"the slots need {needed} MB ({parts}) but {available} MB is free "
            f"({total_mb} MB minus JUDGE_RESERVED_MEMORY_MB={reserved_mb}). "
            "Lower JUDGE_SLOTS or the reserve, or use a bigger server."
        )


def lane_memory_mb() -> dict[str, int]:
    """The largest memory limit among the active profiles of each lane."""
    memory: dict[str, int] = {}
    for profile in RunnerProfile.objects.filter(is_active=True):
        limit = profile.judge_profile().memory_mb
        memory[profile.lane] = max(memory.get(profile.lane, 0), limit)
    return memory


def total_memory_mb() -> int:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)


Runner = Callable[[docker.DockerClient, JudgeConfig, Job], None]


def run_job(client: docker.DockerClient, config: JudgeConfig, job: Job) -> None:
    # The database guarantees the target matches the kind (system_job_target_matches_kind).
    if job.kind == Job.Kind.BUILD and job.task_version is not None:
        run_build(client, config, job.task_version)
    elif job.submission is not None:
        run_judge(client, config, job.submission)
    else:
        raise RuntimeError(f"job {job.pk} has nothing to run")


class Worker:
    def __init__(
        self,
        settings: WorkerSettings,
        config: JudgeConfig,
        client: docker.DockerClient,
        runner: Runner = run_job,
    ) -> None:
        self.settings = settings
        self.config = config
        self.client = client
        self.runner = runner

    def run(self, stop: threading.Event) -> None:
        """Work until ``stop`` is set; jobs already running are finished first."""
        self._register()
        threads = [
            threading.Thread(target=self._slot, args=(lane, stop), name=f"{lane}-{n}", daemon=True)
            for lane, count in self.settings.slots.items()
            for n in range(1, count + 1)
        ]
        for thread in threads:
            thread.start()
        log.info("worker %s: slots %s", self.settings.node_name, self.settings.slots)
        try:
            while not stop.is_set():
                close_old_connections()
                reaped = queue.reap()
                if reaped:
                    log.warning("returned %d jobs of stopped workers", reaped)
                WorkerNode.objects.filter(name=self.settings.node_name).update(
                    last_heartbeat=timezone.now()
                )
                stop.wait(self.settings.poll_interval_s)
        finally:
            for thread in threads:
                thread.join()
            connection.close()

    def _register(self) -> None:
        now = timezone.now()
        WorkerNode.objects.update_or_create(
            name=self.settings.node_name,
            defaults={
                "arch": platform.machine(),
                "slots": self.settings.slots,
                "started_at": now,
                "last_heartbeat": now,
            },
        )

    def _slot(self, lane: str, stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                close_old_connections()
                job = queue.claim(SLOT_LANES[lane], self.settings.node_name, self.settings.lease_s)
                if job is None:
                    stop.wait(self.settings.poll_interval_s)
                    continue
                self._process(job)
        finally:
            connection.close()

    def _process(self, job: Job) -> None:
        log.info("job %s: %s started", job.pk, job.kind)
        done = threading.Event()
        heartbeat = threading.Thread(target=self._keep_lease, args=(job, done), daemon=True)
        heartbeat.start()
        try:
            self.runner(self.client, self.config, job)
        except Exception:  # any failure goes back to the queue with its trace
            error = traceback.format_exc()
            log.error("job %s failed:\n%s", job.pk, error)
            queue.fail(job, error)
        else:
            queue.finish(job)
            log.info("job %s: done", job.pk)
        finally:
            done.set()
            heartbeat.join()

    def _keep_lease(self, job: Job, done: threading.Event) -> None:
        try:
            while not done.wait(self.settings.lease_s / 3):
                if not queue.extend_lease(job, self.settings.lease_s):
                    log.warning("job %s: lease lost (reaped)", job.pk)
                    return
        finally:
            connection.close()
