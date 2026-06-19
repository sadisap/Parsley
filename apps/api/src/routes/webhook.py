from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/webhook", tags=["webhook"])
SUPPORTED_PUSH_REF = "refs/heads/main"


class WebhookAdapter(Protocol):
    def find_project_by_repo(self, repo_full_name: str, repo_clone_url: str) -> Any | None: ...

    def trigger_redeploy(self, project: Any, payload: dict[str, Any], delivery_id: str) -> Any: ...


@dataclass(frozen=True)
class GitHubRepoInfo:
    full_name: str
    clone_url: str
    html_url: str | None = None


def _get_webhook_secret() -> str:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET") or os.getenv("PARSLEY_GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub webhook secret is not configured.",
        )
    return secret


def _verify_signature(raw_body: bytes, signature_header: str | None, secret: str) -> None:
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook signature.")

    try:
        algorithm, provided_signature = signature_header.split("=", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature format.") from exc

    if algorithm != "sha256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported webhook signature algorithm. Expected sha256.",
        )

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook signature verification failed.")


def _parse_json(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook payload is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook payload must be a JSON object.")

    return payload


def _extract_repo_info(payload: dict[str, Any]) -> GitHubRepoInfo:
    repo = payload.get("repository")
    if not isinstance(repo, dict) or not repo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository information.")

    full_name = repo.get("full_name")
    if not isinstance(full_name, str) or not full_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository full_name.")

    clone_url = repo.get("clone_url")
    if not isinstance(clone_url, str) or not clone_url.strip():
        html_url = repo.get("html_url")
        if isinstance(html_url, str) and html_url.strip():
            clone_url = html_url.removesuffix("/") + ".git"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing repository clone_url.")

    html_url = repo.get("html_url")
    if not isinstance(html_url, str) or not html_url.strip():
        html_url = None

    return GitHubRepoInfo(full_name=full_name, clone_url=clone_url, html_url=html_url)


def _is_main_branch_push(payload: dict[str, Any]) -> bool:
    return payload.get("ref") == SUPPORTED_PUSH_REF


def _get_adapter(request: Request) -> WebhookAdapter:
    adapter = getattr(request.app.state, "webhook_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No webhook adapter configured. Attach an object with "
                "find_project_by_repo() and trigger_redeploy() to app.state.webhook_adapter."
            ),
        )
    return adapter


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


@router.post("")
async def receive_github_webhook(request: Request) -> JSONResponse:
    event = request.headers.get("X-GitHub-Event")
    delivery_id = request.headers.get("X-GitHub-Delivery") or ""
    signature = request.headers.get("X-Hub-Signature-256")

    raw_body = await request.body()
    secret = _get_webhook_secret()
    _verify_signature(raw_body, signature, secret)
    payload = _parse_json(raw_body)

    if event == "ping":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "event": "ping", "delivery_id": delivery_id},
        )

    if event != "push":
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "ignored", "reason": "unsupported event", "event": event},
        )

    if not _is_main_branch_push(payload):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "ignored", "reason": "non-main branch push", "ref": payload.get("ref")},
        )

    repo_info = _extract_repo_info(payload)
    adapter = _get_adapter(request)

    project = adapter.find_project_by_repo(repo_info.full_name, repo_info.clone_url)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Parsley project is registered for repository '{repo_info.full_name}'.",
        )

    result = _json_safe(adapter.trigger_redeploy(project, payload, delivery_id))

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "accepted",
            "event": event,
            "delivery_id": delivery_id,
            "repository": repo_info.full_name,
            "result": result,
        },
    )