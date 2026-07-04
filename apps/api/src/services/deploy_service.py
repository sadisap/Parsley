# apps/api/src/services/deploy_service.py

import os
from apps.networking.src.traefik import build_traefik_labels
from apps.networking.src.container import redeploy


def deploy_to_vps(
    project_id: str,
    subdomain: str,
    image_tag: str,
    port: int,
) -> str:
    """
    Builds Traefik labels and calls redeploy() from container.py.
    Rollback is handled automatically if health check fails.
    Returns the container name.
    """

    base_domain = os.getenv("BASE_DOMAIN", "")
    container_name = f"parsley-{project_id}"

    labels = build_traefik_labels(
        project_id=project_id,
        subdomain=subdomain,
        port=port,
        base_domain=base_domain,
    )

    redeploy(
        image=image_tag,
        container_name=container_name,
        port=port,
        labels=labels,
    )

    return container_name