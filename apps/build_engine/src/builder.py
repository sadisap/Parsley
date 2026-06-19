from __future__ import annotations

import os
import re
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

EXCLUDED_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".next",
    "coverage",
    "htmlcov",
    ".DS_Store",
}

EXCLUDED_PATTERNS = ("*.pyc", "*.pyo", "*.pyd", "*.swp", "*.swo", "*.log", ".env", ".env.*")
DOCKER_TAG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")


class BuildError(RuntimeError):
    pass


def _repo_name(repo_path: Path) -> str:
    name = repo_path.name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"[-_.]{2,}", "-", name).strip("-._")
    return name or "app"


def _template_path(framework: str) -> Path:
    template = Path(__file__).resolve().parent / "templates" / TEMPLATE_MAP[framework]
    if not template.is_file():
        raise FileNotFoundError(f"Template not found: {template}")
    return template


def _image_name(repo_path: Path, image_repository: str | None) -> str:
    if image_repository is not None:
        image_repository = image_repository.strip()
        if not image_repository or any(c.isspace() for c in image_repository):
            raise ValueError("image_repository is invalid")
        return image_repository

    username = os.getenv("DOCKERHUB_USERNAME", "").strip().lower()
    if not username:
        raise ValueError("Provide image_repository or set DOCKERHUB_USERNAME")
    return f"{username}/{_repo_name(repo_path)}"


def _port(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return 8000
    try:
        port = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid port: {value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"Port out of range: {port}")
    return port


def _default_start_command(framework: str, port: int) -> str:
    if framework == "react":
        return f"serve -s dist -l {port}"
    if framework == "static":
        return f"python -m http.server {port} --bind 0.0.0.0"
    if framework == "express":
        return "node index.js"
    if framework == "fastapi":
        return f"uvicorn main:app --host 0.0.0.0 --port {port}"
    if framework == "flask":
        return f"flask run --host 0.0.0.0 --port {port}"
    raise ValueError(f"Unsupported framework: {framework}")


def _render_template(template_text: str, framework: str, detection: Mapping[str, Any]) -> tuple[str, int, str, str]:
    port = _port(detection.get("port"))

    build_command = str(
        detection.get("build_command")
        or {
            "react": "npm run build",
            "express": "npm install",
            "fastapi": "pip install --no-cache-dir -r requirements.txt",
            "flask": "pip install --no-cache-dir -r requirements.txt",
            "static": "true",
        }[framework]
    )

    start_command = (
        f"serve -s dist -l {port}"
        if framework == "react"
        else str(detection.get("start_command") or _default_start_command(framework, port))
    )

    rendered = (
        template_text.replace("{{PORT}}", str(port))
        .replace("{{START_COMMAND}}", start_command)
        .replace("{{BUILD_COMMAND}}", build_command)
    )
    return rendered, port, build_command, start_command


def _copy_repo(repo_path: Path, build_dir: Path) -> None:
    ignore = shutil.ignore_patterns(*EXCLUDED_NAMES, *EXCLUDED_PATTERNS)

    for item in repo_path.iterdir():
        if item.name in EXCLUDED_NAMES or any(item.match(pattern) for pattern in EXCLUDED_PATTERNS):
            continue
        if item.is_symlink():
            continue

        dest = build_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest, ignore=ignore)
            else:
                shutil.copy2(item, dest)
        except (OSError, shutil.Error) as exc:
            raise BuildError(f"Failed to copy '{item.name}': {exc}") from exc


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise BuildError(f"Required executable not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        msg = [f"Command failed: {' '.join(cmd)}"]
        if exc.stdout:
            msg.append(f"stdout:\n{exc.stdout.strip()}")
        if exc.stderr:
            msg.append(f"stderr:\n{exc.stderr.strip()}")
        raise BuildError("\n\n".join(msg)) from exc


def build(
    repo_path: str | Path,
    detection: Mapping[str, Any],
    image_repository: str | None = None,
    tag: str = "latest",
) -> dict[str, Any]:
    if not isinstance(detection, Mapping):
        raise TypeError("detection must be a mapping")

    repo_path = Path(repo_path).expanduser().resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo_path}")
    if not tag or not DOCKER_TAG_RE.match(tag):
        raise ValueError(f"Invalid Docker tag: {tag!r}")

    framework = str(detection.get("framework", "")).strip().lower()
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"Unsupported framework: {framework}")

    template = _template_path(framework)
    image = f"{_image_name(repo_path, image_repository)}:{tag}"

    with tempfile.TemporaryDirectory(prefix="parsley-build-") as tmpdir:
        build_dir = Path(tmpdir)

        _copy_repo(repo_path, build_dir)

        template_text = template.read_text(encoding="utf-8")
        rendered, port, build_command, start_command = _render_template(template_text, framework, detection)
        (build_dir / "Dockerfile").write_text(rendered, encoding="utf-8")

        _run(["docker", "build", "-t", image, "."], cwd=build_dir)
        _run(["docker", "push", image])

    return {
        "image": image,
        "framework": framework,
        "template": str(template),
        "port": port,
        "build_command": build_command,
        "start_command": start_command,
    }