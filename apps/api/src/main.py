from contextlib import asynccontextmanager
from fastapi import FastAPI

from apps.api.src.db.database import init_db
from apps.api.src.lib.auth import router as auth_router
from apps.api.src.routes.projects import router as projects_router
from apps.api.src.routes.builds import router as builds_router
from apps.api.src.routes.deployments import router as deployments_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Parsley",
    lifespan=lifespan
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(builds_router)
app.include_router(deployments_router)

@app.get("/")
def health_check():
    return {"status": "ok"}