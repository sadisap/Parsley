from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from detect import detect


def write_file(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    return repo


def test_detect_missing_repo_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect(tmp_path / "missing-repo")


def test_detect_rejects_file_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo.txt"
    repo.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_rejects_invalid_package_json(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "package.json", "{")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_rejects_unsupported_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "README.md", "# hello")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_ignores_signals_inside_skipped_dirs(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, ".venv/app.py", "from fastapi import FastAPI\napp = FastAPI()")
    write_file(repo, "node_modules/package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    write_file(repo, "README.md", "nothing useful here")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_react_with_preview_script(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18.0.0"},
                "scripts": {
                    "build": "vite build",
                    "preview": "vite preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run preview"


def test_detect_react_falls_back_to_start_script_when_preview_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18.0.0"},
                "scripts": {
                    "build": "vite build",
                    "start": "vite preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_express_with_scripts_and_listen_port(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"express": "^4.0.0"},
                "scripts": {
                    "build": "echo build",
                    "start": "node index.js",
                },
            }
        ),
    )
    write_file(repo, "server.js", "const app = require('express')();\napp.listen(4000);")

    result = detect(repo)

    assert result["framework"] == "express"
    assert result["port"] == 4000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_express_uses_main_field_when_no_start_script(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"express": "^4.0.0"},
                "main": "src/server.js",
            }
        ),
    )
    write_file(repo, "src/server.js", "const app = require('express')();\napp.listen(3333);")

    result = detect(repo)

    assert result["framework"] == "express"
    assert result["port"] == 3333
    assert result["build_command"] is None
    assert result["start_command"] == "node src/server.js"


def test_detect_fastapi_from_requirements_and_source_port(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "requirements.txt", "fastapi\nuvicorn\n")
    write_file(
        repo,
        "main.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "# uvicorn main:app --host 0.0.0.0 --port 9000\n",
    )

    result = detect(repo)

    assert result["framework"] == "fastapi"
    assert result["port"] == 9000
    assert result["build_command"] is None
    assert result["start_command"] == "uvicorn main:app --host 0.0.0.0 --port 9000"


def test_detect_flask_nested_module_and_port(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "requirements.txt", "flask\n")
    write_file(
        repo,
        "src/api/app.py",
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "# flask run --host 0.0.0.0 --port 5050\n",
    )

    result = detect(repo)

    assert result["framework"] == "flask"
    assert result["port"] == 5050
    assert result["build_command"] is None
    assert result["start_command"] == "flask --app src.api.app run --host 0.0.0.0 --port 5050"


def test_detect_static_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "index.html", "<!doctype html><html><body>Hello</body></html>")
    write_file(repo, "styles.css", "body { margin: 0; }")

    result = detect(repo)

    assert result["framework"] == "static"
    assert result["port"] == 80
    assert result["build_command"] is None
    assert result["start_command"] is None