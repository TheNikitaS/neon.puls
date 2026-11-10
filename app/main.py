"""Точка входа FastAPI: API + статический интерфейс."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_TAGLINE, BASE_DIR
from .database import Base, SessionLocal, engine
from .migrations import ensure_columns
from .routers import admin, ai, analytics, auth, integrations, locations, notifications, org, reports
from .seed import seed

app = FastAPI(title=APP_NAME, description=APP_TAGLINE, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    org.router,
    locations.router,
    analytics.router,
    ai.router,
    integrations.router,
    reports.router,
    notifications.router,
    admin.router,
):
    app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "version": "0.1.0"}


WEB_DIR = BASE_DIR / "web"
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

    @app.get("/")
    def index():
        return FileResponse(Path(WEB_DIR) / "index.html")

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = Path(WEB_DIR) / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(Path(WEB_DIR) / "index.html")
