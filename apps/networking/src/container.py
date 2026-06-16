# run a pushed Docker image on this server, and swap out old
# versions of a deployment when redeploying

import docker
from docker.errors import NotFound

_client = docker.from_env()


def run_container(image: str, container_name: str, port: int, env_vars: dict[str, str] | None = None) -> str:
    """
    Pull `image` and start it as `container_name`, publishing `port` on the host
    at the same port inside the container.

    Returns the new container's ID.
    """
    _client.images.pull(image)

    container = _client.containers.run(
        image,
        name=container_name,
        ports={f"{port}/tcp": port},
        environment=env_vars or {},
        detach=True,
        restart_policy={"Name": "unless-stopped"},
    )
    return container.id


def stop_container(container_name: str) -> None:
    """Stop and remove `container_name` if it exists. No-op if it doesn't."""
    try:
        container = _client.containers.get(container_name)
    except NotFound:
        return

    container.stop()
    container.remove()


def redeploy(image: str, container_name: str, port: int, env_vars: dict[str, str] | None = None) -> str:
    """
    Replace whatever is currently running as `container_name` with a fresh
    container started from `image`. Returns the new container's ID.
    """
    stop_container(container_name)
    return run_container(image, container_name, port, env_vars)


def get_status(container_name: str) -> str | None:
    """Return the container's status (e.g. "running", "exited"), or None if it doesn't exist."""
    try:
        container = _client.containers.get(container_name)
    except NotFound:
        return None
    return container.status
