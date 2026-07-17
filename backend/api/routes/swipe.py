"""POST /swipe/{profile_id}/approve: execute a swipe the user has explicitly
approved (design doc §1: the user approves every swipe -- nothing swipes
autonomously). Not listed among the route files enumerated for this issue,
but the endpoint itself is spelled out explicitly in the design doc excerpt
and needs a home; kept as its own single-responsibility router file to match
every other route module.

All the actual work (idempotency check, adapter lookup/dispatch) lives in
``backend.services.swipe_service``.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_db

router = APIRouter(prefix="/swipe", tags=["swipe"])


@router.post("/{profile_id}/approve")
def approve_swipe(profile_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    from backend.services import swipe_service

    try:
        swiped_now = swipe_service.approve(conn, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"profile_id": profile_id, "swiped_now": swiped_now}
