"""GET /apps: list every registered dating-app row (design doc §4)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.api.deps import get_db

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def list_apps(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    from backend.db import repository

    return [dict(row) for row in repository.list_apps(conn)]
