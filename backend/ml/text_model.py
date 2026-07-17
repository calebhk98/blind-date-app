"""Text model: frozen encoder + trainable head over per-profile bio embeddings
(design doc §8, §8.1).

``predict_proba(item)`` encodes raw bio text (via the injected encoder) and
returns P(yes). Cold-start handling lives entirely in ``ml/_head.py`` -- this
module never special-cases "untrained" itself.

``train()`` takes pre-computed embeddings (not raw text) plus Verdict labels.
Only ``Verdict.YES``/``Verdict.NO`` are valid training signal; any
``Verdict.PENDING`` rows (not yet labelled) are excluded here, mirroring how
``image_model.py`` excludes ``PhotoLabel.NOT_RELEVANT``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from backend.domain.enums import Verdict
from backend.ml._head import NO_LABEL, TrainableHead, YES_LABEL
from backend.ml.embeddings import Encoder
from backend.ml.embeddings.text_encoder import SentenceTransformerTextEncoder

_LABEL_TO_INT = {Verdict.YES: YES_LABEL, Verdict.NO: NO_LABEL}


class TextModel:
    """Predicts P(yes) for a single profile's bio text."""

    def __init__(self, encoder: Encoder | None = None) -> None:
        # Real encoder is lazy-heavy-import (sentence-transformers) --
        # constructing it here does NOT import it; only encoder.encode() does.
        self.encoder: Encoder = encoder if encoder is not None else SentenceTransformerTextEncoder()
        self._head = TrainableHead()

    @property
    def is_trained(self) -> bool:
        return self._head.is_trained

    def predict_proba(self, item: object) -> float:
        """P(yes) for raw bio text, encoded via ``self.encoder``."""
        embedding = self.encoder.encode(item)
        return self._head.predict_proba(embedding)

    def train(self, embeddings: np.ndarray, labels: Sequence[Verdict]) -> None:
        """Fit the head on pre-computed embeddings + Verdict labels.

        ``Verdict.PENDING`` rows are excluded before fitting -- unlabelled
        data is never valid training signal.
        """
        embeddings = np.asarray(embeddings)
        if len(labels) != embeddings.shape[0]:
            raise ValueError(
                f"embeddings/labels length mismatch: {embeddings.shape[0]} vs {len(labels)}"
            )
        keep_idx = [i for i, label in enumerate(labels) if label != Verdict.PENDING]
        if not keep_idx:
            raise ValueError("no trainable (yes/no) examples after excluding pending")
        filtered_labels = [labels[i] for i in keep_idx]
        for label in filtered_labels:
            if label not in _LABEL_TO_INT:
                raise ValueError(f"unexpected Verdict for training: {label!r}")
        filtered_embeddings = embeddings[keep_idx]
        int_labels = np.array([_LABEL_TO_INT[label] for label in filtered_labels])
        self._head.train(filtered_embeddings, int_labels)
