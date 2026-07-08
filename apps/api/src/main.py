from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.src.db.database import init_db
from apps.api.src.lib.auth import router as auth_router
from apps.api.src.routes.projects import router as projects_router
from apps.api.src.routes.builds import router as builds_router
from apps.api.src.routes.deployments import router as deployments_router
from apps.api.src.routes.logs import router as logs_router
from apps.api.src.routes.webhook import router as webhook_router
from apps.api.src.services.webhook_adapter import DBWebhookAdapter

def _cleanup_stuck_builds():
    db = SessionLocal()
    try:
        stuck_builds = db.query(Build).filter(Build.status.in_(["building", "queued"])).all()
        for build in stuck_builds:
            build.status = "failed"
            build.finished_at = datetime.utcnow()
        stuck_projects = db.query(Project).filter(Project.status == "building").all()
        for project in stuck_projects:
            project.status = "failed"
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_loop()
    init_db()
    _cleanup_stuck_builds()
    app.state.webhook_adapter = DBWebhookAdapter()
    yield


app = FastAPI(
    title="Parsley",
    lifespan=lifespan,
    redirect_slashes=False
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://app.parsley.website"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(builds_router)
app.include_router(deployments_router)
app.include_router(logs_router)
app.include_router(webhook_router)

@app.get("/")
def health_check():
    return {"status": "ok"}