"""GET /dashboard: pending counts, final-decision counts, and rolling
accuracy per model (design doc §8.1, §8.2)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.api.deps import get_db
from backend.config import CONFIG
from backend.domain.enums import Decision, ModelName

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    from backend.db import repository

    return {
        "pending": {
            "photos": len(repository.list_pending_photo_items(conn)),
            "text": len(repository.list_pending_text_items(conn)),
        },
        "decisions": _decision_counts(conn),
        "rolling_accuracy": _rolling_accuracy(conn),
    }


def _decision_counts(conn: sqlite3.Connection) -> dict:
    # No repository helper exposes this aggregate; profiles.final_decision is
    # a plain schema column, so a direct read-only aggregate query is the
    # pragmatic choice here rather than adding a bespoke repository function
    # for a single dashboard tile.
    counts = {decision.value: 0 for decision in Decision}
    rows = conn.execute(
        "SELECT final_decision, COUNT(*) AS n FROM profiles GROUP BY final_decision"
    ).fetchall()
    counts.update({row["final_decision"]: row["n"] for row in rows})
    return counts


def _rolling_accuracy(conn: sqlite3.Connection) -> dict:
    from backend.ml.accuracy import rolling_accuracy

    return {
        model.value: rolling_accuracy(conn, model.value, window=CONFIG.model.accuracy_window)
        for model in ModelName
    }
