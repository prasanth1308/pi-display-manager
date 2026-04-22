import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import control, files, playlists, schedules
from scheduler_service import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield


app = FastAPI(
    title="Pi Display Manager",
    description="Manage and schedule media playback on Raspberry Pi",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["Playlists"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["Schedules"])
app.include_router(control.router, prefix="/api/control", tags=["Control"])


@app.get("/", include_in_schema=False)
async def serve_ui():
    return FileResponse("frontend/index.html")
