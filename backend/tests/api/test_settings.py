"""FastAPI TestClient tests for /settings/hard-filter (design doc §7.4,
issue #21): GET returns CONFIG-seeded defaults before anything is saved, PUT
persists new criteria/toggle and GET reflects it, and a fetched profile's
``hard_filter_hit`` is computed from the currently-stored criteria (issue
#20's rule, wired through fetch_service).

Same TestClient-over-temp-DB pattern as test_api.py: real migrations, a
FakeAdapter, no Playwright/Appium/torch.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_db
from backend.api.main import app
from backend.config import CONFIG
from backend.db import repository
from backend.db.connection import connect
from backend.db.migrate import apply_migrations
from backend.domain.types import RawProfile
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


# -- GET defaults ------------------------------------------------------------


def test_get_hard_filter_returns_config_defaults_when_unset(client: TestClient) -> None:
    response = client.get("/settings/hard-filter")
    assert response.status_code == 200
    body = response.json()
    assert body["criteria"] == {
        "min_age": CONFIG.hard_filter.min_age,
        "max_age": CONFIG.hard_filter.max_age,
        "max_distance": CONFIG.hard_filter.max_distance,
        "blocked_keywords": list(CONFIG.hard_filter.blocked_keywords),
        "required_keywords": list(CONFIG.hard_filter.required_keywords),
    }
    assert body["enabled"] == CONFIG.hard_filter.enabled_by_default


# -- PUT persists / GET reflects ---------------------------------------------


def test_put_hard_filter_persists_and_get_reflects_it(client: TestClient) -> None:
    payload = {
        "criteria": {
            "min_age": 25,
            "max_age": 40,
            "max_distance": 50,
            "blocked_keywords": ["Married", " onlyfans "],
            "required_keywords": ["Vaccinated"],
        },
        "enabled": False,
    }

    put_response = client.put("/settings/hard-filter", json=payload)
    assert put_response.status_code == 200
    put_body = put_response.json()
    # Keywords are normalized (trimmed + lowered) on write.
    assert put_body["criteria"]["blocked_keywords"] == ["married", "onlyfans"]
    assert put_body["criteria"]["required_keywords"] == ["vaccinated"]
    assert put_body["criteria"]["min_age"] == 25
    assert put_body["criteria"]["max_age"] == 40
    assert put_body["criteria"]["max_distance"] == 50
    assert put_body["enabled"] is False

    get_response = client.get("/settings/hard-filter")
    assert get_response.status_code == 200
    assert get_response.json() == put_body


def test_put_hard_filter_rejects_wrong_type(client: TestClient) -> None:
    response = client.put(
        "/settings/hard-filter",
        json={"criteria": {"min_age": "not-a-number"}, "enabled": True},
    )
    assert response.status_code == 422


# -- draw reads the stored toggle when hard_filter is omitted ---------------


def test_draw_omitted_param_uses_stored_enabled_toggle(
    client: TestClient, conn: sqlite3.Connection
) -> None:
    repository.insert_profile(
        conn,
        profile_id="hf-profile",
        app_id=FAKE_APP_ID,
        external_id="ext-hf",
        bio_text="filtered",
        hard_filter_hit=True,
    )

    client.put(
        "/settings/hard-filter",
        json={"criteria": {}, "enabled": True},
    )
    assert client.get("/draw").json() is None  # stored toggle is on -> excluded

    client.put(
        "/settings/hard-filter",
        json={"criteria": {}, "enabled": False},
    )
    assert client.get("/draw").json() is not None  # stored toggle is off -> included

    # An explicit query param still overrides the stored toggle either way.
    assert client.get("/draw", params={"hard_filter": True}).json() is None


# -- fetch computes hard_filter_hit from stored criteria (issue #20 + #21) --


def test_fetched_profile_hard_filter_hit_uses_stored_criteria(
    client: TestClient, conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services import fetch_service

    monkeypatch.setenv("BDA_IMAGE_DIR", str(tmp_path / "images"))
    reset_fake_adapter()

    client.put(
        "/settings/hard-filter",
        json={
            "criteria": {
                "min_age": None,
                "max_age": None,
                "max_distance": None,
                "blocked_keywords": ["onlyfans"],
                "required_keywords": [],
            },
            "enabled": True,
        },
    )

    FakeAdapter.NEXT_PROFILES = [
        RawProfile(app_id=FAKE_APP_ID, external_id="clean", bio_text="hiking and coffee"),
        RawProfile(app_id=FAKE_APP_ID, external_id="blocked", bio_text="check out my onlyfans"),
    ]

    profile_ids = fetch_service.fetch_new_profiles(conn, FAKE_APP_ID)

    profiles = {pid: repository.get_profile(conn, pid) for pid in profile_ids}
    by_external_id = {p["external_id"]: p for p in profiles.values()}
    assert by_external_id["clean"]["hard_filter_hit"] == 0
    assert by_external_id["blocked"]["hard_filter_hit"] == 1
