from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.src.db.database import get_db
from apps.api.src.db.models import Deployment, Project, User
from apps.api.src.lib.auth import get_current_user

router = APIRouter(tags=["deployments"])


@router.get("/projects/{project_id}/deployments")
def list_deployments(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    deployments = (
        db.query(Deployment)
        .filter(Deployment.project_id == project_id)
        .order_by(Deployment.created_at.desc())
        .all()
    )

    return [
        {
            "deployment_id": d.deployment_id,
            "build_id": d.build_id,
            "container_id": d.container_id,
            "status": d.status,
            "deployed_at": d.deployed_at,
            "created_at": d.created_at,
        }
        for d in deployments
    ]


@router.get("/projects/{project_id}/deployments/{deployment_id}")
def get_deployment(
    project_id: str,
    deployment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.deployment_id == deployment_id,
        )
        .first()
    )
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return {
        "deployment_id": deployment.deployment_id,
        "build_id": deployment.build_id,
        "container_id": deployment.container_id,
        "status": deployment.status,
        "deployed_at": deployment.deployed_at,
        "created_at": deployment.created_at,
    }
