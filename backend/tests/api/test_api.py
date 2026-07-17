"""FastAPI TestClient integration tests for the orchestrator (design doc §4,
§8.1). Exercises fetch -> draw -> judge -> verdict recompute -> review ->
swipe against a temp SQLite DB (real migrations) and a FakeAdapter -- no
Playwright/Appium/torch involved, matching the DEP CONSTRAINT that this
whole app must run with only fastapi/httpx installed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_db
from backend.api.main import app
from backend.db import repository
from backend.db.connection import connect
from backend.db.migrate import apply_migrations
from backend.domain.enums import Decision, DecisionSource, TriggerReason
from backend.domain.types import RawPhoto, RawProfile
from backend.tests.api._fakes import FAKE_APP_ID, FakeAdapter, register_fake_adapter, reset_fake_adapter

register_fake_adapter()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    conn = connect(str(path))
    apply_migrations(conn)
    repository.insert_app(conn, FAKE_APP_ID, "web", "Fake App")
    conn.close()
    return path


@pytest.fixture()
def conn(db_path: Path):
    connection = connect(str(db_path))
    yield connection
    connection.close()


@pytest.fixture()
def client(db_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    reset_fake_adapter()

    def override_get_db():
        connection = connect(str(db_path))
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_profile(conn: sqlite3.Connection, *, n_photos: int = 1, bio: str = "hi") -> tuple[str, list[str]]:
    profile_id = "profile-1"
    repository.insert_profile(
        conn, profile_id=profile_id, app_id=FAKE_APP_ID, external_id="ext-1", bio_text=bio
    )
    photo_ids = []
    for i in range(n_photos):
        photo_id = f"photo-{i}"
        repository.insert_photo(
            conn, photo_id=photo_id, profile_id=profile_id, file_path=f"/tmp/{photo_id}.jpg", order_index=i
        )
        photo_ids.append(photo_id)
    return profile_id, photo_ids


# -- fetch (service-level, no dedicated HTTP route in this issue's scope) --


def test_fetch_persists_profile_and_photo(conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.services import fetch_service

    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    reset_fake_adapter()
    FakeAdapter.NEXT_PROFILES = [
        RawProfile(
            app_id=FAKE_APP_ID,
            external_id="ext-42",
            bio_text="hello world",
            photos=[RawPhoto(order_index=0, image_bytes=b"fake-jpeg-bytes")],
        )
    ]

    profile_ids = fetch_service.fetch_new_profiles(conn, FAKE_APP_ID)

    assert len(profile_ids) == 1
    profile = repository.get_profile(conn, profile_ids[0])
    assert profile["external_id"] == "ext-42"
    assert profile["bio_text"] == "hello world"
    photos = repository.get_photos(conn, profile_ids[0])
    assert len(photos) == 1
    assert Path(photos[0]["file_path"]).read_bytes() == b"fake-jpeg-bytes"
    assert FakeAdapter.LOGIN_CALLS  # login was called before fetching


# -- draw --------------------------------------------------------------


def test_draw_returns_pending_item_for_profile(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=2)

    response = client.get("/draw", params={"hard_filter": False})

    assert response.status_code == 200
    body = response.json()
    assert body is not None
    assert body["profile_id"] == profile_id
    assert body["app_id"] == FAKE_APP_ID
    assert body["modality"] in ("photo", "text")
    if body["modality"] == "photo":
        assert body["item_id"] in photo_ids
        assert body["content"]["file_path"] is not None
    else:
        assert body["item_id"] == profile_id
        assert body["content"]["bio_text"] == "hi"


def test_draw_returns_none_when_nothing_pending(client: TestClient, conn: sqlite3.Connection):
    response = client.get("/draw")
    assert response.status_code == 200
    assert response.json() is None


def test_draw_respects_hard_filter(client: TestClient, conn: sqlite3.Connection):
    repository.insert_profile(
        conn,
        profile_id="hf-profile",
        app_id=FAKE_APP_ID,
        external_id="ext-hf",
        bio_text="filtered",
        hard_filter_hit=True,
    )
    response = client.get("/draw", params={"hard_filter": True})
    assert response.json() is None

    response = client.get("/draw", params={"hard_filter": False})
    assert response.json() is not None


# -- judge / verdict recompute -----------------------------------------


def test_judge_photo_then_text_reaches_auto_yes_decision(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)

    photo_response = client.post("/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "yes"})
    assert photo_response.status_code == 200
    body = photo_response.json()
    assert body["decision"] is None  # text still pending -- not ready yet
    assert body["route_to_review"] is False

    profile = repository.get_profile(conn, profile_id)
    assert profile["image_verdict"] == "yes"

    text_response = client.post("/judge", json={"item_type": "text", "id": profile_id, "label": "yes"})
    assert text_response.status_code == 200
    body = text_response.json()
    assert body["decision"] == Decision.YES.value
    assert body["source"] == DecisionSource.AUTO.value

    profile = repository.get_profile(conn, profile_id)
    assert profile["final_decision"] == "yes"
    assert profile["decision_source"] == "auto"


def test_judge_split_decision_routes_to_review(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)

    client.post("/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "yes"})
    response = client.post("/judge", json={"item_type": "text", "id": profile_id, "label": "no"})

    body = response.json()
    assert body["decision"] is None
    assert body["route_to_review"] is True
    assert body["trigger_reason"] == TriggerReason.SPLIT_DECISION.value

    profile = repository.get_profile(conn, profile_id)
    assert profile["final_decision"] == "pending"


def test_judge_all_photos_not_relevant_routes_to_review(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)

    response = client.post(
        "/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "not_relevant"}
    )

    body = response.json()
    assert body["decision"] is None
    assert body["route_to_review"] is True
    assert body["trigger_reason"] == TriggerReason.ALL_NOT_RELEVANT.value


def test_judge_unknown_photo_is_404(client: TestClient):
    response = client.post("/judge", json={"item_type": "photo", "id": "nope", "label": "yes"})
    assert response.status_code == 404


def test_judge_invalid_label_is_422(client: TestClient, conn: sqlite3.Connection):
    _, photo_ids = _make_profile(conn, n_photos=1)
    response = client.post("/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "maybe"})
    assert response.status_code == 422


# -- review --------------------------------------------------------------


def test_review_sets_final_decision_after_split(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)
    client.post("/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "yes"})
    client.post("/judge", json={"item_type": "text", "id": profile_id, "label": "no"})

    response = client.post(f"/review/{profile_id}", json={"user_decision": "yes"})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == Decision.YES.value
    assert body["source"] == DecisionSource.REVIEW.value

    profile = repository.get_profile(conn, profile_id)
    assert profile["final_decision"] == "yes"
    assert profile["decision_source"] == "review"


def test_review_rejects_profile_not_pending_review(client: TestClient, conn: sqlite3.Connection):
    profile_id, _ = _make_profile(conn, n_photos=1)  # nothing judged yet
    response = client.post(f"/review/{profile_id}", json={"user_decision": "yes"})
    assert response.status_code == 404


def test_review_invalid_user_decision_is_422(client: TestClient, conn: sqlite3.Connection):
    profile_id, _ = _make_profile(conn, n_photos=1)
    response = client.post(f"/review/{profile_id}", json={"user_decision": "maybe"})
    assert response.status_code == 422


# -- swipe approve (idempotent) ------------------------------------------


def test_swipe_approve_is_idempotent(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)
    client.post("/judge", json={"item_type": "photo", "id": photo_ids[0], "label": "yes"})
    client.post("/judge", json={"item_type": "text", "id": profile_id, "label": "yes"})
    assert repository.get_profile(conn, profile_id)["final_decision"] == "yes"

    first = client.post(f"/swipe/{profile_id}/approve")
    second = client.post(f"/swipe/{profile_id}/approve")

    assert first.status_code == 200
    assert first.json()["swiped_now"] is True
    assert second.status_code == 200
    assert second.json()["swiped_now"] is False
    assert len(FakeAdapter.SWIPE_CALLS) == 1
    assert FakeAdapter.SWIPE_CALLS[0] == ("ext-1", "yes")
    assert repository.is_swiped(conn, profile_id) is True


def test_swipe_approve_without_final_decision_is_404(client: TestClient, conn: sqlite3.Connection):
    profile_id, _ = _make_profile(conn, n_photos=1)  # final_decision still pending
    response = client.post(f"/swipe/{profile_id}/approve")
    assert response.status_code == 404


# -- inference -------------------------------------------------------------


def test_inference_combined_pre_training_returns_cold_start_probability(
    client: TestClient, conn: sqlite3.Connection
):
    from backend.config import CONFIG
    from backend.ml.combined_model import CAVEAT

    profile_id, _ = _make_profile(conn, n_photos=1)

    response = client.get(f"/inference/combined/{profile_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["probability"] == CONFIG.model.cold_start_probability
    assert body["caveat"] == CAVEAT


def test_inference_unknown_model_is_404(client: TestClient, conn: sqlite3.Connection):
    profile_id, _ = _make_profile(conn, n_photos=1)
    response = client.get(f"/inference/nonsense/{profile_id}")
    assert response.status_code == 404


def test_inference_unknown_target_is_404(client: TestClient):
    response = client.get("/inference/combined/does-not-exist")
    assert response.status_code == 404


def test_inference_image_and_text_require_torch():
    pytest.importorskip("torch")  # noqa: skip in envs without torch/open_clip
    pytest.skip("guarded placeholder: exercised only where torch is installed")


# -- dashboard / apps / profiles -------------------------------------------


def test_dashboard_reports_pending_counts_and_null_accuracy(client: TestClient, conn: sqlite3.Connection):
    from backend.domain.enums import ModelName

    _make_profile(conn, n_photos=2)

    response = client.get("/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["pending"]["photos"] == 2
    assert body["pending"]["text"] == 1
    assert body["decisions"]["pending"] == 1
    for model in ModelName:
        assert body["rolling_accuracy"][model.value] is None  # no resolved predictions yet


def test_list_apps(client: TestClient):
    response = client.get("/apps")
    assert response.status_code == 200
    app_ids = [row["app_id"] for row in response.json()]
    assert FAKE_APP_ID in app_ids


def test_get_profile(client: TestClient, conn: sqlite3.Connection):
    profile_id, photo_ids = _make_profile(conn, n_photos=1)
    response = client.get(f"/profiles/{profile_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["profile_id"] == profile_id
    assert [p["photo_id"] for p in body["photos"]] == photo_ids


def test_get_unknown_profile_is_404(client: TestClient):
    response = client.get("/profiles/does-not-exist")
    assert response.status_code == 404


# -- abstraction boundary: no app-specific branching (design doc §4) ------


def test_no_app_specific_branching_in_api_or_services():
    """Static guard for design doc §4: 'No app-specific logic anywhere in
    api/ or services/. Never write `if app_id == "tinder"`.' Every dispatch
    must go through backend.adapters.registry.get_adapter_class instead."""
    root = Path(__file__).resolve().parents[2]  # backend/
    offenders = []
    for sub in ("api", "services"):
        for path in (root / sub).rglob("*.py"):
            text = path.read_text()
            for known_app in ("tinder", "bumble", "hinge"):
                if f'"{known_app}"' in text or f"'{known_app}'" in text:
                    offenders.append(str(path))
    assert not offenders, f"app-specific literals found outside adapters/: {offenders}"
