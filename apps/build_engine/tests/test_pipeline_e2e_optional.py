from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import index


def _enabled() -> bool:
    return os.getenv('RUN_PARSLEY_E2E', '').strip().lower() in {'1', 'true', 'yes'}


pytestmark = pytest.mark.e2e


@pytest.mark.skipif(not _enabled(), reason='Set RUN_PARSLEY_E2E=1 to run the real GitHub/DockerHub smoke test')
def test_real_public_repo_can_be_built_and_pushed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if shutil.which('docker') is None:
        pytest.skip('docker CLI is not installed')

    docker_username = os.getenv('DOCKERHUB_USERNAME', '').strip()
    if not docker_username:
        pytest.skip('DOCKERHUB_USERNAME is required')

    repo_url = os.getenv('PARSLEY_E2E_REPO_URL', 'https://github.com/BStok/deployment-test-repo').strip()
    if not repo_url:
        pytest.skip('PARSLEY_E2E_REPO_URL is empty')

    project_id = os.getenv('PARSLEY_E2E_PROJECT_ID', 'parsley-e2e-smoke')

    # Build engine writes temporary clones under its own build directory. We keep the repo URL
    # configurable so you can point this at a small public repo that matches one of Parsley's
    # supported stacks.
    result = index.run_pipeline(project_id=project_id, repo_url=repo_url, docker_username=docker_username)

    assert result['image_tag'] == f'{docker_username}/{project_id}:latest'
    assert result['image'] == result['image_tag']
    assert result['framework'] in {
        'react', 'vue', 'next', 'nuxt', 'express', 'fastapi', 'flask', 'django', 'static'
    }

    inspect = subprocess.run(
        ['docker', 'manifest', 'inspect', result['image_tag']],
        check=True,
        capture_output=True,
        text=True,
    )
    assert inspect.returncode == 0
