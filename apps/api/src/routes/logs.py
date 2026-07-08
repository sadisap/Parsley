# apps/api/src/routes/logs.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from apps.api.src.lib.log_store import get_logs
from apps.api.src.db.database import SessionLocal
from apps.api.src.db.models import Build
import asyncio

router = APIRouter(tags=["logs"])


@router.websocket("/ws/builds/{build_id}/logs")
async def stream_build_logs(websocket: WebSocket, build_id: str):
    await websocket.accept()

    db = SessionLocal()
    try:
        build = db.query(Build).filter(Build.build_id == build_id).first()
        if not build:
            await websocket.send_text("Build not found")
            await websocket.close()
            return

        sent = 0

        # send any lines already in the store
        existing = get_logs(build_id)
        for line in existing:
            await websocket.send_text(line)
        sent = len(existing)

        # if already finished, close immediately
        if build.status in ("success", "failed"):
            await websocket.send_text("__done__")
            return

        # poll every 0.5s for new lines and build completion
        while True:
            await asyncio.sleep(0.5)

            all_lines = get_logs(build_id)
            for line in all_lines[sent:]:
                await websocket.send_text(line)
            sent = len(all_lines)

            db.refresh(build)
            if build.status in ("success", "failed"):
                await websocket.send_text("__done__")
                break

    except WebSocketDisconnect:
        pass
    finally:
        db.close()


@router.websocket("/ws/containers/{container_name}/logs")
async def stream_container_logs(websocket: WebSocket, container_name: str):
    """Streams live runtime logs from a running container."""
    await websocket.accept()

    import subprocess
    import asyncio

    loop = asyncio.get_event_loop()

    try:
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                ["docker", "logs", "--follow", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        )

        async def read_lines():
            while True:
                line = await loop.run_in_executor(None, process.stdout.readline)
                if not line:
                    break
                await websocket.send_text(line.rstrip())

        await read_lines()

    except WebSocketDisconnect:
        process.terminate()
    except Exception as e:
        await websocket.send_text(f"Error: {e}")
        await websocket.close()
    finally:
        if process:
            process.terminate()