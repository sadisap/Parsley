# what framework it is (React, Express, FastAPI, Flask, static)
# what port it runs on
# what the start command is

import json
import re
from pathlib import Path

SUPPORTED_FRAMEWORKS = {"react", "express", "fastapi", "flask", "static"}

STATIC_EXTENSIONS = {
    ".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".woff", ".woff2", ".ttf"
}

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
    "flask": {"build": None, "start": "flask run --host 0.0.0.0 --port 5000"},
    "static": {"build": None, "start": None},
}


# 1: detect framework

def _detect_framework(repo: Path) -> str:
    pkg = repo / "package.json"
    req = repo / "requirements.txt"

    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Could not parse package.json: {e}")

        deps = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
        }

        if "react" in deps:
            return "react"
        if "express" in deps:
            return "express"

    if req.exists():
        try:
            contents = req.read_text(encoding="utf-8").lower()
        except OSError as e:
            raise ValueError(f"Could not read requirements.txt: {e}")

        # matches "fastapi" or "fastapi==..." as a line start to avoid false positives
        if re.search(r"^fastapi([=<>!;\s]|$)", contents, re.MULTILINE):
            return "fastapi"
        if re.search(r"^flask([=<>!;\s]|$)", contents, re.MULTILINE):
            return "flask"

    # fallback: inspect Python source files directly
    for py_file in repo.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue

        if "from flask import" in text or "flask(__name__)" in text:
            return "flask"

        if "from fastapi import" in text or "fastapi()" in text:
            return "fastapi"

    # fallback: all root-level files are static assets
    root_files = [f for f in repo.iterdir() if f.is_file()]
    if root_files and all(f.suffix.lower() in STATIC_EXTENSIONS for f in root_files):
        return "static"

    raise ValueError("Framework not supported")


# 2: detect port

def _detect_port(repo: Path, framework: str) -> int:
    if framework == "express":
        return _scan_express_port(repo)
    if framework in ("fastapi", "flask"):
        return _scan_python_port(repo, framework)
    return DEFAULT_PORTS[framework]


def _scan_express_port(repo: Path) -> int:
    for filename in ("index.js", "server.js"):
        candidate = repo / filename
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        # matches: app.listen(3000)  app.listen(PORT, ...)  app.listen(process.env.PORT || 3000)
        match = re.search(r"\.listen\(\s*(?:[A-Za-z_][A-Za-z0-9_.]*\s*\|\|\s*)?(\d{2,5})", text)
        if match:
            return int(match.group(1))
    return DEFAULT_PORTS["express"]


def _scan_python_port(repo: Path, framework: str) -> int:
    for filename in ("main.py", "app.py"):
        candidate = repo / filename
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        # matches: port=8000  --port 8000  --port=8000
        match = re.search(r"(?:port\s*=\s*|--port[=\s]+)(\d{2,5})", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return DEFAULT_PORTS[framework]


# 3: detect start and build commands

def _detect_commands(repo: Path, framework: str) -> dict[str, str | None]:
    defaults = DEFAULT_COMMANDS[framework]

    if framework not in ("react", "express"):
        # Python frameworks and static don't use package.json scripts
        return {"build": defaults["build"], "start": defaults["start"]}

    pkg = repo / "package.json"
    if not pkg.exists():
        return {"build": defaults["build"], "start": defaults["start"]}

    try:
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return {"build": defaults["build"], "start": defaults["start"]}

    build_cmd = "npm run build" if "build" in scripts else defaults["build"]
    start_cmd = "npm run start" if "start" in scripts else defaults["start"]

    return {"build": build_cmd, "start": start_cmd}


# Public API

def detect(repo_path: str | Path) -> dict:
    """
    Analyse a cloned repo and return framework metadata.

    Returns:
        {
            "framework":     str,
            "port":          int,
            "start_command": str | None,
            "build_command": str | None,
        }

    Raises:
        ValueError: if the framework is not supported or a config file is malformed.
        FileNotFoundError: if repo_path does not exist.
    """
    repo = Path(repo_path)

    if not repo.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo}")
    if not repo.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo}")

    framework = _detect_framework(repo)
    port = _detect_port(repo, framework)
    commands = _detect_commands(repo, framework)

    return {
        "framework": framework,
        "port": port,
        "start_command": commands["start"],
        "build_command": commands["build"],
    }