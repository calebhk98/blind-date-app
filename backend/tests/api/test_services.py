"""Direct (non-HTTP) tests for backend/services/*.py against a temp SQLite DB
and the shared FakeAdapter (see _fakes.py). Complements test_api.py, which
covers the same behaviour through the FastAPI routes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.db import repository
from backend.db.connection import connect
from backend.db.migrate import apply_migrations
from backend.domain.enums import (
    Decision,
    DecisionSource,
    PhotoLabel,
    TriggerReason,
    UserDecision,
    Verdict,
)
from backend.domain.types import RawPhoto, RawProfile
from backend.tests.api._fakes import FAKE_APP_ID, FakeAdapter, register_fake_adapter, reset_fake_adapter

register_fake_adapter()


@pytest.fixture()
def conn(tmp_path: Path):
    connection = connect(str(tmp_path / "svc.db"))
    apply_migrations(connection)
    repository.insert_app(connection, FAKE_APP_ID, "web", "Fake App")
    reset_fake_adapter()
    yield connection
    connection.close()


def _profile(conn: sqlite3.Connection, profile_id: str = "p1", n_photos: int = 1) -> list[str]:
    repository.insert_profile(
        conn, profile_id=profile_id, app_id=FAKE_APP_ID, external_id=f"ext-{profile_id}", bio_text="bio"
    )
    photo_ids = []
    for i in range(n_photos):
        photo_id = f"{profile_id}-photo-{i}"
        repository.insert_photo(
            conn, photo_id=photo_id, profile_id=profile_id, file_path=f"/tmp/{photo_id}.jpg", order_index=i
        )
        photo_ids.append(photo_id)
    return photo_ids


# -- verdict_engine ---------------------------------------------------------


def test_on_photo_judged_recomputes_image_verdict_via_pure_rule(conn: sqlite3.Connection):
    from backend.logic.verdict import aggregate_image_verdict
    from backend.services import verdict_engine

    photo_ids = _profile(conn, n_photos=2)
    verdict_engine.on_photo_judged(conn, "p1", photo_ids[0], PhotoLabel.YES)
    verdict_engine.on_photo_judged(conn, "p1", photo_ids[1], PhotoLabel.NO)

    profile = repository.get_profile(conn, "p1")
    labels = [PhotoLabel(row["label"]) for row in repository.get_photos(conn, "p1")]
    expected = aggregate_image_verdict(labels)
    assert profile["image_verdict"] == expected.verdict.value


def test_on_text_judged_rejects_non_decided_verdict(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    _profile(conn)
    with pytest.raises(ValueError):
        verdict_engine.on_text_judged(conn, "p1", Verdict.PENDING)


def test_evaluate_profile_unknown_raises(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    with pytest.raises(ValueError):
        verdict_engine.evaluate_profile(conn, "does-not-exist")


def test_both_no_auto_decision(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    photo_ids = _profile(conn)
    verdict_engine.on_photo_judged(conn, "p1", photo_ids[0], PhotoLabel.NO)
    result = verdict_engine.on_text_judged(conn, "p1", Verdict.NO)

    assert result.decision == Decision.NO
    assert result.source == DecisionSource.AUTO
    assert repository.get_profile(conn, "p1")["final_decision"] == "no"


def test_hard_filter_hit_forces_no_even_with_yes_verdicts(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    repository.insert_profile(
        conn,
        profile_id="hf",
        app_id=FAKE_APP_ID,
        external_id="ext-hf",
        bio_text="bio",
        hard_filter_hit=True,
    )
    photo_id = "hf-photo-0"
    repository.insert_photo(conn, photo_id=photo_id, profile_id="hf", file_path="/tmp/x.jpg", order_index=0)

    verdict_engine.on_photo_judged(conn, "hf", photo_id, PhotoLabel.YES)
    result = verdict_engine.on_text_judged(conn, "hf", Verdict.YES)

    assert result.decision == Decision.NO
    assert result.source == DecisionSource.AUTO


def test_record_review_decision_requires_pending_review(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    _profile(conn)
    with pytest.raises(ValueError):
        verdict_engine.record_review_decision(conn, "p1", UserDecision.YES)


def test_record_review_decision_writes_review_row(conn: sqlite3.Connection):
    from backend.services import verdict_engine

    photo_ids = _profile(conn)
    verdict_engine.on_photo_judged(conn, "p1", photo_ids[0], PhotoLabel.YES)
    verdict_engine.on_text_judged(conn, "p1", Verdict.NO)  # split -> route to review

    result = verdict_engine.record_review_decision(conn, "p1", UserDecision.NO)

    assert result.decision == Decision.NO
    assert result.source == DecisionSource.REVIEW
    row = conn.execute("SELECT * FROM review_decisions WHERE profile_id = 'p1'").fetchone()
    assert row is not None
    assert row["trigger_reason"] == TriggerReason.SPLIT_DECISION.value
    assert row["user_decision"] == "no"


# -- swipe_service ------------------------------------------------------


def test_swipe_service_approve_calls_adapter_once(conn: sqlite3.Connection):
    from backend.services import swipe_service, verdict_engine

    photo_ids = _profile(conn)
    verdict_engine.on_photo_judged(conn, "p1", photo_ids[0], PhotoLabel.YES)
    verdict_engine.on_text_judged(conn, "p1", Verdict.YES)

    first = swipe_service.approve(conn, "p1")
    second = swipe_service.approve(conn, "p1")

    assert first is True
    assert second is False
    assert len(FakeAdapter.SWIPE_CALLS) == 1
    assert FakeAdapter.SWIPE_CALLS[0] == ("ext-p1", "yes")


def test_swipe_service_rejects_pending_decision(conn: sqlite3.Connection):
    from backend.services import swipe_service

    _profile(conn)
    with pytest.raises(ValueError):
        swipe_service.approve(conn, "p1")


def test_swipe_service_unknown_profile_raises(conn: sqlite3.Connection):
    from backend.services import swipe_service

    with pytest.raises(ValueError):
        swipe_service.approve(conn, "nope")


# -- fetch_service ------------------------------------------------------


def test_fetch_service_persists_multiple_photos(conn: sqlite3.Connection, tmp_path: Path, monkeypatch):
    from backend.services import fetch_service

    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    FakeAdapter.NEXT_PROFILES = [
        RawProfile(
            app_id=FAKE_APP_ID,
            external_id="ext-multi",
            bio_text="multi photo bio",
            photos=[
                RawPhoto(order_index=0, image_bytes=b"one"),
                RawPhoto(order_index=1, image_bytes=b"two"),
            ],
        )
    ]

    [profile_id] = fetch_service.fetch_new_profiles(conn, FAKE_APP_ID)

    photos = repository.get_photos(conn, profile_id)
    assert len(photos) == 2
    assert {Path(p["file_path"]).read_bytes() for p in photos} == {b"one", b"two"}


def test_fetch_service_respects_limit(conn: sqlite3.Connection, tmp_path: Path, monkeypatch):
    from backend.services import fetch_service

    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    FakeAdapter.NEXT_PROFILES = [
        RawProfile(app_id=FAKE_APP_ID, external_id=f"ext-{i}", bio_text="bio", photos=[]) for i in range(5)
    ]

    profile_ids = fetch_service.fetch_new_profiles(conn, FAKE_APP_ID, limit=2)

    assert len(profile_ids) == 2


def test_fetch_service_raises_on_photo_with_no_source(conn: sqlite3.Connection, tmp_path: Path, monkeypatch):
    from backend.services import fetch_service

    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    FakeAdapter.NEXT_PROFILES = [
        RawProfile(
            app_id=FAKE_APP_ID,
            external_id="ext-bad",
            bio_text="bio",
            photos=[RawPhoto(order_index=0)],  # neither url nor image_bytes
        )
    ]

    with pytest.raises(ValueError):
        fetch_service.fetch_new_profiles(conn, FAKE_APP_ID)
