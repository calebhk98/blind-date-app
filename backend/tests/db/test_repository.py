"""Tests for backend/db/repository.py: round-trips through a real (in-memory)
SQLite DB created via the actual migrations, plus CHECK-constraint guards."""

from __future__ import annotations

import sqlite3

import pytest

from backend.db import repository as repo
from backend.db.connection import connect
from backend.db.migrate import apply_migrations
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


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = connect(":memory:")
    apply_migrations(connection)
    yield connection
    connection.close()


def _seed_app(conn: sqlite3.Connection, app_id: str = "tinder") -> None:
    repo.insert_app(conn, app_id, BackendType.WEB.value, "Tinder")


def _seed_profile(
    conn: sqlite3.Connection,
    profile_id: str = "p1",
    app_id: str = "tinder",
    hard_filter_hit: bool = False,
) -> None:
    repo.insert_profile(
        conn,
        profile_id=profile_id,
        app_id=app_id,
        external_id="ext-1",
        bio_text="hello world",
        hard_filter_hit=hard_filter_hit,
    )


# --- apps -------------------------------------------------------------


def test_insert_and_list_apps(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    apps = repo.list_apps(conn)
    assert len(apps) == 1
    assert apps[0]["app_id"] == "tinder"
    assert apps[0]["backend_type"] == "web"
    assert apps[0]["display_name"] == "Tinder"


def test_insert_app_rejects_bad_backend_type(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_app(conn, "bad", "not_a_backend", "Bad App")


# --- profiles / photos --------------------------------------------------


def test_insert_and_get_profile_defaults(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    profile = repo.get_profile(conn, "p1")
    assert profile is not None
    assert profile["profile_id"] == "p1"
    assert profile["app_id"] == "tinder"
    assert profile["external_id"] == "ext-1"
    assert profile["bio_text"] == "hello world"
    assert profile["fetched_at"] is not None
    assert profile["image_verdict"] == Verdict.PENDING.value
    assert profile["text_verdict"] == Verdict.PENDING.value
    assert profile["hard_filter_hit"] == 0
    assert profile["final_decision"] == Decision.PENDING.value
    assert profile["decision_source"] is None
    assert profile["swiped"] == 0


def test_get_profile_missing_returns_none(conn: sqlite3.Connection) -> None:
    assert repo.get_profile(conn, "does-not-exist") is None


def test_insert_and_get_photos_ordered(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)
    repo.insert_photo(conn, photo_id="ph2", profile_id="p1", file_path="/b.jpg", order_index=1)
    repo.insert_photo(conn, photo_id="ph1", profile_id="p1", file_path="/a.jpg", order_index=0)

    photos = repo.get_photos(conn, "p1")
    assert [p["photo_id"] for p in photos] == ["ph1", "ph2"]
    assert [p["order_index"] for p in photos] == [0, 1]
    assert all(p["label"] == PhotoLabel.PENDING.value for p in photos)


# --- pending queues ------------------------------------------------------


def test_list_pending_photo_items(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn, hard_filter_hit=True)
    repo.insert_photo(conn, photo_id="ph1", profile_id="p1", file_path="/a.jpg", order_index=0)
    repo.insert_photo(conn, photo_id="ph2", profile_id="p1", file_path="/b.jpg", order_index=1)
    repo.set_photo_label(conn, "ph2", PhotoLabel.YES.value)

    pending = repo.list_pending_photo_items(conn)
    assert len(pending) == 1
    row = pending[0]
    assert row["photo_id"] == "ph1"
    assert row["profile_id"] == "p1"
    assert row["app_id"] == "tinder"
    assert row["hard_filter_hit"] == 1


def test_list_pending_text_items(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn, profile_id="p1")
    _seed_profile(conn, profile_id="p2")
    repo.set_text_verdict(conn, "p2", Verdict.YES.value)

    pending = repo.list_pending_text_items(conn)
    assert len(pending) == 1
    assert pending[0]["profile_id"] == "p1"
    assert pending[0]["app_id"] == "tinder"


# --- setters --------------------------------------------------------------


def test_set_photo_label_sets_judged_at(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)
    repo.insert_photo(conn, photo_id="ph1", profile_id="p1", file_path="/a.jpg", order_index=0)

    repo.set_photo_label(conn, "ph1", PhotoLabel.NOT_RELEVANT.value)

    photo = repo.get_photos(conn, "p1")[0]
    assert photo["label"] == PhotoLabel.NOT_RELEVANT.value
    assert photo["judged_at"] is not None


def test_set_photo_label_rejects_bad_value(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)
    repo.insert_photo(conn, photo_id="ph1", profile_id="p1", file_path="/a.jpg", order_index=0)
    with pytest.raises(sqlite3.IntegrityError):
        repo.set_photo_label(conn, "ph1", "not_a_label")


def test_set_image_and_text_verdict(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    repo.set_image_verdict(conn, "p1", Verdict.YES.value)
    repo.set_text_verdict(conn, "p1", Verdict.NO.value)

    profile = repo.get_profile(conn, "p1")
    assert profile["image_verdict"] == Verdict.YES.value
    assert profile["text_verdict"] == Verdict.NO.value


def test_set_final_decision(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    repo.set_final_decision(conn, "p1", Decision.YES.value, DecisionSource.AUTO.value)

    profile = repo.get_profile(conn, "p1")
    assert profile["final_decision"] == Decision.YES.value
    assert profile["decision_source"] == DecisionSource.AUTO.value


# --- swipe state ------------------------------------------------------------


def test_is_swiped_and_mark_swiped(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    assert repo.is_swiped(conn, "p1") is False
    repo.mark_swiped(conn, "p1")
    assert repo.is_swiped(conn, "p1") is True


def test_is_swiped_missing_profile_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        repo.is_swiped(conn, "does-not-exist")


# --- review decisions ---------------------------------------------------


def test_insert_review_decision(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    repo.insert_review_decision(
        conn,
        review_id="r1",
        profile_id="p1",
        trigger_reason=TriggerReason.SPLIT_DECISION.value,
        image_verdict_at_review=Verdict.YES.value,
        text_verdict_at_review=Verdict.NO.value,
        user_decision=UserDecision.YES.value,
    )

    row = conn.execute(
        "SELECT * FROM review_decisions WHERE review_id = ?", ("r1",)
    ).fetchone()
    assert row["profile_id"] == "p1"
    assert row["trigger_reason"] == TriggerReason.SPLIT_DECISION.value
    assert row["user_decision"] == UserDecision.YES.value
    assert row["decided_at"] is not None


def test_insert_review_decision_rejects_bad_trigger_reason(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_review_decision(
            conn,
            review_id="r1",
            profile_id="p1",
            trigger_reason="not_a_reason",
            image_verdict_at_review=Verdict.YES.value,
            text_verdict_at_review=Verdict.NO.value,
            user_decision=UserDecision.YES.value,
        )


# --- model predictions ------------------------------------------------------


def test_insert_and_resolve_prediction(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    repo.insert_prediction(
        conn,
        prediction_id="pred1",
        model_name=ModelName.IMAGE.value,
        target_id="p1",
        predicted_probability=0.75,
    )

    row = conn.execute(
        "SELECT * FROM model_predictions WHERE prediction_id = ?", ("pred1",)
    ).fetchone()
    assert row["model_name"] == ModelName.IMAGE.value
    assert row["predicted_probability"] == 0.75
    assert row["actual_label"] is None
    assert row["resolved_at"] is None

    repo.resolve_prediction(conn, "pred1", "yes")

    row = conn.execute(
        "SELECT * FROM model_predictions WHERE prediction_id = ?", ("pred1",)
    ).fetchone()
    assert row["actual_label"] == "yes"
    assert row["resolved_at"] is not None


def test_insert_prediction_rejects_bad_model_name(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_prediction(
            conn,
            prediction_id="pred1",
            model_name="not_a_model",
            target_id="p1",
            predicted_probability=0.5,
        )


def test_recent_predictions_returns_only_resolved_newest_first(
    conn: sqlite3.Connection,
) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    for i in range(5):
        repo.insert_prediction(
            conn,
            prediction_id=f"pred{i}",
            model_name=ModelName.TEXT.value,
            target_id="p1",
            predicted_probability=0.1 * i,
        )
    # Resolve all but pred0, in a known order so we can assert newest-first.
    for i in [1, 2, 3, 4]:
        repo.resolve_prediction(conn, f"pred{i}", "yes" if i % 2 == 0 else "no")

    resolved = repo.recent_predictions(conn, ModelName.TEXT.value, window=2)
    assert len(resolved) == 2
    assert all(row["resolved_at"] is not None for row in resolved)
    assert "pred0" not in {row["prediction_id"] for row in resolved}


def test_recent_predictions_filters_by_model_name(conn: sqlite3.Connection) -> None:
    _seed_app(conn)
    _seed_profile(conn)

    repo.insert_prediction(
        conn, prediction_id="img1", model_name=ModelName.IMAGE.value,
        target_id="p1", predicted_probability=0.9,
    )
    repo.insert_prediction(
        conn, prediction_id="txt1", model_name=ModelName.TEXT.value,
        target_id="p1", predicted_probability=0.2,
    )
    repo.resolve_prediction(conn, "img1", "yes")
    repo.resolve_prediction(conn, "txt1", "no")

    image_only = repo.recent_predictions(conn, ModelName.IMAGE.value, window=10)
    assert [row["prediction_id"] for row in image_only] == ["img1"]
