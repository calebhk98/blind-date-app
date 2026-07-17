"""POST /review/{profile_id}: record the human decision on a profile routed
to full-profile review (design doc §6.3) and set its final_decision.

All of the actual logic -- re-deriving the trigger_reason, writing
review_decisions, setting final_decision -- lives in
``backend.services.verdict_engine.record_review_decision`` (single source of
truth); this route only translates the HTTP request/response.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_db
from backend.domain.enums import UserDecision

router = APIRouter(prefix="/review", tags=["review"])


class ReviewRequest(BaseModel):
    user_decision: str


@router.post("/{profile_id}")
def review(profile_id: str, body: ReviewRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    from backend.services import verdict_engine

    try:
        user_decision = UserDecision(body.user_decision)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"invalid user_decision: {body.user_decision}"
        ) from exc

    try:
        result = verdict_engine.record_review_decision(conn, profile_id, user_decision)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "decision": result.decision.value if result.decision is not None else None,
        "source": result.source.value if result.source is not None else None,
    }
