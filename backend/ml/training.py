"""On-demand retraining entry point (design doc §8, §8.1, §8.2).

Pulls labelled data straight out of SQLite and retrains the image, text, and
combined models. Guards against too-little data per model: a model with
fewer than ``CONFIG.model.min_training_examples`` labelled examples is
skipped and reported as not-trained rather than raising -- ``ml/_head.py``
itself fails loud on that same condition, but here it's an expected, routine
outcome (a fresh deployment simply hasn't collected enough labels yet), not a
bug, so we check first and skip quietly instead of relying on catching the
head's exception.

NOTE (scope): this module does not persist trained models anywhere -- no
model store/registry exists yet in this codebase (``backend.config`` has no
model directory). ``retrain_all`` reports whether each model *would* train
successfully given current data volumes; wiring persisted/singleton model
instances into the prediction path is a separate, not-yet-scoped piece of
work.
"""

from __future__ import annotations

import sqlite3
import warnings

import numpy as np

from backend.config import CONFIG
from backend.domain.enums import ModelName, PhotoLabel, UserDecision, Verdict
from backend.ml.combined_model import CombinedModel
from backend.ml.image_model import ImageModel
from backend.ml.text_model import TextModel


def _retrain_image(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT file_path, label FROM photos WHERE label IN ('yes', 'no')"
    ).fetchall()
    if len(rows) < CONFIG.model.min_training_examples:
        return False
    model = ImageModel()
    labels = [PhotoLabel(row["label"]) for row in rows]
    embeddings = np.stack([model.encoder.encode(row["file_path"]) for row in rows])
    try:
        model.train(embeddings, labels)
    except ValueError as exc:
        warnings.warn(f"image model retrain skipped: {exc}", stacklevel=2)
        return False
    return model.is_trained


def _retrain_text(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT bio_text, text_verdict FROM profiles "
        "WHERE text_verdict IN ('yes', 'no') AND bio_text IS NOT NULL"
    ).fetchall()
    if len(rows) < CONFIG.model.min_training_examples:
        return False
    model = TextModel()
    labels = [Verdict(row["text_verdict"]) for row in rows]
    embeddings = np.stack([model.encoder.encode(row["bio_text"]) for row in rows])
    try:
        model.train(embeddings, labels)
    except ValueError as exc:
        warnings.warn(f"text model retrain skipped: {exc}", stacklevel=2)
        return False
    return model.is_trained


def _retrain_combined(conn: sqlite3.Connection) -> bool:
    # review_decisions rows exist ONLY for profiles routed to full-profile
    # review (design doc §6.3) -- the table is already review-path-only by
    # construction, so no extra filtering is needed here (see combined_model
    # module docstring / CAVEAT for what that implies about this model).
    rows = conn.execute(
        "SELECT image_verdict_at_review, text_verdict_at_review, user_decision "
        "FROM review_decisions"
    ).fetchall()
    if len(rows) < CONFIG.model.min_training_examples:
        return False
    model = CombinedModel()
    features = np.stack(
        [
            CombinedModel.build_features(
                Verdict(row["image_verdict_at_review"])
                if row["image_verdict_at_review"]
                else Verdict.PENDING,
                Verdict(row["text_verdict_at_review"])
                if row["text_verdict_at_review"]
                else Verdict.PENDING,
            )
            for row in rows
        ]
    )
    labels = [UserDecision(row["user_decision"]) for row in rows]
    try:
        model.train(features, labels)
    except ValueError as exc:
        warnings.warn(f"combined model retrain skipped: {exc}", stacklevel=2)
        return False
    return model.is_trained


def retrain_all(conn: sqlite3.Connection) -> dict[str, bool]:
    """Retrain the image, text, and combined models from current DB state.

    Returns a ``{model_name: trained}`` dict (keys = ``ModelName`` values) so
    callers can report which models actually trained vs. were skipped for
    lack of data.
    """
    return {
        ModelName.IMAGE.value: _retrain_image(conn),
        ModelName.TEXT.value: _retrain_text(conn),
        ModelName.COMBINED.value: _retrain_combined(conn),
    }
