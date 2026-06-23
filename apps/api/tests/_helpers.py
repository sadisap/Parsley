from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from src.db.models import Project, User


def create_user(db_session: Session, *, username: str = 'alice') -> User:
    user = User(
        user_id=str(uuid4()),
        username=username,
        password='hashed-password',
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_project_record(
    db_session: Session,
    user_id: str,
    *,
    name: str,
    repo_url: str,
    status: str = 'pending',
) -> Project:
    project = Project(
        project_id=str(uuid4()),
        user_id=user_id,
        name=name,
        repo_url=repo_url,
        subdomain=name.lower().replace(' ', '-'),
        status=status,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
