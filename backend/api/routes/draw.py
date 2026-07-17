"""GET /draw: pick one un-judged item across every app (design doc §7).

Thin route: pulls the flat pending-item rows from ``backend.db.repository``
and maps them into ``backend.logic.draw.DrawProfile`` -- the only
translation this file does -- then hands off to the pure pool-builder/picker
in ``backend.logic.draw``. The draw rule itself (which app, which item) lives
there and only there (design doc §4: single source of truth).
"""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_db
from backend.domain.enums import Modality

router = APIRouter(prefix="/draw", tags=["draw"])


@router.get("")
def draw(hard_filter: bool = True, conn: sqlite3.Connection = Depends(get_db)) -> dict | None:
    from backend.db import repository
    from backend.logic.draw import build_pending_pool, draw_one

    profiles = _pending_profiles(conn, repository)
    pool = build_pending_pool(profiles, hard_filter_enabled=hard_filter)
    entry = draw_one(pool, random.Random())
    if entry is None:
        return None

    return {
        "app_id": entry.app_id,
        "modality": entry.modality.value,
        "item_id": entry.item_id,
        "profile_id": entry.profile_id,
        "hard_filter_hit": entry.hard_filter_hit,
        # The UI shows a single photo OR the bio text blind/separately -- ship
        # the actual content alongside the pool-entry identifiers so it
        # doesn't need a second round trip to render the draw.
        "content": _load_content(conn, repository, entry),
    }


def _pending_profiles(conn: sqlite3.Connection, repository: Any) -> list:
    from backend.logic.draw import DrawProfile

    by_profile: dict[str, dict] = {}
    for row in repository.list_pending_photo_items(conn):
        bucket = _profile_bucket(by_profile, row)
        bucket["pending_photo_ids"].append(row["photo_id"])
    for row in repository.list_pending_text_items(conn):
        bucket = _profile_bucket(by_profile, row)
        bucket["text_pending"] = True

    return [
        DrawProfile(
            app_id=data["app_id"],
            profile_id=profile_id,
            hard_filter_hit=data["hard_filter_hit"],
            text_pending=data["text_pending"],
            pending_photo_ids=data["pending_photo_ids"],
        )
        for profile_id, data in by_profile.items()
    ]


def _profile_bucket(by_profile: dict[str, dict], row: Any) -> dict:
    profile_id = row["profile_id"]
    return by_profile.setdefault(
        profile_id,
        {
            "app_id": row["app_id"],
            "hard_filter_hit": bool(row["hard_filter_hit"]),
            "text_pending": False,
            "pending_photo_ids": [],
        },
    )


def _load_content(conn: sqlite3.Connection, repository: Any, entry: Any) -> dict:
    if entry.modality == Modality.TEXT:
        profile = repository.get_profile(conn, entry.profile_id)
        return {"bio_text": profile["bio_text"] if profile else None}
    photos = repository.get_photos(conn, entry.profile_id)
    match = next((photo for photo in photos if photo["photo_id"] == entry.item_id), None)
    return {"file_path": match["file_path"] if match else None}
