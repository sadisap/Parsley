from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.db.database import get_db  # noqa: E402
from src.db.models import Base, User  # noqa: E402
from src.lib.auth import get_current_user  # noqa: E402
from src.routes.projects import router as projects_router  # noqa: E402
from tests._helpers import create_user  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path: Path):
    db_path = tmp_path / 'parsley_test.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session(db_session_factory) -> Generator[Session, None, None]:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def current_user(db_session) -> User:
    return create_user(db_session)


@pytest.fixture()
def app(db_session_factory, current_user) -> FastAPI:
    app = FastAPI()
    app.include_router(projects_router)

    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)
