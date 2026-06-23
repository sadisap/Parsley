from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import index


def test_run_pipeline_calls_clone_detect_build_and_returns_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()
    (repo_path / 'package.json').write_text('{"name":"demo"}', encoding='utf-8')

    calls = {}

    def fake_clone_repo(project_id: str, repo_url: str):
        calls['clone'] = (project_id, repo_url)
        return repo_path

    def fake_detect(cloned_path):
        calls['detect'] = Path(cloned_path)
        return {
            'framework': 'react',
            'port': 5173,
            'start_command': 'npm run preview',
            'build_command': 'npm run build',
        }

    def fake_build(*, repo_path, detection, image_repository, tag):
        calls['build'] = {
            'repo_path': Path(repo_path),
            'detection': dict(detection),
            'image_repository': image_repository,
            'tag': tag,
        }
        return {
            'image': f'{image_repository}:{tag}',
            'framework': detection['framework'],
            'template': '/tmp/template',
            'port': detection['port'],
            'build_command': detection['build_command'],
            'start_command': detection['start_command'],
        }

    monkeypatch.setattr(index, 'clone_repo', fake_clone_repo)
    monkeypatch.setattr(index, 'detect', fake_detect)
    monkeypatch.setattr(index, 'build', fake_build)

    result = index.run_pipeline('project-123', 'https://github.com/example/repo.git', 'docker-user')

    assert calls['clone'] == ('project-123', 'https://github.com/example/repo.git')
    assert calls['detect'] == repo_path
    assert calls['build']['image_repository'] == 'docker-user/project-123'
    assert calls['build']['tag'] == 'latest'
    assert result == {
        'image_tag': 'docker-user/project-123:latest',
        'image': 'docker-user/project-123:latest',
        'framework': 'react',
        'port': 5173,
        'start_command': 'npm run preview',
        'build_command': 'npm run build',
    }
    assert not repo_path.exists()


def test_run_pipeline_cleans_up_when_detection_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    monkeypatch.setattr(index, 'clone_repo', lambda *_: repo_path)

    def fake_detect(_):
        raise RuntimeError('detect failed')

    monkeypatch.setattr(index, 'detect', fake_detect)
    monkeypatch.setattr(index, 'build', lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match='detect failed'):
        index.run_pipeline('project-123', 'https://github.com/example/repo.git', 'docker-user')

    assert not repo_path.exists()


def test_run_pipeline_cleans_up_when_build_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    monkeypatch.setattr(index, 'clone_repo', lambda *_: repo_path)
    monkeypatch.setattr(
        index,
        'detect',
        lambda _: {
            'framework': 'react',
            'port': 5173,
            'start_command': 'npm run preview',
            'build_command': 'npm run build',
        },
    )

    def fake_build(*args, **kwargs):
        raise RuntimeError('build failed')

    monkeypatch.setattr(index, 'build', fake_build)

    with pytest.raises(RuntimeError, match='build failed'):
        index.run_pipeline('project-123', 'https://github.com/example/repo.git', 'docker-user')

    assert not repo_path.exists()
