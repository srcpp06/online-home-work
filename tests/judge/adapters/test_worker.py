"""The worker loop with a stand-in runner: no Docker needed."""

import threading
import time
from collections.abc import Callable

import pytest

from apps.system import queue
from apps.system.models import Job, WorkerNode
from judge.adapters.worker import Worker, WorkerSettings, check_memory, parse_slots
from judge.config import ConfigError, read_env
from tests.apps.world import World

SETTINGS = WorkerSettings("node-t", {"fast": 2, "heavy": 1}, 0.05, 30, 0)


def test_slots_are_lane_count_pairs() -> None:
    assert parse_slots("heavy:1, fast:2") == {"heavy": 1, "fast": 2}


@pytest.mark.parametrize(
    "text", ["", "heavy", "gpu:1", "heavy:x", "fast:1,fast:2", "fast:0,heavy:0"]
)
def test_bad_slots_are_refused(text: str) -> None:
    with pytest.raises(ConfigError, match="JUDGE_SLOTS"):
        parse_slots(text)


def test_slots_must_fit_in_memory() -> None:
    check_memory({"heavy": 1, "fast": 1}, {"heavy": 1536, "fast": 1024}, 12000, 3072)

    with pytest.raises(ConfigError, match=r"need 5632 MB .* but 5000 MB is free"):
        check_memory({"heavy": 3, "fast": 1}, {"heavy": 1536, "fast": 1024}, 8072, 3072)


def test_settings_come_from_the_environment() -> None:
    env = {
        "JUDGE_NODE_NAME": "node-2",
        "JUDGE_SLOTS": "heavy:3,fast:2",
        "JUDGE_POLL_INTERVAL_S": "1",
        "JUDGE_LEASE_S": "60",
        "JUDGE_RESERVED_MEMORY_MB": "3072",
    }

    settings = WorkerSettings.from_env(env)

    assert (settings.node_name, settings.slots, settings.lease_s) == (
        "node-2",
        {"heavy": 3, "fast": 2},
        60,
    )
    with pytest.raises(ConfigError, match="JUDGE_LEASE_S"):
        WorkerSettings.from_env({k: v for k, v in env.items() if k != "JUDGE_LEASE_S"})


def run_until(worker: Worker, done: Callable[[], bool], timeout_s: float = 10) -> None:
    stop = threading.Event()
    thread = threading.Thread(target=worker.run, args=(stop,))
    thread.start()
    try:
        deadline = time.monotonic() + timeout_s
        while not done() and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        stop.set()
        thread.join(10)
    assert done(), "the worker did not finish in time"


@pytest.mark.django_db(transaction=True)
def test_the_worker_runs_every_job_once(world: World) -> None:
    jobs = [queue.enqueue_judge(world.a.submission), queue.enqueue_build(world.a.version)]
    ran: list[int] = []
    lock = threading.Lock()

    def runner(client: object, config: object, job: Job) -> None:
        with lock:
            ran.append(job.pk)

    worker = Worker(SETTINGS, config=None, client=None, runner=runner)  # type: ignore[arg-type]
    run_until(worker, lambda: Job.objects.filter(status="done").count() == 2)

    assert sorted(ran) == sorted(job.pk for job in jobs)
    node = WorkerNode.objects.get(name="node-t")
    assert node.slots == {"fast": 2, "heavy": 1}


@pytest.mark.django_db(transaction=True)
def test_a_crashing_job_is_retried_then_given_up(world: World) -> None:
    job = queue.enqueue_judge(world.a.submission)

    def runner(client: object, config: object, job: Job) -> None:
        raise RuntimeError("container runtime exploded")

    worker = Worker(SETTINGS, config=None, client=None, runner=runner)  # type: ignore[arg-type]
    run_until(worker, lambda: Job.objects.filter(pk=job.pk, status="failed").exists())

    job.refresh_from_db()
    assert job.attempts == queue.MAX_ATTEMPTS
    assert "container runtime exploded" in job.last_error


@pytest.mark.django_db(transaction=True)
def test_a_heavy_slot_also_runs_fast_jobs(world: World) -> None:
    job = queue.enqueue_judge(world.a.submission)  # dart: the fast lane
    heavy_only = WorkerSettings("node-h", {"heavy": 1}, 0.05, 30, 0)

    worker = Worker(heavy_only, config=None, client=None, runner=lambda *_: None)  # type: ignore[arg-type]
    run_until(worker, lambda: Job.objects.filter(pk=job.pk, status="done").exists())


def test_a_heavy_slot_has_room_for_either_lane() -> None:
    """A heavy slot may run a fast job, so it is counted with the larger of the two."""
    with pytest.raises(ConfigError, match=r"need 2048 MB"):
        check_memory({"heavy": 1}, {"heavy": 1024, "fast": 2048}, 2000, 0)


@pytest.mark.django_db
def test_a_missing_base_image_stops_the_worker_with_the_fix(world: World) -> None:
    """Without it every build would fail three times and end as "Tizim xatosi"."""
    from docker.errors import ImageNotFound

    from judge.adapters.worker import check_base_images
    from judge.config import JudgeConfig

    class Images:
        def get(self, tag: str) -> object:
            if tag.startswith("ohw-base-flutter"):
                raise ImageNotFound(tag)
            return object()

    class Client:
        images = Images()

    config = JudgeConfig.from_env(read_env())

    with pytest.raises(ConfigError, match=r"ohw-base-flutter:\S+ .*make base-images"):
        check_base_images(Client(), config)  # type: ignore[arg-type]
