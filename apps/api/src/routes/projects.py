from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import threading
import os
from datetime import datetime

from apps.api.src.db.database import get_db, SessionLocal
from apps.api.src.db.models import Project, Build, User
from apps.api.src.lib.auth import get_current_user
from apps.api.src.lib.log_store import append_log
from apps.build_engine.src.index import run_pipeline
from apps.api.src.services.deploy_service import deploy_to_vps
from apps.api.src.db.models import Deployment

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectBody(BaseModel):
    name: str
    repo_url: str


class EnvVarsBody(BaseModel):
    env_vars: dict


@router.get("/")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = db.query(Project).filter(Project.user_id == current_user.user_id).all()
    return [
        {
            "project_id": p.project_id,
            "name": p.name,
            "repo_url": p.repo_url,
            "subdomain": p.subdomain,
            "status": p.status,
            "framework": p.framework,
        }
        for p in projects
    ]


@router.get("/{project_id}/env")
def get_env(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.user_id == current_user.user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.env_vars or {}


@router.put("/{project_id}/env")
def set_env(
    project_id: str,
    body: EnvVarsBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.user_id == current_user.user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.env_vars = body.env_vars
    db.commit()
    return project.env_vars


@router.post("/")
def create_project(
    body: CreateProjectBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subdomain = body.name.lower().replace(" ", "-")

    existing = db.query(Project).filter(Project.subdomain == subdomain).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project name already taken")

    project = Project(
        project_id=str(uuid.uuid4()),
        user_id=current_user.user_id,
        name=body.name,
        repo_url=body.repo_url,
        subdomain=subdomain,
        status="pending",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return {
        "project_id": project.project_id,
        "name": project.name,
        "repo_url": project.repo_url,
        "subdomain": project.subdomain,
        "status": project.status,
    }


@router.post("/{project_id}/deploy")
def deploy_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.user_id == current_user.user_id,
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == "building":
        raise HTTPException(status_code=409, detail="Build already in progress")

    # create build record
    build = Build(
        build_id=str(uuid.uuid4()),
        project_id=project.project_id,
        status="queued",
        created_at=datetime.utcnow(),
    )
    db.add(build)
    project.status = "building"
    db.commit()

    build_id = build.build_id
    repo_url = project.repo_url
    p_id = project.project_id

    def run_build():
        # use a new DB session — the request session closes after response
        db2 = SessionLocal()
        try:
            build_record = db2.query(Build).filter(Build.build_id == build_id).first()
            project_record = db2.query(Project).filter(Project.project_id == p_id).first()

            build_record.status = "building"
            build_record.started_at = datetime.utcnow()
            db2.commit()

            result = run_pipeline(
                project_id=p_id,
                repo_url=repo_url,
                docker_username=os.getenv("DOCKERHUB_USERNAME"),
                log_callback=lambda line: append_log(build_id, line),  # ← here
            )

            container_name = deploy_to_vps(
                project_id=p_id,
                subdomain=project_record.subdomain,
                image_tag=result["image_tag"],
                port=result["port"],
                env_vars=project_record.env_vars or {},
            )

            deployment = Deployment(
                deployment_id=str(uuid.uuid4()),
                project_id=p_id,
                build_id=build_id,
                container_id=container_name,
                status="running",
                deployed_at=datetime.utcnow(),
            )
            db2.add(deployment)
            db2.commit()

            build_record.status = "success"
            build_record.image_tag = result["image_tag"]
            build_record.finished_at = datetime.utcnow()
            project_record.status = "running"
            project_record.framework = result["framework"]
            project_record.port = result["port"]
            project_record.start_command = result["start_command"]
            db2.commit()

        except Exception as e:
            print(f"BUILD THREAD ERROR: {e}")
            build_record.status = "failed"
            build_record.finished_at = datetime.utcnow()
            project_record.status = "failed"
            db2.commit()
            append_log(build_id, f"ERROR: {e}")

        finally:
            append_log(build_id, "__done__")  # ← signals WebSocket to close
            db2.close()

    thread = threading.Thread(target=run_build)
    thread.start()

    return {
        "build_id": build_id,
        "status": "queued",
        "message": "Build started"
    }