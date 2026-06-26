from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.src.db.database import get_db
from apps.api.src.db.models import Build, Project, User
from apps.api.src.lib.auth import get_current_user

router = APIRouter(tags=["builds"])


@router.get("/projects/{project_id}/builds")
def list_builds(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    builds = (
        db.query(Build)
        .filter(Build.project_id == project_id)
        .order_by(Build.created_at.desc())
        .all()
    )

    return [
        {
            "build_id": b.build_id,
            "status": b.status,
            "image_tag": b.image_tag,
            "started_at": b.started_at,
            "finished_at": b.finished_at,
            "created_at": b.created_at,
        }
        for b in builds
    ]


@router.get("/builds/{build_id}")
def get_build(
    build_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    build = db.query(Build).filter(Build.build_id == build_id).first()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    project = db.query(Project).filter(Project.project_id == build.project_id).first()
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "build_id": build.build_id,
        "project_id": build.project_id,
        "status": build.status,
        "image_tag": build.image_tag,
        "log_output": build.log_output,
        "log_expires_at": build.log_expires_at,
        "started_at": build.started_at,
        "finished_at": build.finished_at,
        "created_at": build.created_at,
    }
