"""`manage.py judge_worker`: the judge worker (judge.adapters.worker). The only part of
the project that talks to Docker; it runs in its own container next to the site."""

import logging
import signal
import threading
from typing import Any

import docker
from django.core.management.base import BaseCommand, CommandError

from judge.adapters.worker import (
    Worker,
    WorkerSettings,
    check_memory,
    lane_memory_mb,
    total_memory_mb,
)
from judge.config import ConfigError, JudgeConfig, read_env
from judge.infra import docker_client


class Command(BaseCommand):
    help = "Take build and judge jobs from the queue and run them in Docker"

    def handle(self, *args: Any, **options: Any) -> None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(threadName)s %(message)s")
        env = read_env()
        try:
            settings = WorkerSettings.from_env(env)
            config = JudgeConfig.from_env(env)
            check_memory(
                settings.slots, lane_memory_mb(), total_memory_mb(), settings.reserved_memory_mb
            )
        except ConfigError as error:
            raise CommandError(str(error)) from None
        try:
            client = docker_client.connect()
        except docker.errors.DockerException as error:
            raise CommandError(f"can't reach Docker: {error}") from None

        stop = threading.Event()

        def on_signal(signum: int, frame: object) -> None:
            self.stdout.write("stopping: finishing the running jobs first")
            stop.set()

        signal.signal(signal.SIGTERM, on_signal)
        signal.signal(signal.SIGINT, on_signal)
        Worker(settings, config, client).run(stop)
