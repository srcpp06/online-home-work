"""The one way to reach Docker: the worker, the CLI and the tests all connect here."""

import docker

# Saving a Flutter container as an image (commit) writes gigabytes and took longer than
# the SDK's default 60 s on a slow disk, failing a good build. Run time limits don't rely
# on this: the sandbox stops a run with its own timer.
API_TIMEOUT_S = 600


def connect() -> docker.DockerClient:
    """A client to the local Docker; raises DockerException when it can't be reached."""
    client = docker.from_env(timeout=API_TIMEOUT_S)
    client.ping()
    return client
