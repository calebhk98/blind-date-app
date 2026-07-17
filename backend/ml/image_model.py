"""Image model: frozen encoder + trainable head over per-photo embeddings
(design doc §8, §8.1).

``predict_proba(item)`` encodes a raw photo (path/PIL.Image/whatever the
injected encoder accepts) and returns P(yes). Cold-start handling (return
``CONFIG.model.cold_start_probability`` until enough labelled data has been
seen) lives entirely in ``ml/_head.py`` -- this module never special-cases
"untrained" itself.

``train()`` takes pre-computed embeddings (not raw items) plus PhotoLabel
labels, per design doc §8.1: ``not_relevant`` photos are never valid
training signal (they mean "no photo of a person to judge", not a yes/no
preference) and are excluded here before anything reaches the head.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from backend.domain.enums import PhotoLabel
from backend.ml._head import NO_LABEL, TrainableHead, YES_LABEL
from backend.ml.embeddings import Encoder
from backend.ml.embeddings.image_encoder import OpenClipImageEncoder

_LABEL_TO_INT = {PhotoLabel.YES: YES_LABEL, PhotoLabel.NO: NO_LABEL}


class ImageModel:
    """Predicts P(yes) for a single photo."""

    def __init__(self, encoder: Encoder | None = None) -> None:
        # Real encoder is lazy-heavy-import (torch/open_clip) -- constructing
        # it here does NOT import torch; only encoder.encode() does.
        self.encoder: Encoder = encoder if encoder is not None else OpenClipImageEncoder()
        self._head = TrainableHead()

    @property
    def is_trained(self) -> bool:
        return self._head.is_trained

    def predict_proba(self, item: object) -> float:
        """P(yes) for a raw photo item, encoded via ``self.encoder``."""
        embedding = self.encoder.encode(item)
        return self._head.predict_proba(embedding)

    def train(self, embeddings: np.ndarray, labels: Sequence[PhotoLabel]) -> None:
        """Fit the head on pre-computed embeddings + PhotoLabel labels.

        ``PhotoLabel.NOT_RELEVANT`` rows are excluded before fitting (§8.1) --
        this is the single source of truth for that exclusion rule.
        """
        embeddings = np.asarray(embeddings)
        if len(labels) != embeddings.shape[0]:
            raise ValueError(
                f"embeddings/labels length mismatch: {embeddings.shape[0]} vs {len(labels)}"
            )
        keep_idx = [i for i, label in enumerate(labels) if label != PhotoLabel.NOT_RELEVANT]
        if not keep_idx:
            raise ValueError("no trainable (yes/no) examples after excluding not_relevant")
        filtered_labels = [labels[i] for i in keep_idx]
        for label in filtered_labels:
            if label not in _LABEL_TO_INT:
                raise ValueError(f"unexpected PhotoLabel for training: {label!r}")
        filtered_embeddings = embeddings[keep_idx]
        int_labels = np.array([_LABEL_TO_INT[label] for label in filtered_labels])
        self._head.train(filtered_embeddings, int_labels)
