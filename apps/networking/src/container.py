# container.py
# run a pushed Docker image on the VPS via SSH, swap out old
# versions of a deployment when redeploying

import paramiko
import os

# from apps.networking.src.health import wait_for_health


def _get_ssh_client() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    host = os.getenv("VPS_HOST")
    user = os.getenv("VPS_USER", "root")
    key_path = os.getenv("VPS_SSH_KEY_PATH")
    password = os.getenv("VPS_PASSWORD")

    if key_path:
        ssh.connect(hostname=host, username=user, key_filename=key_path)
    else:
        ssh.connect(hostname=host, username=user, password=password)

    return ssh


def _run_remote(client: paramiko.SSHClient, cmd: str, ignore_errors: bool = False) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()

    if exit_status != 0 and not ignore_errors:
        raise RuntimeError(f"Remote command failed: {cmd}\n{err}")

    return out.strip()


def container_exists(client: paramiko.SSHClient, container_name: str) -> bool:
    out = _run_remote(
        client,
        f"docker ps -a --filter name=^{container_name}$ --format '{{{{.Names}}}}'",
        ignore_errors=True,
    )
    return container_name in out


def run_container(
    client: paramiko.SSHClient,
    image: str,
    container_name: str,
    port: int,
    env_vars: dict[str, str] | None = None,
    labels: list[str] | None = None,
) -> str:
    """
    Pull an image and start it as a detached container on the VPS.
    Returns the new container ID.
    """
    _run_remote(client, f"docker pull {image}")

    env_flags = ""
    if env_vars:
        env_flags = " ".join(f'-e {k}="{v}"' for k, v in env_vars.items())

    label_flags = ""
    if labels:
        label_flags = " ".join(labels) if labels else ""

    cmd = (
        f"docker run -d --name {container_name} "
        f"--network traefik-net --restart unless-stopped "
        f"{label_flags} {env_flags} {image}"
    )

    container_id = _run_remote(client, cmd)
    return container_id


def stop_container(client: paramiko.SSHClient, container_name: str) -> None:
    """
    Stop and remove a container if it exists.
    """
    if not container_exists(client, container_name):
        return

    _run_remote(client, f"docker stop {container_name}", ignore_errors=True)
    _run_remote(client, f"docker rm {container_name}", ignore_errors=True)

def _check_health_remote(client: paramiko.SSHClient, container_name: str, port: int, timeout: int = 10) -> bool:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = _run_remote(
            client,
            f"docker inspect -f '{{{{.State.Running}}}}' {container_name}",
            ignore_errors=True,
        )
        if "true" in out.lower():
            time.sleep(3)
            out2 = _run_remote(
                client,
                f"docker inspect -f '{{{{.State.Running}}}}' {container_name}",
                ignore_errors=True,
            )
            return "true" in out2.lower()
        time.sleep(0.5)
    return False

def redeploy(
    image: str,
    container_name: str,
    port: int,
    env_vars: dict[str, str] | None = None,
    labels: list[str] | None = None,
) -> str:
    """
    Deploy a new container on the VPS with automatic rollback.

    1. Remove any stale "<container_name>_old" container.
    2. Rename the currently running container to "<container_name>_old".
    3. Start the new container.
    4. Wait up to 10 seconds for a health check.
    5. If healthy: remove the old container.
       Else: remove the new container, restore the previous container, raise.
    """

    client = _get_ssh_client()

    try:
        old_container_name = f"{container_name}_old"

        # remove any leftover "_old" container
        if container_exists(client, old_container_name):
            _run_remote(client, f"docker stop {old_container_name}", ignore_errors=True)
            _run_remote(client, f"docker rm {old_container_name}", ignore_errors=True)

        had_previous = container_exists(client, container_name)

        # rename current deployment
        if had_previous:
            _run_remote(client, f"docker rename {container_name} {old_container_name}")

        # start the new deployment
        try:
            new_container_id = run_container(
                client=client,
                image=image,
                container_name=container_name,
                port=port,
                env_vars=env_vars,
                labels=labels,
            )
        except Exception:
            # new container failed to even start — restore old immediately
            if had_previous:
                _run_remote(client, f"docker rename {old_container_name} {container_name}", ignore_errors=True)
                _run_remote(client, f"docker start {container_name}", ignore_errors=True)
            raise

        # wait for health check
        # healthy = wait_for_health(
        #     host=container_name,
        #     # host=os.getenv("VPS_HOST"),
        #     port=port,
        #     timeout=10,
        # )

        healthy = _check_health_remote(client, container_name, port)

        if healthy:
            if had_previous:
                _run_remote(client, f"docker stop {old_container_name}", ignore_errors=True)
                _run_remote(client, f"docker rm {old_container_name}", ignore_errors=True)
            return new_container_id

        # health check failed — roll back
        stop_container(client, container_name)

        if had_previous:
            _run_remote(client, f"docker rename {old_container_name} {container_name}")
            _run_remote(client, f"docker start {container_name}")

        raise RuntimeError("Deploy failed, rolled back to previous version")

    finally:
        client.close()



def get_status(container_name: str) -> str | None:
    """
    Return the Docker status of a container on the VPS, or None if it does not exist.
    """
    client = _get_ssh_client()
    try:
        if not container_exists(client, container_name):
            return None

        status = _run_remote(
            client,
            f"docker inspect -f '{{{{.State.Status}}}}' {container_name}",
            ignore_errors=True,
        )
        return status or None
    finally:
        client.close()