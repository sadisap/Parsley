from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from routes.webhook import router  # noqa: E402


SECRET = "test-secret"
DELIVERY_ID = "delivery-123"


class FakeAdapter:
    def __init__(self, project: Any = SimpleNamespace(id="project-1"), result: Any = None) -> None:
        self.project = project
        self.result = result if result is not None else {"deployment_id": "deploy-1"}
        self.calls: list[tuple[Any, ...]] = []

    def find_project_by_repo(self, repo_full_name: str, repo_clone_url: str) -> Any | None:
        self.calls.append(("find", repo_full_name, repo_clone_url))
        return self.project

    def trigger_redeploy(self, project: Any, payload: dict[str, Any], delivery_id: str) -> Any:
        self.calls.append(("redeploy", project, payload, delivery_id))
        return self.result


def make_app(adapter: FakeAdapter | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if adapter is not None:
        app.state.webhook_adapter = adapter
    return app


def make_client(adapter: FakeAdapter | None = None) -> TestClient:
    return TestClient(make_app(adapter))


def signed_body(payload: Any, secret: str = SECRET) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": DELIVERY_ID,
        "X-Hub-Signature-256": f"sha256={signature}",
    }
    return raw, headers


def post_webhook(client: TestClient, payload: Any, *, event: str = "push", secret: str = SECRET, headers: dict[str, str] | None = None):
    raw, signed_headers = signed_body(payload, secret=secret)
    signed_headers["X-GitHub-Event"] = event
    if headers:
        signed_headers.update(headers)
    return client.post("/webhook", content=raw, headers=signed_headers)


def test_missing_secret_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("PARSLEY_GITHUB_WEBHOOK_SECRET", raising=False)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"}}
    raw, headers = signed_body(payload)
    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 500
    assert response.json()["detail"] == "GitHub webhook secret is not configured."


def test_ping_event_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"zen": "keep it logically awesome"}
    response = post_webhook(client, payload, event="ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "event": "ping", "delivery_id": DELIVERY_ID}


def test_unsupported_event_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"action": "opened"}
    response = post_webhook(client, payload, event="pull_request")

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "unsupported event"
    assert response.json()["event"] == "pull_request"


def test_missing_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"}}
    raw, headers = signed_body(payload)
    headers.pop("X-Hub-Signature-256")

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing webhook signature."


def test_invalid_signature_format_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"}}
    raw, headers = signed_body(payload)
    headers["X-Hub-Signature-256"] = "not-a-valid-signature"

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature format."


def test_unsupported_signature_algorithm_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"}}
    raw, headers = signed_body(payload)
    headers["X-Hub-Signature-256"] = "sha1=abc123"

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Unsupported webhook signature algorithm. Expected sha256."


def test_bad_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"}}
    raw, headers = signed_body(payload)
    headers["X-Hub-Signature-256"] = "sha256=deadbeef"

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Webhook signature verification failed."


def test_invalid_json_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    raw = b"{"
    signature = hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": DELIVERY_ID,
        "X-Hub-Signature-256": f"sha256={signature}",
    }

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook payload is not valid JSON."


def test_non_object_json_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = ["not", "an", "object"]
    raw, headers = signed_body(payload)

    response = client.post("/webhook", content=raw, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook payload must be a JSON object."


def test_non_main_branch_push_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {
        "ref": "refs/heads/feature",
        "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"},
    }
    response = post_webhook(client, payload)

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "non-main branch push"
    assert response.json()["ref"] == "refs/heads/feature"


def test_missing_repository_info_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main"}
    response = post_webhook(client, payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing repository information."


def test_missing_full_name_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {"ref": "refs/heads/main", "repository": {"clone_url": "https://example.com/org/repo.git"}}
    response = post_webhook(client, payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing repository full_name."


def test_missing_clone_url_falls_back_to_html_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    adapter = FakeAdapter()
    client = make_client(adapter)

    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "org/repo",
            "html_url": "https://github.com/org/repo",
        },
    }

    response = post_webhook(client, payload)

    assert response.status_code == 200
    assert adapter.calls[0] == ("find", "org/repo", "https://github.com/org/repo.git")
    assert response.json()["repository"] == "org/repo"


def test_missing_clone_url_and_html_url_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "org/repo",
        },
    }
    response = post_webhook(client, payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing repository clone_url."


def test_missing_adapter_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    client = make_client()
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"},
    }
    response = post_webhook(client, payload)

    assert response.status_code == 500
    assert "No webhook adapter configured" in response.json()["detail"]


def test_project_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    adapter = FakeAdapter(project=None)
    client = make_client(adapter)
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"},
    }

    response = post_webhook(client, payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "No Parsley project is registered for repository 'org/repo'."
    assert adapter.calls == [("find", "org/repo", "https://example.com/org/repo.git")]


def test_successful_redeploy_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    adapter = FakeAdapter(result={"deployment_id": "deploy-123"})
    client = make_client(adapter)
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"},
    }

    response = post_webhook(client, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["event"] == "push"
    assert body["delivery_id"] == DELIVERY_ID
    assert body["repository"] == "org/repo"
    assert body["result"] == {"deployment_id": "deploy-123"}
    assert adapter.calls[0] == ("find", "org/repo", "https://example.com/org/repo.git")
    assert adapter.calls[1][0] == "redeploy"
    assert adapter.calls[1][3] == DELIVERY_ID


def test_non_json_serializable_result_is_stringified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)

    adapter = FakeAdapter(result={"a", "b"})
    client = make_client(adapter)
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "org/repo", "clone_url": "https://example.com/org/repo.git"},
    }

    response = post_webhook(client, payload)

    assert response.status_code == 200
    assert isinstance(response.json()["result"], str)