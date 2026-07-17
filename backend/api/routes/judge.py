"""POST /judge: persist a human judgment (photo label or text verdict) and
recompute verdicts/decisions via ``backend.services.verdict_engine`` (design
doc §6.2, §6.3). This route never re-implements the aggregation/decision
rules -- it only maps the request onto a verdict_engine call.

Body: ``{"item_type": "photo"|"text", "id": <photo_id or profile_id>,
"label": <PhotoLabel or Verdict value>}``. For a photo item, ``id`` is the
photo_id and this route looks up its owning profile_id; for a text item,
``id`` *is* the profile_id (matches ``DrawProfile``/pool-entry semantics in
``backend.logic.draw``, where a text pool entry's ``item_id`` is the
profile_id).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_db
from backend.domain.enums import PhotoLabel, Verdict
from backend.domain.types import DecisionResult

router = APIRouter(prefix="/judge", tags=["judge"])


class JudgeRequest(BaseModel):
    item_type: Literal["photo", "text"]
    id: str
    label: str


@router.post("")
def judge(body: JudgeRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    from backend.services import verdict_engine

    try:
        if body.item_type == "photo":
            result = _judge_photo(conn, verdict_engine, body.id, body.label)
        else:
            result = _judge_text(conn, verdict_engine, body.id, body.label)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _response(result)


def _judge_photo(conn: sqlite3.Connection, verdict_engine: Any, photo_id: str, raw_label: str) -> DecisionResult:
    label = _parse_enum(PhotoLabel, raw_label, "photo label")
    row = conn.execute("SELECT profile_id FROM photos WHERE photo_id = ?", (photo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown photo id: {photo_id}")
    result: DecisionResult = verdict_engine.on_photo_judged(conn, row["profile_id"], photo_id, label)
    return result


def _judge_text(conn: sqlite3.Connection, verdict_engine: Any, profile_id: str, raw_label: str) -> DecisionResult:
    verdict = _parse_enum(Verdict, raw_label, "text verdict")
    if verdict not in (Verdict.YES, Verdict.NO):
        raise HTTPException(status_code=422, detail="text verdict must be yes or no")
    result: DecisionResult = verdict_engine.on_text_judged(conn, profile_id, verdict)
    return result


def _parse_enum(enum_cls: Any, raw_value: str, what: str) -> Any:
    try:
        return enum_cls(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid {what}: {raw_value}") from exc


def _response(result: DecisionResult) -> dict:
    return {
        "decision": result.decision.value if result.decision is not None else None,
        "source": result.source.value if result.source is not None else None,
        "route_to_review": result.route_to_review,
        "trigger_reason": result.trigger_reason,
    }
