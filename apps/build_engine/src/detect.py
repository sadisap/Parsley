from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SUPPORTED_FRAMEWORKS = {
    "react",
    "vue",
    "next",
    "nuxt",
    "express",
    "fastapi",
    "flask",
    "django",
    "static",
}

DEFAULT_PORTS = {
    "react": 5173,
    "vue": 5173,
    "next": 3000,
    "nuxt": 3000,
    "express": 3000,
    "fastapi": 8000,
    "flask": 5000,
    "django": 8000,
    "static": 80,
}

DEFAULT_COMMANDS = {
    "react": {"build": "npm run build", "start": "npm run preview"},
    "vue": {"build": "npm run build", "start": "serve -s dist -l 5173"},
    "next": {"build": "npm run build", "start": "npm run start"},
    "nuxt": {"build": "npm run build", "start": "npm run start"},
    "express": {"build": None, "start": "node index.js"},
    "fastapi": {"build": None, "start": "uvicorn main:app --host 0.0.0.0 --port 8000"},
    "flask": {"build": None, "start": "flask --app app run --host 0.0.0.0 --port 5000"},
    "django": {"build": None, "start": "python manage.py runserver 0.0.0.0:8000"},
    "static": {"build": None, "start": None},
}

SKIP_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".next",
    ".nuxt",
    ".output",
    "dist",
    "build",
}

JS_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".json"}
PY_SUFFIXES = {".py", ".txt", ".toml", ".ini", ".cfg", ".json"}
PORT_RE = re.compile(r"(?:--port(?:=|\s+)|-p(?:=|\s+)|port\s*[:=]\s*)(\d{2,5})", re.IGNORECASE)
EXPRESS_PORT_RE = re.compile(r"\.listen\(\s*(?:[A-Za-z_][A-Za-z0-9_.]*\s*\|\|\s*)?(\d{2,5})")
RUNSERVER_PORT_RE = re.compile(r"runserver\s+(?:[\d.]+:)?(\d{2,5})", re.IGNORECASE)
FASTAPI_REQ_RE = re.compile(r"^fastapi(\[[^\]]+\])?([=<>!;\s]|$)", re.MULTILINE)
FLASK_REQ_RE = re.compile(r"^flask(\[[^\]]+\])?([=<>!;\s]|$)", re.MULTILINE)
DJANGO_REQ_RE = re.compile(r"^django(\[[^\]]+\])?([=<>!;\s]|$)", re.MULTILINE)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


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


def _has_named_file(repo: Path, names: set[str]) -> bool:
    return any(path.name in names for path in repo.rglob("*") if path.is_file() and not SKIP_PARTS.intersection(path.parts))


def _has_content(repo: Path, suffixes: set[str], needles: tuple[str, ...]) -> bool:
    for path in _iter_files(repo, suffixes):
        text = _read_text(path)
        if text is None:
            continue
        lowered = text.lower()
        if any(needle in lowered for needle in needles):
            return True
    return False


def _package_json(repo: Path) -> dict[str, Any] | None:
    path = repo / "package.json"
    if not path.is_file():
        return None
    text = _read_text(path)
    if text is None:
        raise ValueError("Could not read package.json")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse package.json: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _requirements_text(repo: Path) -> str | None:
    path = repo / "requirements.txt"
    if not path.is_file():
        return None
    text = _read_text(path)
    if text is None:
        raise ValueError("Could not read requirements.txt")
    return text.lower()


def _dependency_names(pkg: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        names.update(k.lower() for k in _dict_section(pkg, section).keys())
    return names


def _script_text(pkg: dict[str, Any]) -> str:
    scripts = _dict_section(pkg, "scripts")
    parts = [str(v) for v in scripts.values() if isinstance(v, str)]
    for key in ("name", "description", "packageManager"):
        value = pkg.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts).lower()


def _package_framework(pkg: dict[str, Any]) -> str | None:
    deps = _dependency_names(pkg)
    text = _script_text(pkg)

    if "next" in deps or "next.config." in text or any(
        key in text
        for key in ("next/head", "next/link", "next/navigation", "next/router")
    ):
        return "next"

    if "nuxt" in deps or "nuxt.config." in text or any(
        key in text
        for key in ("definenuxtconfig", "usenuxtapp", "<nuxtpage", "<nuxtlayout")
    ):
        return "nuxt"

    if "vue" in deps or any(path.name.endswith(".vue") for path in Path(".").glob("**/*.vue")):
        return "vue"

    if "react" in deps or any(key in text for key in ("reactdom", "createroot(", "from 'react'", 'from "react"')):
        return "react"

    if "express" in deps or any(key in text for key in ("require('express')", 'require("express")', "from 'express'", 'from "express"', ".listen(")):
        return "express"

    return None


def _detect_framework(repo: Path) -> str:
    pkg = _package_json(repo)
    if pkg is not None:
        framework = _package_framework(pkg)
        if framework is not None:
            return framework

    req = _requirements_text(repo)
    if req is not None:
        if DJANGO_REQ_RE.search(req):
            return "django"
        if FASTAPI_REQ_RE.search(req):
            return "fastapi"
        if FLASK_REQ_RE.search(req):
            return "flask"

    if _has_named_file(repo, {"manage.py"}) or _has_content(
        repo,
        {".py", ".txt", ".toml", ".ini", ".cfg"},
        ("from django import", "import django", "django.setup(", "django.conf", "django.core"),
    ):
        return "django"

    if _has_named_file(repo, {"next.config.js", "next.config.mjs", "next.config.cjs", "next.config.ts"}) or _has_content(
        repo,
        JS_SUFFIXES,
        ("next/head", "next/link", "next/navigation", "next/router"),
    ):
        return "next"

    if _has_named_file(repo, {"nuxt.config.js", "nuxt.config.mjs", "nuxt.config.cjs", "nuxt.config.ts", "app.vue"}) or _has_content(
        repo,
        JS_SUFFIXES,
        ("definenuxtconfig", "usenuxtapp", "<nuxtpage", "<nuxtlayout"),
    ):
        return "nuxt"

    if any(path.suffix.lower() == ".vue" for path in _iter_files(repo, {".vue"})) or _has_content(
        repo,
        JS_SUFFIXES,
        ("from 'vue'", 'from "vue"', "createapp("),
    ):
        return "vue"

    if _has_content(
        repo,
        JS_SUFFIXES,
        ("from 'react'", 'from "react"', "reactdom", "createroot("),
    ):
        return "react"

    if _has_content(
        repo,
        JS_SUFFIXES,
        ("require('express')", 'require("express")', "from 'express'", 'from "express"', ".listen("),
    ):
        return "express"

    if _has_content(
        repo,
        {".py", ".txt", ".toml", ".ini", ".cfg"},
        ("from fastapi import", "fastapi(", "import fastapi"),
    ):
        return "fastapi"

    if _has_content(
        repo,
        {".py", ".txt", ".toml", ".ini", ".cfg"},
        ("from flask import", "flask(", "import flask"),
    ):
        return "flask"

    if any(path.name == "index.html" for path in repo.rglob("index.html") if path.is_file() and not SKIP_PARTS.intersection(path.parts)):
        return "static"

    raise ValueError("Framework not supported")


def _scan_port(repo: Path, framework: str) -> int:
    suffixes = JS_SUFFIXES | PY_SUFFIXES
    for path in _iter_files(repo, suffixes):
        text = _read_text(path)
        if text is None:
            continue

        for pattern in (EXPRESS_PORT_RE, RUNSERVER_PORT_RE, PORT_RE):
            match = pattern.search(text)
            if match:
                return int(match.group(1))

    return DEFAULT_PORTS[framework]


def _find_python_app_module(repo: Path, framework: str, default_module: str) -> str:
    for py_file in _iter_files(repo, {".py"}):
        text = _read_text(py_file)
        if text is None:
            continue
        lowered = text.lower()
        if framework == "fastapi":
            if "from fastapi import" in lowered or "fastapi(" in lowered:
                return ".".join(py_file.relative_to(repo).with_suffix("").parts)
        elif framework == "flask":
            if "from flask import" in lowered or "flask(" in lowered:
                return ".".join(py_file.relative_to(repo).with_suffix("").parts)
    return default_module


def _find_express_entry(repo: Path) -> str | None:
    for js_file in _iter_files(repo, JS_SUFFIXES):
        text = _read_text(js_file)
        if text is None:
            continue
        if ".listen(" in text:
            return js_file.relative_to(repo).as_posix()
    return None


def _js_build_command(scripts: dict, deps: set) -> str:
    """Pick the right build command for any JS project without downloading tools."""
    if "build" in scripts:
        return "npm run build"
    for tool, cmd in [
        ("vite", "./node_modules/.bin/vite build"),
        ("react-scripts", "./node_modules/.bin/react-scripts build"),
        ("webpack", "./node_modules/.bin/webpack"),
        ("parcel", "./node_modules/.bin/parcel build"),
        ("rollup", "./node_modules/.bin/rollup -c"),
    ]:
        if tool in deps:
            return cmd
    return "npm run build"


def _detect_commands(repo: Path, framework: str, port: int) -> dict[str, str | None]:
    defaults = DEFAULT_COMMANDS[framework]

    if framework == "static":
        return defaults.copy()

    if framework == "django":
        return {"build": None, "start": f"python manage.py runserver 0.0.0.0:{port}"}

    if framework == "fastapi":
        module = _find_python_app_module(repo, framework, "main")
        return {"build": None, "start": f"uvicorn {module}:app --host 0.0.0.0 --port {port}"}

    if framework == "flask":
        module = _find_python_app_module(repo, framework, "app")
        return {"build": None, "start": f"flask --app {module} run --host 0.0.0.0 --port {port}"}

    pkg = _package_json(repo)
    scripts = _dict_section(pkg, "scripts") if pkg is not None else {}

    if framework == "react":
        deps = _dependency_names(pkg) if pkg else set()
        build = _js_build_command(scripts, deps)
        start = "npm run preview" if "preview" in scripts else ("npm run start" if "start" in scripts else defaults["start"])
        return {"build": build, "start": start}

    if framework == "vue":
        deps = _dependency_names(pkg) if pkg else set()
        build = _js_build_command(scripts, deps)
        if "preview" in scripts:
            start = "npm run preview"
        elif "start" in scripts:
            start = "npm run start"
        else:
            start = f"serve -s dist -l {port}"
        return {"build": build, "start": start}

    if framework == "next":
        build = "npm run build" if "build" in scripts else "./node_modules/.bin/next build"
        start = "npm run start" if "start" in scripts else f"./node_modules/.bin/next start -p {port} -H 0.0.0.0"
        return {"build": build, "start": start}

    if framework == "nuxt":
        build = "npm run build" if "build" in scripts else "./node_modules/.bin/nuxi build"
        start = "npm run start" if "start" in scripts else f"./node_modules/.bin/nuxi preview --host 0.0.0.0 --port {port}"
        return {"build": build, "start": start}

    if framework == "express":
        if "start" in scripts:
            start = "npm run start"
        else:
            main = pkg.get("main") if pkg is not None and isinstance(pkg.get("main"), str) else None
            start = f"node {main}" if main else _find_express_entry(repo) or defaults["start"]
        build = "npm run build" if "build" in scripts else None
        return {"build": build, "start": start}

    raise ValueError(f"Unsupported framework: {framework}")


def detect(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()

    if not repo.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo}")
    if not repo.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo}")

    framework = _detect_framework(repo)
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"Unsupported framework: {framework}")

    port = _scan_port(repo, framework)
    commands = _detect_commands(repo, framework, port)

    return {
        "framework": framework,
        "port": port,
        "start_command": commands["start"],
        "build_command": commands["build"],
    }