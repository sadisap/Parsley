# apps/api/src/services/deploy_service.py

import paramiko
import os
from apps.networking.src.traefik import build_traefik_labels, build_docker_run_command


def deploy_to_vps(
    project_id: str,
    subdomain: str,
    image_tag: str,
    port: int,
    env_vars: dict = None,
) -> str:
    """
    SSHes into VPS, pulls the image, and runs it with Traefik labels.
    Returns the container name.
    """

    host = os.getenv("VPS_HOST")
    user = os.getenv("VPS_USER", "root")
    key_path = os.getenv("VPS_SSH_KEY_PATH")
    password = os.getenv("VPS_PASSWORD")
    base_domain = os.getenv("BASE_DOMAIN", "")

    container_name = f"parsley-{project_id}"

    # generate traefik labels and docker run command
    labels = build_traefik_labels(
        project_id=project_id,
        subdomain=subdomain,
        port=port,
        base_domain=base_domain,
    )
    run_cmd = build_docker_run_command(
        image_tag=image_tag,
        container_name=container_name,
        labels=labels,
        env_vars=env_vars or {},
    )

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_path:
            ssh.connect(hostname=host, username=user, key_filename=key_path)
        else:
            ssh.connect(hostname=host, username=user, password=password)

        _run_remote(ssh, f"docker pull {image_tag}")
        _run_remote(ssh, f"docker stop {container_name} || true")
        _run_remote(ssh, f"docker rm {container_name} || true")
        _run_remote(ssh, run_cmd)

    finally:
        ssh.close()

    return container_name


def _run_remote(client: paramiko.SSHClient, cmd: str) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()

    if exit_status != 0 and "No such container" not in err:
        raise Exception(f"Remote command failed: {cmd}\n{err}")

    return out