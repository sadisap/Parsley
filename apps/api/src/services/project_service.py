import os
import threading
import uuid
from datetime import datetime

from apps.api.src.db.database import SessionLocal
from apps.api.src.db.models import Build, Deployment, Project
from apps.api.src.lib.log_store import append_log
from apps.api.src.services.deploy_service import deploy_to_vps
from apps.build_engine.src.index import run_pipeline


def start_build_and_deploy(project_id: str) -> str:
    """
    Creates a Build record, marks the project as building, and starts the
    build+deploy thread. Returns the build_id so callers can stream logs.
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        if project.status == "building":
            raise ValueError("Build already in progress")

        build = Build(
            build_id=str(uuid.uuid4()),
            project_id=project_id,
            status="queued",
            created_at=datetime.utcnow(),
        )
        db.add(build)
        project.status = "building"
        db.commit()
        build_id = build.build_id
    finally:
        db.close()

    def run_build():
        db2 = SessionLocal()
        try:
            build_record = db2.query(Build).filter(Build.build_id == build_id).first()
            project_record = db2.query(Project).filter(Project.project_id == project_id).first()

            build_record.status = "building"
            build_record.started_at = datetime.utcnow()
            db2.commit()

            result = run_pipeline(
                project_id=project_id,
                repo_url=project_record.repo_url,
                docker_username=os.getenv("DOCKERHUB_USERNAME"),
                log_callback=lambda line: append_log(build_id, line),
            )

            container_name = deploy_to_vps(
                project_id=project_id,
                subdomain=project_record.subdomain,
                image_tag=result["image_tag"],
                port=result["port"],
            )

            deployment = Deployment(
                deployment_id=str(uuid.uuid4()),
                project_id=project_id,
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
            try:
                if build_record:
                    build_record.status = "failed"
                    build_record.finished_at = datetime.utcnow()
                if project_record:
                    project_record.status = "failed"
                db2.commit()
            except Exception as inner:
                print(f"BUILD THREAD CLEANUP ERROR: {inner}")
                db2.rollback()
            append_log(build_id, f"ERROR: {e}")

        finally:
            append_log(build_id, "__done__")
            db2.close()

    threading.Thread(target=run_build).start()
    return build_id
