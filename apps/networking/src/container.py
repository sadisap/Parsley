# run a pushed Docker image on this server, and swap out old
# versions of a deployment when redeploying

import docker
from docker.errors import NotFound

from apps.networking.src.health import wait_for_health

_client = docker.from_env()


def run_container(
    image: str,
    container_name: str,
    port: int,
    env_vars: dict[str, str] | None = None,
) -> str:
    """
    Pull an image and start it as a detached container.

    Returns the new container ID.
    """
    _client.images.pull(image)

    container = _client.containers.run(
        image=image,
        name=container_name,
        ports={f"{port}/tcp": port},
        environment=env_vars or {},
        detach=True,
        restart_policy={"Name": "unless-stopped"},
    )

    return container.id


def stop_container(container_name: str) -> None:
    """
    Stop and remove a container if it exists.
    """

    try:
        container = _client.containers.get(container_name)
    except NotFound:
        return

    container.stop()
    container.remove()


def redeploy(
    image: str,
    container_name: str,
    port: int,
    env_vars: dict[str, str] | None = None,
) -> str:
    """
    Deploy a new container with automatic rollback.

    Deployment process:

    1. Remove any stale "<container_name>_old" container.
    2. Rename the currently running container to "<container_name>_old".
    3. Start the new container.
    4. Wait up to 10 seconds for a health check.
    5. If healthy:
           remove the old container.
       Else:
           remove the new container,
           restore the previous container,
           raise RuntimeError.
    """

    old_container_name = f"{container_name}_old"

    #
    # Remove any leftover "_old" container.
    #
    try:
        stale = _client.containers.get(old_container_name)

        if stale.status == "running":
            stale.stop()

        stale.remove()

    except NotFound:
        pass

    previous_container = None

    #
    # Rename the current deployment.
    #
    try:
        previous_container = _client.containers.get(container_name)
        previous_container.rename(old_container_name)

    except NotFound:
        previous_container = None

    #
    # Start the new deployment.
    #
    new_container_id = run_container(
        image=image,
        container_name=container_name,
        port=port,
        env_vars=env_vars,
    )

    #
    # Wait for the application to become healthy.
    #
    healthy = wait_for_health(
        host="localhost",
        port=port,
        timeout=10,
    )

    #
    # Success.
    #
    if healthy:

        if previous_container is not None:

            previous_container.reload()

            try:
                previous_container.stop()
            except Exception:
                pass

            try:
                previous_container.remove()
            except Exception:
                pass

        return new_container_id

    #
    # Health check failed.
    # Roll back.
    #
    stop_container(container_name)

    if previous_container is not None:

        restored_container = _client.containers.get(old_container_name)

        restored_container.rename(container_name)

        restored_container.start()

    raise RuntimeError(
        "Deploy failed, rolled back to previous version"
    )


def get_status(container_name: str) -> str | None:
    """
    Return the Docker status of a container,
    or None if it does not exist.
    """

    try:
        container = _client.containers.get(container_name)
    except NotFound:
        return None

    container.reload()

    return container.status