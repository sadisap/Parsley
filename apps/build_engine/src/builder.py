from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

SUPPORTED_FRAMEWORKS = {"react", "express", "fastapi", "flask", "static"}

TEMPLATE_MAP = {
    "react": "react-vite.dockerfile",
    "express": "express.dockerfile",
    "fastapi": "fastapi.dockerfile",
    "flask": "flask.dockerfile",
    "static": "static.dockerfile",
}


def _repo_name(repo_path: Path) -> str:
    return repo_path.name.lower().replace(" ", "-")


def _image_name(repo_path: Path, image_repository: str | None) -> str:
    if image_repository:
        return image_repository

    username = os.getenv("DOCKERHUB_USERNAME")
    if username:
        return f"{username}/{_repo_name(repo_path)}"

    return _repo_name(repo_path)


def _template_path(framework: str) -> Path:
    base = Path(__file__).resolve().parent / "templates"
    template_name = TEMPLATE_MAP[framework]
    template = base / template_name
    if not template.exists():
        raise FileNotFoundError(f"Template not found: {template}")
    return template


def _render_template(template_text: str, framework: str, detection: Mapping[str, Any]) -> str:
    port = str(detection.get("port", 80))
    build_command = str(detection.get("build_command") or "npm run build")

    if framework == "react":
        start_command = f"serve -s dist -l {port}"
    elif framework == "static":
        start_command = f"python -m http.server {port} --bind 0.0.0.0"
    else:
        start_command = str(
            detection.get("start_command")
            or {
                "express": "node index.js",
                "fastapi": f"uvicorn main:app --host 0.0.0.0 --port {port}",
                "flask": f"flask run --host 0.0.0.0 --port {port}",
            }[framework]
        )

    return (
        template_text
        .replace("{{PORT}}", port)
        .replace("{{START_COMMAND}}", start_command)
        .replace("{{BUILD_COMMAND}}", build_command)
    )


def build(
    repo_path: str | Path,
    detection: Mapping[str, Any],
    image_repository: str | None = None,
    tag: str = "latest",
) -> dict[str, Any]:
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo_path}")

    framework = str(detection.get("framework", "")).lower()
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"Unsupported framework: {framework}")

    template = _template_path(framework)
    image = f"{_image_name(repo_path, image_repository)}:{tag}"

    with tempfile.TemporaryDirectory(prefix="parsley-build-") as tmpdir:
        build_dir = Path(tmpdir)

        for item in repo_path.iterdir():
            if item.name in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}:
                continue
            dest = build_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        template_text = template.read_text(encoding="utf-8")
        (build_dir / "Dockerfile").write_text(
            _render_template(template_text, framework, detection),
            encoding="utf-8",
        )

        subprocess.run(["docker", "build", "-t", image, "."], cwd=build_dir, check=True)
        subprocess.run(["docker", "push", image], check=True)

    return {
        "image": image,
        "framework": framework,
        "template": str(template),
    }
