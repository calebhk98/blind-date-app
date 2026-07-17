"""Tests for the migration runner (backend/db/migrate.py) and the guard that
keeps migrations/0001_initial.sql's CHECK constraints in sync with the enums
in backend/domain/enums.py (the single source of truth, per that module's
docstring)."""

from __future__ import annotations

import sqlite3

import pytest

from backend.db.connection import connect
from backend.db.migrate import MIGRATIONS_DIR, apply_migrations
from backend.domain.enums import (
    BackendType,
    Decision,
    DecisionSource,
    ModelName,
    PhotoLabel,
    TriggerReason,
    UserDecision,
    Verdict,
)

INITIAL_SQL = (MIGRATIONS_DIR / "0001_initial.sql").read_text()

# (enum class, column it constrains in the schema)
ENUM_COLUMNS = [
    (BackendType, "backend_type"),
    (Verdict, "image_verdict"),
    (Verdict, "text_verdict"),
    (Decision, "final_decision"),
    (DecisionSource, "decision_source"),
    (PhotoLabel, "label"),
    (TriggerReason, "trigger_reason"),
    (UserDecision, "user_decision"),
    (ModelName, "model_name"),
]


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    yield connection
    connection.close()


@pytest.mark.parametrize("enum_cls, column", ENUM_COLUMNS)
def test_check_clause_matches_enum(enum_cls: type, column: str) -> None:
    """The literal CHECK clause hand-written into the .sql must match what the
    enum would generate -- catches drift between enums.py and the migration."""
    expected_clause = enum_cls.sql_check(column)
    assert expected_clause in INITIAL_SQL, (
        f"{enum_cls.__name__}.sql_check({column!r}) = {expected_clause!r} "
        "not found verbatim in 0001_initial.sql -- migration has drifted "
        "from the enum single source of truth"
    )


def test_apply_migrations_creates_all_tables(conn: sqlite3.Connection) -> None:
    applied = apply_migrations(conn)
    assert applied == [1, 2]

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert tables == {
        "apps",
        "profiles",
        "photos",
        "review_decisions",
        "model_predictions",
        "schema_version",
        "settings",  # migration 0002 (design doc §7.4, issue #21)
    }


def test_apply_migrations_is_idempotent(conn: sqlite3.Connection) -> None:
    first = apply_migrations(conn)
    second = apply_migrations(conn)
    assert first == [1, 2]
    assert second == []

    version_rows = conn.execute("SELECT version FROM schema_version").fetchall()
    assert [row["version"] for row in version_rows] == [1, 2]


def test_indexes_created(conn: sqlite3.Connection) -> None:
    apply_migrations(conn)
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    assert {
        "idx_profiles_app_id",
        "idx_photos_profile_id",
        "idx_photos_label",
        "idx_model_predictions_model_name",
    }.issubset(indexes)


def test_bad_enum_value_rejected_by_check_constraint(conn: sqlite3.Connection) -> None:
    apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO apps (app_id, backend_type, display_name) "
            "VALUES ('a1', 'not_a_real_backend', 'Tinder')"
        )


def test_foreign_key_enforced(conn: sqlite3.Connection) -> None:
    apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO profiles "
            "(profile_id, app_id, external_id, bio_text, fetched_at) "
            "VALUES ('p1', 'no-such-app', 'ext1', 'hi', CURRENT_TIMESTAMP)"
        )
