"""Tests for backend/ml/accuracy.py (design doc §8.2).

Uses a temp/in-memory DB with real migrations applied (backend.db.migrate).
backend.db.repository does not exist yet (being built in parallel), so rows
are inserted with raw SQL matching the model_predictions schema in
backend/db/migrations/0001_initial.sql -- this also exercises accuracy.py's
fallback query path.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

from backend.db.connection import connect
from backend.db.migrate import apply_migrations
from backend.domain.enums import ModelName
from backend.ml.accuracy import accuracy_by_week, rolling_accuracy


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    apply_migrations(connection)
    yield connection
    connection.close()


def _insert_prediction(
    conn: sqlite3.Connection,
    model_name: str,
    predicted_probability: float,
    actual_label: str | None,
    resolved: bool,
    resolved_at: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO model_predictions "
        "(prediction_id, model_name, target_id, predicted_at, predicted_probability, "
        "actual_label, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            model_name,
            str(uuid.uuid4()),
            datetime.utcnow().isoformat(sep=" "),
            predicted_probability,
            actual_label,
            resolved_at if resolved else None,
        ),
    )
    conn.commit()


def test_rolling_accuracy_none_with_no_predictions_at_all(conn: sqlite3.Connection) -> None:
    assert rolling_accuracy(conn, ModelName.IMAGE.value) is None


def test_rolling_accuracy_ignores_unresolved_predictions(conn: sqlite3.Connection) -> None:
    _insert_prediction(conn, ModelName.IMAGE.value, 0.9, None, resolved=False)
    assert rolling_accuracy(conn, ModelName.IMAGE.value) is None


def test_rolling_accuracy_computes_fraction_correct(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow()
    rows = [
        (0.9, "yes"),  # correct: >=0.5 -> yes, matches
        (0.1, "no"),  # correct: <0.5 -> no, matches
        (0.8, "no"),  # wrong: >=0.5 -> yes, actual no
        (0.4, "yes"),  # wrong: <0.5 -> no, actual yes
    ]
    for i, (prob, actual) in enumerate(rows):
        _insert_prediction(
            conn,
            ModelName.TEXT.value,
            prob,
            actual,
            resolved=True,
            resolved_at=(now + timedelta(minutes=i)).isoformat(sep=" "),
        )
    assert rolling_accuracy(conn, ModelName.TEXT.value) == pytest.approx(0.5)


def test_rolling_accuracy_is_per_model(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow()
    _insert_prediction(conn, ModelName.IMAGE.value, 0.9, "yes", resolved=True, resolved_at=now.isoformat(sep=" "))
    _insert_prediction(conn, ModelName.TEXT.value, 0.9, "no", resolved=True, resolved_at=now.isoformat(sep=" "))
    assert rolling_accuracy(conn, ModelName.IMAGE.value) == pytest.approx(1.0)
    assert rolling_accuracy(conn, ModelName.TEXT.value) == pytest.approx(0.0)


def test_rolling_accuracy_respects_explicit_window(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow()
    for i, (prob, actual) in enumerate([(0.9, "yes"), (0.9, "yes"), (0.9, "yes")]):
        _insert_prediction(
            conn, ModelName.COMBINED.value, prob, actual, resolved=True,
            resolved_at=(now + timedelta(minutes=i)).isoformat(sep=" "),
        )
    for i, (prob, actual) in enumerate([(0.9, "no"), (0.9, "no")], start=3):
        _insert_prediction(
            conn, ModelName.COMBINED.value, prob, actual, resolved=True,
            resolved_at=(now + timedelta(minutes=i)).isoformat(sep=" "),
        )
    # Most recent 2 rows (by resolved_at) are both wrong.
    assert rolling_accuracy(conn, ModelName.COMBINED.value, window=2) == pytest.approx(0.0)
    # All 5 rows: 3 correct, 2 wrong.
    assert rolling_accuracy(conn, ModelName.COMBINED.value, window=100) == pytest.approx(0.6)


class _FakeModelConfig:
    accuracy_window = 2


class _FakeConfig:
    model = _FakeModelConfig()


def test_rolling_accuracy_uses_config_default_window(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.ml.accuracy.CONFIG", _FakeConfig())
    now = datetime.utcnow()
    for i, (prob, actual) in enumerate([(0.9, "yes"), (0.9, "yes")]):
        _insert_prediction(
            conn, ModelName.IMAGE.value, prob, actual, resolved=True,
            resolved_at=(now + timedelta(minutes=i)).isoformat(sep=" "),
        )
    for i, (prob, actual) in enumerate([(0.9, "no"), (0.9, "no")], start=2):
        _insert_prediction(
            conn, ModelName.IMAGE.value, prob, actual, resolved=True,
            resolved_at=(now + timedelta(minutes=i)).isoformat(sep=" "),
        )
    # 4 rows total, but the (patched) default window is 2 -> only the 2 most
    # recent (both wrong) are counted.
    assert rolling_accuracy(conn, ModelName.IMAGE.value) == pytest.approx(0.0)


def test_accuracy_by_week_groups_by_iso_week(conn: sqlite3.Connection) -> None:
    week1 = datetime(2026, 1, 5)  # Monday, ISO week 2026-W02
    week2 = datetime(2026, 1, 12)  # Monday, ISO week 2026-W03
    _insert_prediction(
        conn, ModelName.IMAGE.value, 0.9, "yes", resolved=True, resolved_at=week1.isoformat(sep=" ")
    )
    _insert_prediction(
        conn, ModelName.IMAGE.value, 0.9, "no", resolved=True,
        resolved_at=(week1 + timedelta(hours=1)).isoformat(sep=" "),
    )
    _insert_prediction(
        conn, ModelName.IMAGE.value, 0.9, "yes", resolved=True, resolved_at=week2.isoformat(sep=" ")
    )

    result = accuracy_by_week(conn, ModelName.IMAGE.value)

    assert [row["n"] for row in result] == [2, 1]
    assert result[0]["accuracy"] == pytest.approx(0.5)
    assert result[1]["accuracy"] == pytest.approx(1.0)
    assert result[0]["week"] < result[1]["week"]


def test_accuracy_by_week_empty_when_no_resolved_predictions(conn: sqlite3.Connection) -> None:
    assert accuracy_by_week(conn, ModelName.IMAGE.value) == []
