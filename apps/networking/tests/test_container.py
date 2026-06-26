from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from apps.networking.src.container import (
    run_container,
    stop_container,
    get_status,
    redeploy,
)


#
# ---------------------------------------------------------------------
# run_container
# ---------------------------------------------------------------------
#

@patch("apps.networking.src.container._client")
def test_run_container(mock_client):
    container = MagicMock()
    container.id = "abc123"

    mock_client.containers.run.return_value = container

    result = run_container(
        image="demo:latest",
        container_name="demo",
        port=8000,
        env_vars={"ENV": "prod"},
    )

    mock_client.images.pull.assert_called_once_with("demo:latest")

    mock_client.containers.run.assert_called_once_with(
        image="demo:latest",
        name="demo",
        ports={"8000/tcp": 8000},
        environment={"ENV": "prod"},
        detach=True,
        restart_policy={"Name": "unless-stopped"},
    )

    assert result == "abc123"


@patch("apps.networking.src.container._client")
def test_run_container_defaults_env_vars(mock_client):
    container = MagicMock()
    container.id = "xyz"

    mock_client.containers.run.return_value = container

    run_container(
        image="demo",
        container_name="demo",
        port=5000,
    )

    args = mock_client.containers.run.call_args.kwargs

    assert args["environment"] == {}


#
# ---------------------------------------------------------------------
# stop_container
# ---------------------------------------------------------------------
#

@patch("apps.networking.src.container._client")
def test_stop_container_existing(mock_client):
    container = MagicMock()

    mock_client.containers.get.return_value = container

    stop_container("demo")

    container.stop.assert_called_once()
    container.remove.assert_called_once()


@patch("apps.networking.src.container._client")
def test_stop_container_missing(mock_client):
    mock_client.containers.get.side_effect = NotFound("missing")

    stop_container("demo")

    mock_client.containers.get.assert_called_once_with("demo")


#
# ---------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------
#

@patch("apps.networking.src.container._client")
def test_get_status_existing(mock_client):
    container = MagicMock()
    container.status = "running"

    mock_client.containers.get.return_value = container

    status = get_status("demo")

    container.reload.assert_called_once()

    assert status == "running"


@patch("apps.networking.src.container._client")
def test_get_status_missing(mock_client):
    mock_client.containers.get.side_effect = NotFound("missing")

    assert get_status("demo") is None


#
# ---------------------------------------------------------------------
# redeploy
# ---------------------------------------------------------------------
#

@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_first_deployment(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    No container currently exists.
    This is the initial deployment.
    """

    mock_client.containers.get.side_effect = [
        NotFound("missing old"),
        NotFound("missing current"),
    ]

    mock_run_container.return_value = "new-container"

    mock_health.return_value = True

    result = redeploy(
        image="demo:latest",
        container_name="demo",
        port=8000,
    )

    assert result == "new-container"

    mock_run_container.assert_called_once()

    mock_health.assert_called_once_with(
        host="localhost",
        port=8000,
        timeout=10,
    )

@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_success(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    Existing container is renamed.
    New deployment becomes healthy.
    Old deployment is removed.
    """

    previous = MagicMock()
    previous.status = "running"

    mock_client.containers.get.side_effect = [
        NotFound("no stale"),
        previous,
    ]

    mock_run_container.return_value = "new-id"
    mock_health.return_value = True

    result = redeploy(
        image="demo:v2",
        container_name="demo",
        port=8000,
    )

    assert result == "new-id"

    previous.rename.assert_called_once_with("demo_old")
    previous.reload.assert_called_once()
    previous.stop.assert_called_once()
    previous.remove.assert_called_once()


@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_removes_stale_old_container(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    A leftover demo_old container should be removed before deployment.
    """

    stale = MagicMock()
    stale.status = "running"

    current = MagicMock()

    mock_client.containers.get.side_effect = [
        stale,
        current,
    ]

    mock_run_container.return_value = "container-id"
    mock_health.return_value = True

    redeploy(
        image="demo:v2",
        container_name="demo",
        port=8000,
    )

    stale.stop.assert_called_once()
    stale.remove.assert_called_once()

    current.rename.assert_called_once_with("demo_old")


@patch("apps.networking.src.container.stop_container")
@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_failed_health_check_rolls_back(
    mock_client,
    mock_run_container,
    mock_health,
    mock_stop_container,
):
    """
    Failed health check restores previous deployment.
    """

    previous = MagicMock()
    restored = MagicMock()

    mock_client.containers.get.side_effect = [
        NotFound("no stale"),   # stale _old doesn't exist
        previous,               # current deployment
        restored,               # fetch demo_old during rollback
    ]

    mock_run_container.return_value = "new-id"
    mock_health.return_value = False

    with pytest.raises(RuntimeError) as exc:
        redeploy(
            image="demo:v2",
            container_name="demo",
            port=8000,
        )

    assert str(exc.value) == (
        "Deploy failed, rolled back to previous version"
    )

    mock_stop_container.assert_called_once_with("demo")

    previous.rename.assert_called_once_with("demo_old")

    restored.rename.assert_called_once_with("demo")
    restored.start.assert_called_once()


@patch("apps.networking.src.container.stop_container")
@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_failed_health_without_previous_container(
    mock_client,
    mock_run_container,
    mock_health,
    mock_stop_container,
):
    """
    Health check fails during the first deployment.
    There is nothing to restore.
    """

    mock_client.containers.get.side_effect = [
        NotFound("no stale"),
        NotFound("no current"),
    ]

    mock_run_container.return_value = "container-id"
    mock_health.return_value = False

    with pytest.raises(RuntimeError):
        redeploy(
            image="demo:v2",
            container_name="demo",
            port=8000,
        )

    mock_stop_container.assert_called_once_with("demo")


@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_stale_old_container_already_stopped(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    If demo_old already exists but isn't running,
    it should simply be removed.
    """

    stale = MagicMock()
    stale.status = "exited"

    current = MagicMock()

    mock_client.containers.get.side_effect = [
        stale,
        current,
    ]

    mock_run_container.return_value = "container-id"
    mock_health.return_value = True

    redeploy(
        image="demo:v2",
        container_name="demo",
        port=8000,
    )

    stale.stop.assert_not_called()
    stale.remove.assert_called_once()


@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_calls_health_check_with_correct_arguments(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    Health check should always use localhost,
    deployment port,
    and a 10 second timeout.
    """

    mock_client.containers.get.side_effect = [
        NotFound("missing"),
        NotFound("missing"),
    ]

    mock_run_container.return_value = "container-id"
    mock_health.return_value = True

    redeploy(
        image="demo:v2",
        container_name="demo",
        port=5050,
    )

    mock_health.assert_called_once_with(
        host="localhost",
        port=5050,
        timeout=10,
    )


@patch("apps.networking.src.container.wait_for_health")
@patch("apps.networking.src.container.run_container")
@patch("apps.networking.src.container._client")
def test_redeploy_returns_new_container_id(
    mock_client,
    mock_run_container,
    mock_health,
):
    """
    redeploy should return exactly the ID returned by run_container.
    """

    mock_client.containers.get.side_effect = [
        NotFound("missing"),
        NotFound("missing"),
    ]

    mock_run_container.return_value = "docker-container-123456"

    mock_health.return_value = True

    result = redeploy(
        image="demo:v2",
        container_name="demo",
        port=8000,
    )

    assert result == "docker-container-123456"