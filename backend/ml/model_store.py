"""Persistence for trained model heads (issue #19, design doc §8/§8.1).

``ml/training.py::retrain_all`` trains ``TrainableHead`` instances but, prior
to this module, never wrote them anywhere -- every inference request built a
fresh (untrained) model and therefore always returned the cold-start
probability. This module is the single place that pickles/unpickles a
model's trainable head to/from ``CONFIG.storage.models_dir``.

Only the trainable head is ever persisted here (a fitted
``backend.ml._head.TrainableHead``, which wraps a plain sklearn
``LogisticRegression`` -- both pickle cleanly with the stdlib ``pickle``
module, so this file deliberately does NOT add joblib as a dependency).
Encoders are frozen/stateless and reconstructed separately by
``image_model.py``/``text_model.py`` (real encoders lazy-import
torch/sentence-transformers; persisting them here would either pull those
deps in at load time or pickle something heavier than a feature spec), so
callers must never pass an encoder or raw model wrapper (``ImageModel`` etc.)
into ``save_model`` -- only the head.

Versioning: every ``save_model`` call writes a new timestamped snapshot
(``<name>-<timestamp>.pkl``) and overwrites the ``<name>-latest.pkl``
pointer file with the same bytes (a real copy, not a symlink -- this app
already treats ``CONFIG.storage`` paths as plain files/dirs everywhere else).
Only the last ``_KEEP_LAST_N`` timestamped snapshots are retained; older
ones are pruned on every save.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import CONFIG

# How many timestamped versions of a given model name to keep on disk before
# pruning the oldest. Not exposed via backend.config.CONFIG: design doc §4
# reserves that module for deployment-tunable *behaviour*; this is an
# internal implementation detail of the store's own pruning policy.
_KEEP_LAST_N = 5

_LATEST_STEM_SUFFIX = "latest"
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S%f"


@dataclass(frozen=True)
class ModelVersion:
    """One persisted timestamped snapshot of a named model on disk."""

    name: str
    path: Path
    timestamp: str


def _models_dir() -> Path:
    """CONFIG.storage.models_dir, created on demand.

    Read fresh on every call (not cached) so tests can monkeypatch
    ``BDA_MODELS_DIR`` per-test via ``CONFIG.storage.models_dir`` (itself a
    property re-reading the env var each time -- see backend/config.py).
    """
    directory = CONFIG.storage.models_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _latest_path(name: str) -> Path:
    return _models_dir() / f"{name}-{_LATEST_STEM_SUFFIX}.pkl"


def _versioned_path(name: str, timestamp: str) -> Path:
    return _models_dir() / f"{name}-{timestamp}.pkl"


def save_model(name: str, model: object) -> Path:
    """Persist ``model`` (a fitted head, e.g. a ``TrainableHead``) under
    ``name`` (e.g. ``"image"``/``"text"``/``"combined"`` -- see
    ``backend.domain.enums.ModelName``).

    Writes a new timestamped snapshot, refreshes the ``<name>-latest.pkl``
    pointer to the same bytes, then prunes snapshots beyond
    ``_KEEP_LAST_N``. Returns the path to the timestamped snapshot written.
    Fails loud (design doc §4): an empty ``name`` or an unpicklable
    ``model`` raises rather than silently no-op-ing.
    """
    if not name:
        raise ValueError("model name must be a non-empty string")
    payload = pickle.dumps(model)

    timestamp = datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)
    versioned_path = _versioned_path(name, timestamp)
    # Extremely unlikely (sub-microsecond) collision guard: two saves in the
    # same process landing on the identical microsecond would otherwise
    # silently clobber each other's snapshot rather than keeping both.
    disambiguator = 0
    while versioned_path.exists():
        disambiguator += 1
        versioned_path = _versioned_path(name, f"{timestamp}-{disambiguator}")

    versioned_path.write_bytes(payload)
    _latest_path(name).write_bytes(payload)
    _prune(name)
    return versioned_path


def load_latest(name: str) -> Any:
    """Return the most recently saved model for ``name``, or ``None`` if
    nothing has ever been saved for it (fresh deployment / never trained --
    callers treat ``None`` as "fall back to a cold-start instance").

    Return type is ``Any`` (not ``object``) because the unpickled value is a
    concrete head type that callers assign to their typed ``_head`` slot."""
    latest_path = _latest_path(name)
    if not latest_path.exists():
        return None
    with latest_path.open("rb") as fh:
        return pickle.load(fh)


def list_versions(name: str) -> list[ModelVersion]:
    """All timestamped snapshots for ``name`` on disk, oldest first. Excludes
    the ``<name>-latest.pkl`` pointer (that's a duplicate of the newest
    snapshot's bytes, not a version of its own)."""
    prefix = f"{name}-"
    versions: list[ModelVersion] = []
    for path in _models_dir().glob(f"{prefix}*.pkl"):
        suffix = path.stem[len(prefix) :]
        if suffix == _LATEST_STEM_SUFFIX:
            continue
        versions.append(ModelVersion(name=name, path=path, timestamp=suffix))
    versions.sort(key=lambda version: version.timestamp)
    return versions


def _prune(name: str) -> None:
    """Delete the oldest timestamped snapshots for ``name`` beyond
    ``_KEEP_LAST_N``. The ``latest`` pointer is never pruned (it always
    mirrors the newest snapshot, which is never one of the pruned ones)."""
    versions = list_versions(name)
    excess = len(versions) - _KEEP_LAST_N
    if excess <= 0:
        return
    for version in versions[:excess]:
        version.path.unlink(missing_ok=True)
