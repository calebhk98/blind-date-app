"""Data-access layer (design doc §6). The API/services layer depends on these
exact function names and signatures -- do not rename without updating callers.

Every function takes ``conn: sqlite3.Connection`` as the first argument (see
``backend.db.connection.connect``). All SQL is parameterized. Enum-typed
parameters (``backend_type``, ``*_verdict``, ``label``, ``decision``,
``source``, ``trigger_reason``, ``user_decision``, ``model_name``,
``actual_label``) accept the enum member's ``.value`` (a plain ``str``); the
DB-level CHECK constraints (backed by ``backend.domain.enums``) are the
authority on which values are legal, so nothing is re-validated in Python
here -- a bad value fails loud via ``sqlite3.IntegrityError``.
"""

from __future__ import annotations

import json
import sqlite3

from backend.config import CONFIG
from backend.db.connection import transaction
from backend.logic.hard_filter import HardFilterCriteria


def insert_app(conn: sqlite3.Connection, app_id: str, backend_type: str, display_name: str) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO apps (app_id, backend_type, display_name) VALUES (?, ?, ?)",
            (app_id, backend_type, display_name),
        )


def list_apps(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM apps").fetchall()


def insert_profile(
    conn: sqlite3.Connection,
    *,
    profile_id: str,
    app_id: str,
    external_id: str,
    bio_text: str,
    hard_filter_hit: bool = False,
) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO profiles "
            "(profile_id, app_id, external_id, bio_text, fetched_at, hard_filter_hit) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (profile_id, app_id, external_id, bio_text, int(hard_filter_hit)),
        )


def insert_photo(
    conn: sqlite3.Connection,
    *,
    photo_id: str,
    profile_id: str,
    file_path: str,
    order_index: int,
) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO photos (photo_id, profile_id, file_path, order_index) "
            "VALUES (?, ?, ?, ?)",
            (photo_id, profile_id, file_path, order_index),
        )


def get_profile(conn: sqlite3.Connection, profile_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    return row


def get_photos(conn: sqlite3.Connection, profile_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM photos WHERE profile_id = ? ORDER BY order_index",
        (profile_id,),
    ).fetchall()


def list_pending_photo_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """(photo_id, profile_id, app_id, hard_filter_hit) for every photo still
    awaiting a human label."""
    return conn.execute(
        "SELECT p.photo_id AS photo_id, p.profile_id AS profile_id, "
        "pr.app_id AS app_id, pr.hard_filter_hit AS hard_filter_hit "
        "FROM photos p JOIN profiles pr ON pr.profile_id = p.profile_id "
        "WHERE p.label = 'pending'"
    ).fetchall()


def list_pending_text_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """(profile_id, app_id, hard_filter_hit) for every profile whose bio text
    still awaits a verdict."""
    return conn.execute(
        "SELECT profile_id, app_id, hard_filter_hit FROM profiles "
        "WHERE text_verdict = 'pending'"
    ).fetchall()


def set_photo_label(conn: sqlite3.Connection, photo_id: str, label: str) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE photos SET label = ?, judged_at = CURRENT_TIMESTAMP "
            "WHERE photo_id = ?",
            (label, photo_id),
        )


def set_image_verdict(conn: sqlite3.Connection, profile_id: str, verdict: str) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE profiles SET image_verdict = ? WHERE profile_id = ?",
            (verdict, profile_id),
        )


def set_text_verdict(conn: sqlite3.Connection, profile_id: str, verdict: str) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE profiles SET text_verdict = ? WHERE profile_id = ?",
            (verdict, profile_id),
        )


def set_final_decision(
    conn: sqlite3.Connection, profile_id: str, decision: str, source: str
) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE profiles SET final_decision = ?, decision_source = ? "
            "WHERE profile_id = ?",
            (decision, source, profile_id),
        )


def is_swiped(conn: sqlite3.Connection, profile_id: str) -> bool:
    row = conn.execute(
        "SELECT swiped FROM profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No profile with profile_id={profile_id!r}")
    return bool(row["swiped"])


def mark_swiped(conn: sqlite3.Connection, profile_id: str) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE profiles SET swiped = 1 WHERE profile_id = ?", (profile_id,)
        )


def insert_review_decision(
    conn: sqlite3.Connection,
    *,
    review_id: str,
    profile_id: str,
    trigger_reason: str,
    image_verdict_at_review: str,
    text_verdict_at_review: str,
    user_decision: str,
) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO review_decisions "
            "(review_id, profile_id, trigger_reason, image_verdict_at_review, "
            "text_verdict_at_review, user_decision, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                review_id,
                profile_id,
                trigger_reason,
                image_verdict_at_review,
                text_verdict_at_review,
                user_decision,
            ),
        )


def insert_prediction(
    conn: sqlite3.Connection,
    *,
    prediction_id: str,
    model_name: str,
    target_id: str,
    predicted_probability: float,
) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO model_predictions "
            "(prediction_id, model_name, target_id, predicted_at, "
            "predicted_probability, actual_label, resolved_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, NULL, NULL)",
            (prediction_id, model_name, target_id, predicted_probability),
        )


def resolve_prediction(
    conn: sqlite3.Connection, prediction_id: str, actual_label: str
) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE model_predictions SET actual_label = ?, "
            "resolved_at = CURRENT_TIMESTAMP WHERE prediction_id = ?",
            (actual_label, prediction_id),
        )


def recent_predictions(
    conn: sqlite3.Connection, model_name: str, window: int
) -> list[sqlite3.Row]:
    """The most recent ``window`` *resolved* predictions for ``model_name``,
    newest first (used for the rolling-accuracy computation, design doc
    §8.2)."""
    return conn.execute(
        "SELECT * FROM model_predictions "
        "WHERE model_name = ? AND resolved_at IS NOT NULL "
        "ORDER BY resolved_at DESC, prediction_id DESC "
        "LIMIT ?",
        (model_name, window),
    ).fetchall()


# --- settings (design doc §7.4, issue #21) ---------------------------------
#
# Generic JSON-valued key/value store (migration 0002) so runtime-editable
# settings don't need a new column/table per setting. get_setting/set_setting
# are the untyped primitives; get_hard_filter_settings/set_hard_filter_settings
# below are the one typed consumer today.

_HARD_FILTER_CRITERIA_KEY = "hard_filter_criteria"
_HARD_FILTER_ENABLED_KEY = "hard_filter_enabled"


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_hard_filter_settings(conn: sqlite3.Connection) -> tuple[HardFilterCriteria, bool]:
    """Stored hard-filter criteria + the session-level enabled toggle.

    Seeded from ``CONFIG.hard_filter`` (the env-driven defaults) the first
    time this is read, before anything has ever been saved via
    ``set_hard_filter_settings`` -- the settings table itself stays empty
    until a write happens, so "seeded" here means "computed on read", not
    "written on read".
    """
    criteria_raw = get_setting(conn, _HARD_FILTER_CRITERIA_KEY)
    enabled_raw = get_setting(conn, _HARD_FILTER_ENABLED_KEY)

    criteria = (
        _criteria_from_json(json.loads(criteria_raw))
        if criteria_raw is not None
        else _default_hard_filter_criteria()
    )
    enabled = (
        bool(json.loads(enabled_raw))
        if enabled_raw is not None
        else CONFIG.hard_filter.enabled_by_default
    )
    return criteria, enabled


def set_hard_filter_settings(
    conn: sqlite3.Connection, criteria: HardFilterCriteria, enabled: bool
) -> None:
    set_setting(conn, _HARD_FILTER_CRITERIA_KEY, json.dumps(_criteria_to_json(criteria)))
    set_setting(conn, _HARD_FILTER_ENABLED_KEY, json.dumps(bool(enabled)))


def _default_hard_filter_criteria() -> HardFilterCriteria:
    defaults = CONFIG.hard_filter
    return HardFilterCriteria(
        min_age=defaults.min_age,
        max_age=defaults.max_age,
        max_distance=defaults.max_distance,
        blocked_keywords=tuple(defaults.blocked_keywords),
        required_keywords=tuple(defaults.required_keywords),
    )


def _criteria_to_json(criteria: HardFilterCriteria) -> dict:
    return {
        "min_age": criteria.min_age,
        "max_age": criteria.max_age,
        "max_distance": criteria.max_distance,
        "blocked_keywords": list(criteria.blocked_keywords),
        "required_keywords": list(criteria.required_keywords),
    }


def _criteria_from_json(data: dict) -> HardFilterCriteria:
    return HardFilterCriteria(
        min_age=data.get("min_age"),
        max_age=data.get("max_age"),
        max_distance=data.get("max_distance"),
        blocked_keywords=tuple(data.get("blocked_keywords", [])),
        required_keywords=tuple(data.get("required_keywords", [])),
    )
