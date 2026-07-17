"""GET/PUT /settings/hard-filter: the runtime-editable hard-filter criteria
and on/off toggle (design doc §7.4, issue #21).

Thin route: (de)serializes the request/response shape and hands off to
``backend.db.repository.get_hard_filter_settings`` /
``set_hard_filter_settings`` -- the persisted values are the single source
of truth that ``/draw`` (default toggle) and ``fetch_service``
(``hard_filter_hit`` computation, issue #20) both read.

Pydantic validates request types for us (fail loud: a malformed body is a
422, not a silently-coerced value).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_db
from backend.logic.hard_filter import HardFilterCriteria

router = APIRouter(prefix="/settings", tags=["settings"])


class HardFilterCriteriaBody(BaseModel):
    min_age: int | None = None
    max_age: int | None = None
    max_distance: int | None = None
    blocked_keywords: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)


class HardFilterSettingsBody(BaseModel):
    criteria: HardFilterCriteriaBody
    enabled: bool


@router.get("/hard-filter")
def get_hard_filter(conn: sqlite3.Connection = Depends(get_db)) -> HardFilterSettingsBody:
    from backend.db import repository

    criteria, enabled = repository.get_hard_filter_settings(conn)
    return _to_body(criteria, enabled)


@router.put("/hard-filter")
def put_hard_filter(
    body: HardFilterSettingsBody, conn: sqlite3.Connection = Depends(get_db)
) -> HardFilterSettingsBody:
    from backend.db import repository

    # Keywords are matched against lowered profile text (see
    # fetch_service._profile_text), so normalize on write rather than
    # re-normalizing on every evaluation.
    criteria = HardFilterCriteria(
        min_age=body.criteria.min_age,
        max_age=body.criteria.max_age,
        max_distance=body.criteria.max_distance,
        blocked_keywords=_normalize_keywords(body.criteria.blocked_keywords),
        required_keywords=_normalize_keywords(body.criteria.required_keywords),
    )
    repository.set_hard_filter_settings(conn, criteria, body.enabled)
    return _to_body(criteria, body.enabled)


def _normalize_keywords(keywords: list[str]) -> tuple[str, ...]:
    return tuple(k.strip().lower() for k in keywords if k.strip())


def _to_body(criteria: HardFilterCriteria, enabled: bool) -> HardFilterSettingsBody:
    return HardFilterSettingsBody(
        criteria=HardFilterCriteriaBody(
            min_age=criteria.min_age,
            max_age=criteria.max_age,
            max_distance=criteria.max_distance,
            blocked_keywords=list(criteria.blocked_keywords),
            required_keywords=list(criteria.required_keywords),
        ),
        enabled=enabled,
    )
