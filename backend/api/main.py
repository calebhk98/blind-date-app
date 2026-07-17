"""FastAPI orchestrator app (design doc §4, §8.1).

Only routers are wired up here. Every route handler lazily imports
adapters/ml/repository inside its own function body (see routes/*.py), so
this module -- and therefore ``from backend.api.main import app`` -- never
needs torch, playwright, or Appium-Python-Client to succeed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import (
    apps,
    dashboard,
    draw,
    inference,
    judge,
    photos,
    profiles,
    review,
    settings,
    swipe,
)
from backend.config import CONFIG

app = FastAPI(title="Blind Date App Orchestrator")

# The React UI is served from a different origin (Next.js on :3000) and calls
# this API from the browser, so it needs CORS. Origins come from config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CONFIG.api.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(apps.router)
app.include_router(profiles.router)
app.include_router(draw.router)
app.include_router(judge.router)
app.include_router(review.router)
app.include_router(swipe.router)
app.include_router(inference.router)
app.include_router(dashboard.router)
app.include_router(photos.router)
app.include_router(settings.router)
