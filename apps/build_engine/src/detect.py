from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SUPPORTED_FRAMEWORKS = {"react", "express", "fastapi", "flask", "static"}

DEFAULT_PORTS = {
    "react": 5173,
    "express": 3000,
    "fastapi": 8000,
    "flask": 5000,
    "static": 80,
}

DEFAULT_COMMANDS = {
    "react": {"build": "npm run build", "start": "npm run preview"},
    "express": {"build": None, "start": "node index.js"},
    "fastapi": {"build": None, "start": "uvicorn main:app --host 0.0.0.0 --port 8000"},
    "flask": {"build": None, "start": "flask --app app run --host 0.0.0.0 --port 5000"},
    "static": {"build": None, "start": None},
}

SKIP_PARTS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".next", "dist", "build"}

JS_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".tsx"}
PY_PORT_RE = re.compile(r"(?:port\s*=\s*|--port[=\s]+)(\d{2,5})", re.IGNORECASE)
EXPRESS_PORT_RE = re.compile(r"\.listen\(\s*(?:[A-Za-z_][A-Za-z0-9_.]*\s*\|\|\s*)?(\d{2,5})")
FASTAPI_REQ_RE = re.compile(r"^fastapi(\[[^\]]+\])?([=<>!;\s]|$)", re.MULTILINE)
FLASK_REQ_RE = re.compile(r"^flask(\[[^\]]+\])?([=<>!;\s]|$)", re.MULTILINE)


def _package_json(repo: Path) -> dict[str, Any] | None:
    path = repo / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not parse package.json: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _requirements_text(repo: Path) -> str | None:
    path = repo / "requirements.txt"
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").lower()
    except OSError as exc:
        raise ValueError(f"Could not read requirements.txt: {exc}") from exc


def _dict_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}


def _iter_files(repo: Path, suffixes: set[str]):
    for path in repo.rglob("*"):
        if path.suffix.lower() not in suffixes:
            continue
        if SKIP_PARTS.intersection(path.parts):
            continue
        yield path


def _module_name(path: Path, repo: Path) -> str:
    return ".".join(path.relative_to(repo).with_suffix("").parts)


def _detect_framework(repo: Path) -> str:
    pkg = _package_json(repo)
    if pkg is not None:
        deps = _dict_section(pkg, "dependencies")
        deps.update(_dict_section(pkg, "devDependencies"))
        if "react" in deps:
            return "react"
        if "express" in deps:
            return "express"

    req = _requirements_text(repo)
    if req is not None:
        if FASTAPI_REQ_RE.search(req):
            return "fastapi"
        if FLASK_REQ_RE.search(req):
            return "flask"

    for py_file in _iter_files(repo, {".py"}):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if "from fastapi import" in text or "fastapi(" in text:
            return "fastapi"
        if "from flask import" in text or "flask(" in text:
            return "flask"

    if any(path.name == "index.html" for path in repo.rglob("index.html")):
        return "static"

    raise ValueError("Framework not supported")


def _scan_express_port(repo: Path) -> int:
    for js_file in _iter_files(repo, JS_SUFFIXES):
        try:
            text = js_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = EXPRESS_PORT_RE.search(text)
        if match:
            return int(match.group(1))
    return DEFAULT_PORTS["express"]


def _scan_python_port(repo: Path, framework: str) -> int:
    for py_file in _iter_files(repo, {".py"}):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = PY_PORT_RE.search(text)
        if match:
            return int(match.group(1))
    return DEFAULT_PORTS[framework]


def _detect_port(repo: Path, framework: str) -> int:
    if framework == "express":
        return _scan_express_port(repo)
    if framework in {"fastapi", "flask"}:
        return _scan_python_port(repo, framework)
    return DEFAULT_PORTS[framework]


def _find_python_app_module(repo: Path, framework: str, default_module: str) -> str:
    for py_file in _iter_files(repo, {".py"}):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if framework == "fastapi":
            if "from fastapi import" in text or "fastapi(" in text:
                return _module_name(py_file, repo)
        elif framework == "flask":
            if "from flask import" in text or "flask(" in text:
                return _module_name(py_file, repo)
    return default_module


def _find_express_entry(repo: Path) -> str | None:
    for js_file in _iter_files(repo, JS_SUFFIXES):
        try:
            text = js_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if ".listen(" in text:
            return js_file.relative_to(repo).as_posix()
    return None


def _detect_commands(repo: Path, framework: str, port: int) -> dict[str, str | None]:
    defaults = DEFAULT_COMMANDS[framework]

    if framework == "static":
        return defaults.copy()

    if framework in {"fastapi", "flask"}:
        module = _find_python_app_module(repo, framework, "main" if framework == "fastapi" else "app")
        start = (
            f"uvicorn {module}:app --host 0.0.0.0 --port {port}"
            if framework == "fastapi"
            else f"flask --app {module} run --host 0.0.0.0 --port {port}"
        )
        return {"build": None, "start": start}

    pkg = _package_json(repo)
    scripts = _dict_section(pkg, "scripts") if pkg is not None else {}

    if framework == "react":
        build = "npm run build" if "build" in scripts else defaults["build"]
        start = "npm run preview" if "preview" in scripts else ("npm run start" if "start" in scripts else defaults["start"])
        return {"build": build, "start": start}

    if "start" in scripts:
        start = "npm run start"
    else:
        main = pkg.get("main") if pkg is not None and isinstance(pkg.get("main"), str) else None
        start = f"node {main}" if main else _find_express_entry(repo) or defaults["start"]

    build = "npm run build" if "build" in scripts else None
    return {"build": build, "start": start}


def detect(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()

    if not repo.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo}")
    if not repo.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo}")

    framework = _detect_framework(repo)
    port = _detect_port(repo, framework)
    commands = _detect_commands(repo, framework, port)

    return {
        "framework": framework,
        "port": port,
        "start_command": commands["start"],
        "build_command": commands["build"],
    }