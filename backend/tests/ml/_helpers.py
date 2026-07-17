"""Test-only helpers shared across backend/tests/ml/*.

Not part of the public ``backend.ml`` package -- ``image_model.py`` /
``text_model.py`` depend only on the ``Encoder`` protocol (see
``backend/ml/embeddings/__init__.py``), never on this module, so nothing in
here ever needs torch/open_clip/sentence-transformers.
"""

from __future__ import annotations

import hashlib

import numpy as np

from backend.domain.enums import PhotoLabel, Verdict


class FakeEncoder:
    """Deterministic fake encoder: same input -> same vector, always, no I/O.

    By default, each distinct input hashes (via sha256, not the randomized
    builtin ``hash()``) to a stable pseudo-random vector -- enough to prove
    the encode/predict wiring and determinism. Tests that need explicit
    control over embedding geometry (e.g. a linearly-separable synthetic
    dataset) can set exact vectors via ``overrides``.
    """

    def __init__(self, dim: int = 8, overrides: dict[object, np.ndarray] | None = None) -> None:
        self.dim = dim
        self.overrides: dict[object, np.ndarray] = overrides or {}

    def encode(self, item: object) -> np.ndarray:
        if item in self.overrides:
            return np.asarray(self.overrides[item], dtype=np.float64)
        digest = hashlib.sha256(repr(item).encode("utf-8")).digest()
        repeated = (digest * ((self.dim // len(digest)) + 1))[: self.dim]
        return np.array([b / 255.0 for b in repeated], dtype=np.float64)


def make_separable_dataset(
    n_per_class: int,
    yes_prefix: str,
    no_prefix: str,
    photo_label: bool,
    dim: int = 8,
    seed: int = 0,
) -> tuple[FakeEncoder, list[str], list]:
    """Build a FakeEncoder plus a matching (items, labels) training set that
    is linearly separable by construction: "yes" items cluster around +5 in
    every dimension, "no" items cluster around -5, with small deterministic
    Gaussian noise (fixed seed => fully reproducible).

    Also seeds two held-out keys, ``f"{yes_prefix}_holdout"`` and
    ``f"{no_prefix}_holdout"`` (NOT included in the returned items/labels),
    for post-train predict_proba assertions.
    """
    rng = np.random.default_rng(seed)
    overrides: dict[object, np.ndarray] = {}
    items: list[str] = []
    labels: list = []

    yes_label = PhotoLabel.YES if photo_label else Verdict.YES
    no_label = PhotoLabel.NO if photo_label else Verdict.NO

    for i in range(n_per_class):
        key = f"{yes_prefix}_{i}"
        overrides[key] = rng.normal(loc=5.0, scale=0.25, size=dim)
        items.append(key)
        labels.append(yes_label)
    for i in range(n_per_class):
        key = f"{no_prefix}_{i}"
        overrides[key] = rng.normal(loc=-5.0, scale=0.25, size=dim)
        items.append(key)
        labels.append(no_label)

    overrides[f"{yes_prefix}_holdout"] = rng.normal(loc=5.0, scale=0.25, size=dim)
    overrides[f"{no_prefix}_holdout"] = rng.normal(loc=-5.0, scale=0.25, size=dim)

    encoder = FakeEncoder(dim=dim, overrides=overrides)
    return encoder, items, labels
