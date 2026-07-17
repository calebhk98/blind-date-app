"""Rolling model accuracy, decoupled from UI and training (design doc §8.2).

Reads resolved predictions from ``model_predictions`` (populated whenever a
prediction's real outcome becomes known -- e.g. the profile is later swiped
or reviewed) and reports the fraction where the model's yes/no call matched
``actual_label``.

Prefers ``backend.db.repository.recent_predictions`` when available (that
module is being built in parallel per design doc §6.1/§8.2); falls back to
an equivalent raw-SQL query against ``model_predictions`` so this module
works standalone regardless of build order.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from backend.config import CONFIG

_YES = "yes"
_NO = "no"


def _predicted_label(predicted_probability: float) -> str:
    return _YES if predicted_probability >= 0.5 else _NO


def _recent_predictions_fallback(
    conn: sqlite3.Connection, model_name: str, window: int
) -> list[sqlite3.Row]:
    """Resolved predictions for ``model_name``, most recent first, capped at
    ``window`` rows. Mirrors the query ``backend.db.repository.
    recent_predictions`` is expected to run -- used only until that module
    lands."""
    cursor = conn.execute(
        "SELECT predicted_probability, actual_label, resolved_at "
        "FROM model_predictions "
        "WHERE model_name = ? AND resolved_at IS NOT NULL AND actual_label IS NOT NULL "
        "ORDER BY resolved_at DESC LIMIT ?",
        (model_name, window),
    )
    return cursor.fetchall()


def _fetch_recent_predictions(
    conn: sqlite3.Connection, model_name: str, window: int
) -> list[Any]:
    try:
        from backend.db import repository
    except ImportError:
        repository = None  # type: ignore[assignment]

    if repository is not None and hasattr(repository, "recent_predictions"):
        return list(repository.recent_predictions(conn, model_name, window))
    return _recent_predictions_fallback(conn, model_name, window)


def rolling_accuracy(
    conn: sqlite3.Connection, model_name: str, window: int | None = None
) -> float | None:
    """Fraction of the last ``window`` resolved predictions for
    ``model_name`` whose thresholded call (>= 0.5 -> yes) matched
    ``actual_label``. ``None`` if there are no resolved predictions yet
    (never 0.0 -- "no data" and "always wrong" must stay distinguishable).
    """
    effective_window = window if window is not None else CONFIG.model.accuracy_window
    rows = _fetch_recent_predictions(conn, model_name, effective_window)
    if not rows:
        return None
    correct = sum(
        1 for row in rows if _predicted_label(row["predicted_probability"]) == row["actual_label"]
    )
    return correct / len(rows)


def _iso_week(timestamp: str) -> str:
    normalized = timestamp.replace(" ", "T", 1) if " " in timestamp else timestamp
    dt = datetime.fromisoformat(normalized)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def accuracy_by_week(conn: sqlite3.Connection, model_name: str) -> list[dict[str, Any]]:
    """Optional weekly-bucketed accuracy breakdown for ``model_name``.

    Returns a list of ``{"week": "<ISO year>-W<ISO week>", "accuracy": float,
    "n": int}`` dicts, oldest week first. Separate from ``rolling_accuracy``
    (which uses a fixed row-count window) -- this is for trend dashboards.
    """
    cursor = conn.execute(
        "SELECT predicted_probability, actual_label, resolved_at "
        "FROM model_predictions "
        "WHERE model_name = ? AND resolved_at IS NOT NULL AND actual_label IS NOT NULL "
        "ORDER BY resolved_at ASC",
        (model_name,),
    )
    rows = cursor.fetchall()

    buckets: dict[str, list[bool]] = {}
    for row in rows:
        week = _iso_week(row["resolved_at"])
        is_correct = _predicted_label(row["predicted_probability"]) == row["actual_label"]
        buckets.setdefault(week, []).append(is_correct)

    return [
        {"week": week, "accuracy": sum(results) / len(results), "n": len(results)}
        for week, results in sorted(buckets.items())
    ]
