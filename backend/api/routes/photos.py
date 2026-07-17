"""GET /photos/{photo_id}/image: serve a locally-stored photo's bytes.

Photos live on the local filesystem with their path recorded in the DB
(design doc §5). The review UI needs the actual bytes over HTTP to render the
blind-draw photo, so this route resolves ``photos.file_path`` for a known
``photo_id`` and streams it back. It only ever serves files that (a) are
recorded in our own DB and (b) resolve inside ``CONFIG.storage.image_dir`` --
so a crafted path can never escape the image directory (fail loud on anything
outside it).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.deps import get_db
from backend.config import CONFIG

router = APIRouter(prefix="/photos", tags=["photos"])


@router.get("/{photo_id}/image")
def get_photo_image(
    photo_id: str, conn: sqlite3.Connection = Depends(get_db)
) -> FileResponse:
    row = conn.execute(
        "SELECT file_path FROM photos WHERE photo_id = ?", (photo_id,)
    ).fetchone()
    if row is None or not row["file_path"]:
        raise HTTPException(status_code=404, detail=f"unknown photo id: {photo_id}")

    path = _safe_image_path(row["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo file is missing on disk")
    return FileResponse(path)


def _safe_image_path(file_path: str) -> Path:
    """Resolve ``file_path`` and refuse anything outside the image dir."""
    image_root = CONFIG.storage.image_dir.resolve()
    resolved = Path(file_path).resolve()
    if not resolved.is_relative_to(image_root):
        raise HTTPException(status_code=403, detail="photo path is outside the image dir")
    return resolved
