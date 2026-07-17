"""Tests for the photo image-serving route (GET /photos/{id}/image)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_db
from backend.api.main import app
from backend.config import CONFIG
from backend.db import repository
from backend.db.connection import connect
from backend.db.migrate import apply_migrations


@pytest.fixture()
def image_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "images"
    d.mkdir()
    monkeypatch.setenv("BDA_IMAGE_DIR", str(d))
    return d


@pytest.fixture()
def client(tmp_path: Path, image_dir: Path) -> Iterator[TestClient]:
    db_path = tmp_path / "test.db"
    seed = connect(str(db_path))
    apply_migrations(seed)
    repository.insert_app(seed, "tinder", "web", "Tinder")
    repository.insert_profile(
        seed, profile_id="p1", app_id="tinder", external_id="x1", bio_text="hi"
    )
    seed.commit()
    seed.close()

    def override_get_db() -> Iterator[object]:
        connection = connect(str(db_path))
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _insert_photo(tmp_path: Path, photo_id: str, file_path: str, order_index: int) -> None:
    conn = connect(str(tmp_path / "test.db"))
    repository.insert_photo(
        conn, photo_id=photo_id, profile_id="p1", file_path=file_path, order_index=order_index
    )
    conn.commit()
    conn.close()


def test_unknown_photo_id_returns_404(client: TestClient) -> None:
    assert client.get("/photos/nope/image").status_code == 404


def test_serves_a_file_inside_the_image_dir(
    client: TestClient, tmp_path: Path, image_dir: Path
) -> None:
    img = image_dir / "photo-0.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")  # tiny fake jpeg
    _insert_photo(tmp_path, "ph1", str(img), 0)
    resp = client.get("/photos/ph1/image")
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8\xff\xd9"


def test_rejects_path_outside_image_dir(
    client: TestClient, tmp_path: Path
) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    _insert_photo(tmp_path, "ph2", str(outside), 1)
    assert client.get("/photos/ph2/image").status_code == 403


def test_cors_configured() -> None:
    assert any("localhost:3000" in o for o in CONFIG.api.cors_origins)
