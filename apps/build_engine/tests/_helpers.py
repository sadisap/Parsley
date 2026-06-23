from __future__ import annotations

from pathlib import Path


def write_file(repo: Path, relative_path: str, content: str = '') -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def make_repo(tmp_path: Path, name: str = 'demo-app') -> Path:
    repo = tmp_path / name
    repo.mkdir()
    return repo
