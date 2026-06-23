from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services import build_service


class DummyProject(SimpleNamespace):
    pass


def test_trigger_build_requires_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOCKERHUB_USERNAME', 'demo')

    with pytest.raises(ValueError, match='Project is missing project_id'):
        build_service.trigger_build(DummyProject(repo_url='https://github.com/example/repo.git'))


def test_trigger_build_requires_repo_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOCKERHUB_USERNAME', 'demo')

    with pytest.raises(ValueError, match='Project is missing repo_url'):
        build_service.trigger_build(DummyProject(project_id='project-1'))


def test_trigger_build_requires_dockerhub_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DOCKERHUB_USERNAME', raising=False)

    with pytest.raises(ValueError, match='DOCKERHUB_USERNAME is not set'):
        build_service.trigger_build(
            DummyProject(project_id='project-1', repo_url='https://github.com/example/repo.git')
        )


def test_trigger_build_strips_username_and_calls_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOCKERHUB_USERNAME', '  parsley-user  ')

    captured = {}

    def fake_run_pipeline(*, project_id: str, repo_url: str, docker_username: str):
        captured['project_id'] = project_id
        captured['repo_url'] = repo_url
        captured['docker_username'] = docker_username
        return {'image_tag': f'{docker_username}/{project_id}:latest'}

    monkeypatch.setattr(build_service, 'run_pipeline', fake_run_pipeline)

    result = build_service.trigger_build(
        DummyProject(project_id=123, repo_url='https://github.com/example/repo.git')
    )

    assert result['image_tag'] == 'parsley-user/123:latest'
    assert captured == {
        'project_id': '123',
        'repo_url': 'https://github.com/example/repo.git',
        'docker_username': 'parsley-user',
    }


def test_trigger_build_propagates_pipeline_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('DOCKERHUB_USERNAME', 'demo')

    def fake_run_pipeline(*args, **kwargs):
        raise RuntimeError('build failed')

    monkeypatch.setattr(build_service, 'run_pipeline', fake_run_pipeline)

    with pytest.raises(RuntimeError, match='build failed'):
        build_service.trigger_build(
            DummyProject(project_id='project-1', repo_url='https://github.com/example/repo.git')
        )
