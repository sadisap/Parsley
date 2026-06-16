# after a container starts, poll it until it responds or we give up

import time

import requests

DEFAULT_TIMEOUT = 10
POLL_INTERVAL = 0.5


def wait_for_health(host: str, port: int, path: str = "/", timeout: float = DEFAULT_TIMEOUT) -> bool:
    """
    Poll http://{host}:{port}{path} until it returns any response or `timeout`
    seconds pass.

    Returns True if the container responded, False if it never did.
    """
    url = f"http://{host}:{port}{path}"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            requests.get(url, timeout=1)
            return True
        except requests.RequestException:
            time.sleep(POLL_INTERVAL)

    return False
