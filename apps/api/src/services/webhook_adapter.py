from apps.api.src.db.database import SessionLocal
from apps.api.src.db.models import Project
from apps.api.src.services.project_service import start_build_and_deploy


class DBWebhookAdapter:
    """
    Bridges the webhook route to the database and build pipeline.
    Attached to app.state.webhook_adapter at startup.
    """

    def find_project_by_repo(self, repo_full_name: str, repo_clone_url: str):
        """
        Look up a project by matching repo_url against the clone URL or
        the GitHub HTML URL (with and without .git suffix).
        """
        candidates = {
            repo_clone_url,
            f"https://github.com/{repo_full_name}",
            f"https://github.com/{repo_full_name}.git",
        }

        db = SessionLocal()
        try:
            return (
                db.query(Project)
                .filter(Project.repo_url.in_(candidates))
                .first()
            )
        finally:
            db.close()

    def trigger_redeploy(self, project, payload: dict, delivery_id: str) -> dict:
        build_id = start_build_and_deploy(project.project_id)
        return {"build_id": build_id}
