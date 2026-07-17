"""GET /profiles/{profile_id}: a single profile plus its photos."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_db

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/{profile_id}")
def get_profile(profile_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    from backend.db import repository

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"unknown profile_id: {profile_id}")
    photos = repository.get_photos(conn, profile_id)
    return {"profile": dict(profile), "photos": [dict(photo) for photo in photos]}
