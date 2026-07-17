"""GET /inference/{model}/{target_id}: P(yes) from a trained (or cold-start)
model (design doc §8.1). Cold-start handling lives entirely in
``backend.ml._head.TrainableHead`` -- this route never special-cases
"untrained" itself, so the UI consumes an identical shape either way.

``target_id`` semantics differ per model, matching what each model actually
predicts over (see ``backend/ml/training.py``, which sources training rows
the same way): a photo_id for "image", a profile_id for "text"/"combined".

CONTRACT NOTE: the issue's stated contract is
``predict_proba(item) -> float`` for all three models, but
``backend.ml.combined_model.CombinedModel.predict_proba`` actually takes
``(image_verdict, text_verdict, extra_embedding=None)`` -- it reconciles two
per-modality verdicts, it does not encode a single opaque "item". This route
special-cases the combined model to match its real signature.

Heavy ML deps (torch/open_clip/sentence-transformers) are only pulled in by
``ImageModel``/``TextModel`` when their encoder actually runs, and only
imported here inside the handler -- never at module import time -- so this
router imports fine with only fastapi installed.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_db
from backend.domain.enums import ModelName, Verdict

router = APIRouter(prefix="/inference", tags=["inference"])


@router.get("/{model}/{target_id}")
def infer(model: str, target_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    try:
        model_name = ModelName(model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"unknown model: {model}") from exc

    if model_name is ModelName.IMAGE:
        return {"probability": _predict_image(conn, target_id)}
    if model_name is ModelName.TEXT:
        return {"probability": _predict_text(conn, target_id)}

    probability, caveat = _predict_combined(conn, target_id)
    return {"probability": probability, "caveat": caveat}


def _predict_image(conn: sqlite3.Connection, photo_id: str) -> float:
    from backend.ml.image_model import ImageModel

    # No repository helper fetches a single photo by photo_id alone (only
    # get_photos(conn, profile_id) exists); a direct read against the known
    # photos schema is the pragmatic choice for this one lookup.
    row = conn.execute("SELECT file_path FROM photos WHERE photo_id = ?", (photo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown photo id: {photo_id}")
    return ImageModel().predict_proba(row["file_path"])


def _predict_text(conn: sqlite3.Connection, profile_id: str) -> float:
    from backend.db import repository
    from backend.ml.text_model import TextModel

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"unknown profile_id: {profile_id}")
    return TextModel().predict_proba(profile["bio_text"])


def _predict_combined(conn: sqlite3.Connection, profile_id: str) -> tuple[float, str]:
    from backend.db import repository
    from backend.ml.combined_model import CAVEAT, CombinedModel

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"unknown profile_id: {profile_id}")
    image_verdict = Verdict(profile["image_verdict"])
    text_verdict = Verdict(profile["text_verdict"])
    probability = CombinedModel().predict_proba(image_verdict, text_verdict)
    return probability, CAVEAT
