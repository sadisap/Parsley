from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from builder import BuildError, build


def write_file(repo: Path, relative_path: str, content: str = "") -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo-app"
    repo.mkdir()
    return repo


def detection(framework: str = "react") -> dict:
    return {
        "framework": framework,
        "port": 5173,
        "start_command": "npm run preview",
        "build_command": "npm run build",
    }


def test_missing_repo_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build(tmp_path / "missing", detection())


def test_repo_path_must_be_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")

    with pytest.raises(ValueError):
        build(file_path, detection())


def test_detection_must_be_mapping(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(TypeError):
        build(repo, "not-a-dict")  # type: ignore


def test_invalid_framework(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        build(repo, {"framework": "django"})


def test_invalid_tag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        build(repo, detection(), image_repository="demo/image", tag="bad tag")


def test_missing_template(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with patch("builder._template_path") as mock_template:
        mock_template.side_effect = FileNotFoundError("template missing")

        with pytest.raises(FileNotFoundError):
            build(repo, detection(), image_repository="demo/image")


def test_requires_image_repository_or_env(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)

    monkeypatch.delenv("DOCKERHUB_USERNAME", raising=False)

    with pytest.raises(ValueError):
        build(repo, detection())


def test_image_name_from_env(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)

    monkeypatch.setenv("DOCKERHUB_USERNAME", "sadie")

    with patch("builder._run"):
        with patch("builder._template_path") as template:
            dockerfile = tmp_path / "react-vite.dockerfile"
            dockerfile.write_text("{{PORT}} {{START_COMMAND}} {{BUILD_COMMAND}}")

            template.return_value = dockerfile

            result = build(repo, detection())

    assert result["image"] == "sadie/demo-app:latest"


def test_react_always_uses_serve_command(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    dockerfile = tmp_path / "react-vite.dockerfile"
    dockerfile.write_text("{{START_COMMAND}}")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": "react",
                    "port": 5173,
                    "start_command": "npm run preview",
                    "build_command": "npm run build",
                },
                image_repository="demo/react",
            )

    assert result["start_command"] == "serve -s dist -l 5173"


def test_docker_build_and_push_are_called(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    dockerfile = tmp_path / "react-vite.dockerfile"
    dockerfile.write_text("{{PORT}} {{START_COMMAND}} {{BUILD_COMMAND}}")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run") as mock_run:
            build(
                repo,
                detection(),
                image_repository="demo/image",
            )

    assert mock_run.call_count == 2

    first_call = mock_run.call_args_list[0][0][0]
    second_call = mock_run.call_args_list[1][0][0]

    assert first_call[:2] == ["docker", "build"]
    assert second_call[:2] == ["docker", "push"]


def test_docker_failure_bubbles_up(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    dockerfile = tmp_path / "react-vite.dockerfile"
    dockerfile.write_text("{{PORT}} {{START_COMMAND}} {{BUILD_COMMAND}}")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run", side_effect=BuildError("docker failed")):
            with pytest.raises(BuildError):
                build(
                    repo,
                    detection(),
                    image_repository="demo/image",
                )


def test_successful_build_returns_metadata(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    write_file(repo, "package.json", "{}")

    dockerfile = tmp_path / "react-vite.dockerfile"
    dockerfile.write_text("{{PORT}} {{START_COMMAND}} {{BUILD_COMMAND}}")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                detection(),
                image_repository="demo/image",
                tag="v1",
            )

    assert result["image"] == "demo/image:v1"
    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "serve -s dist -l 5173"


def test_excluded_directories_do_not_break_build(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    write_file(repo, "node_modules/big.js", "ignore")
    write_file(repo, ".git/config", "ignore")
    write_file(repo, "__pycache__/a.pyc", "ignore")
    write_file(repo, "app.py", "print('hello')")

    dockerfile = tmp_path / "flask.dockerfile"
    dockerfile.write_text("{{PORT}} {{START_COMMAND}} {{BUILD_COMMAND}}")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": "flask",
                    "port": 5000,
                    "start_command": "flask run",
                    "build_command": None,
                },
                image_repository="demo/flask",
            )

    assert result["framework"] == "flask"