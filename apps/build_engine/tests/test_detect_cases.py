from __future__ import annotations

from pathlib import Path

import pytest

from _helpers import make_repo, write_file

import detect


def test_detect_prefers_next_over_react_when_both_signals_exist(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, 'next-react')
    write_file(
        repo,
        'package.json',
        '{"dependencies": {"next": "14.0.0", "react": "18.0.0"}, "scripts": {"build": "next build", "start": "next start"}}',
    )
    write_file(repo, 'pages/index.tsx', 'import React from "react"; import Link from "next/link";')

    result = detect.detect(repo)

    assert result['framework'] == 'next'
    assert result['port'] == 3000
    assert result['start_command'] == 'npm run start'
    assert result['build_command'] == 'npm run build'


def test_detect_prefers_nuxt_over_vue_when_both_signals_exist(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, 'nuxt-vue')
    write_file(
        repo,
        'package.json',
        '{"dependencies": {"nuxt": "3.0.0", "vue": "3.0.0"}, "scripts": {"build": "nuxt build", "start": "nuxt start"}}',
    )
    write_file(repo, 'app.vue', '<template><NuxtPage /></template>')

    result = detect.detect(repo)

    assert result['framework'] == 'nuxt'
    assert result['port'] == 3000
    assert result['start_command'] == 'npm run start'
    assert result['build_command'] == 'npm run build'


@pytest.mark.parametrize(
    'files,expected_framework,expected_port,expected_start',
    [
        (
            {'requirements.txt': 'Django==5.0.1\n'},
            'django',
            8000,
            'python manage.py runserver 0.0.0.0:8000',
        ),
        (
            {'manage.py': 'import django\n', 'requirements.txt': 'asgiref\n'},
            'django',
            8000,
            'python manage.py runserver 0.0.0.0:8000',
        ),
        (
            {'requirements.txt': 'fastapi\nuvicorn\n', 'main.py': 'from fastapi import FastAPI\napp = FastAPI()\n'},
            'fastapi',
            8000,
            'uvicorn main:app --host 0.0.0.0 --port 8000',
        ),
        (
            {'requirements.txt': 'Flask\n', 'app.py': 'from flask import Flask\napp = Flask(__name__)\n'},
            'flask',
            5000,
            'flask --app app run --host 0.0.0.0 --port 5000',
        ),
        (
            {'index.html': '<html><body>Hello</body></html>'},
            'static',
            80,
            None,
        ),
    ],
)
def test_detect_python_and_static_variants(
    tmp_path: Path,
    files: dict[str, str],
    expected_framework: str,
    expected_port: int,
    expected_start: str | None,
) -> None:
    repo = make_repo(tmp_path, expected_framework)
    for relative_path, content in files.items():
        write_file(repo, relative_path, content)

    result = detect.detect(repo)

    assert result['framework'] == expected_framework
    assert result['port'] == expected_port
    assert result['start_command'] == expected_start
    if expected_framework == 'static':
        assert result['build_command'] is None


def test_detect_reads_explicit_port_from_source_file(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, 'express-port')
    write_file(
        repo,
        'package.json',
        '{"dependencies": {"express": "4.18.0"}, "scripts": {"start": "node server.js"}}',
    )
    write_file(repo, 'server.js', 'const app = require("express")();\napp.listen(4555);\n')

    result = detect.detect(repo)

    assert result['framework'] == 'express'
    assert result['port'] == 4555
    assert result['start_command'] == 'npm run start'


def test_detect_raises_for_unsupported_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, 'unknown')
    write_file(repo, 'README.md', '# just docs')

    with pytest.raises(ValueError, match='Framework not supported'):
        detect.detect(repo)
