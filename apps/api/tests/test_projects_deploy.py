from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from apps.api.src.db.models import Project
from apps.api.src.routes import projects as projects_route
from apps.api.tests._helpers import create_project_record


def test_create_project_returns_pending_and_persists(client, db_session: Session, current_user) -> None:
    response = client.post(
        '/projects/',
        json={
            'name': 'My Demo App',
            'repo_url': 'https://github.com/example/demo-app.git',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'My Demo App'
    assert body['repo_url'] == 'https://github.com/example/demo-app.git'
    assert body['subdomain'] == 'my-demo-app'
    assert body['status'] == 'pending'

    stored = db_session.get(Project, body['project_id'])
    assert stored is not None
    assert stored.user_id == current_user.user_id
    assert stored.name == 'My Demo App'
    assert stored.status == 'pending'


def test_create_project_rejects_duplicate_subdomain(client) -> None:
    first = client.post(
        '/projects/',
        json={
            'name': 'Same Name',
            'repo_url': 'https://github.com/example/one.git',
        },
    )
    assert first.status_code == 200

    second = client.post(
        '/projects/',
        json={
            'name': 'Same Name',
            'repo_url': 'https://github.com/example/two.git',
        },
    )

    assert second.status_code == 400
    assert second.json()['detail'] == 'Project name already taken'


def test_deploy_project_happy_path_updates_status_and_returns_result(
    client,
    db_session_factory,
    current_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session = db_session_factory()
    try:
        project = create_project_record(
            db_session,
            current_user.user_id,
            name='Deploy Me',
            repo_url='https://github.com/example/deploy-me.git',
        )
    finally:
        db_session.close()

    captured = {}

    def fake_trigger_build(project: Project):
        captured['project_id'] = project.project_id
        captured['status_inside_build'] = project.status
        return {
            'image_tag': 'demo/deploy-me:latest',
            'image': 'demo/deploy-me:latest',
            'framework': 'react',
            'port': 5173,
        }

    monkeypatch.setattr(projects_route, 'trigger_build', fake_trigger_build)

    response = client.post(f'/projects/{project.project_id}/deploy')

    assert response.status_code == 200
    body = response.json()
    assert body['project_id'] == project.project_id
    assert body['status'] == 'deployed'
    assert body['result']['image_tag'] == 'demo/deploy-me:latest'
    assert captured['project_id'] == project.project_id
    assert captured['status_inside_build'] == 'building'

    fresh = db_session_factory().get(Project, project.project_id)
    assert fresh is not None
    assert fresh.status == 'deployed'


def test_deploy_project_sets_failed_when_build_raises(
    client,
    db_session_factory,
    current_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session = db_session_factory()
    try:
        project = create_project_record(
            db_session,
            current_user.user_id,
            name='Broken Deploy',
            repo_url='https://github.com/example/broken-deploy.git',
        )
    finally:
        db_session.close()

    def fake_trigger_build(project: Project):
        assert project.status == 'building'
        raise RuntimeError('docker failed')

    monkeypatch.setattr(projects_route, 'trigger_build', fake_trigger_build)

    response = client.post(f'/projects/{project.project_id}/deploy')

    assert response.status_code == 500
    assert response.json()['detail'] == 'Build failed: docker failed'

    fresh = db_session_factory().get(Project, project.project_id)
    assert fresh is not None
    assert fresh.status == 'failed'


def test_deploy_project_rejects_projects_owned_by_other_user(client, db_session_factory) -> None:
    other_session = db_session_factory()
    try:
        other_project = create_project_record(
            other_session,
            user_id=str(uuid4()),
            name='Someone Else',
            repo_url='https://github.com/example/else.git',
        )
    finally:
        other_session.close()

    response = client.post(f'/projects/{other_project.project_id}/deploy')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Project not found'


def test_deploy_project_rejects_unknown_project(client) -> None:
    response = client.post(f'/projects/{uuid4()}/deploy')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Project not found'
