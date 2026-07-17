"""Shared trainable-head logic for image_model.py / text_model.py / combined_model.py
(design doc §8, §8.1).

Single source of truth for the cold-start rule: a head that has not yet been
fit on at least ``CONFIG.model.min_training_examples`` labelled examples
returns ``CONFIG.model.cold_start_probability`` instead of a real prediction.
Cold-start handling lives here and ONLY here -- callers (models, API, UI)
never special-case "untrained" themselves.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from backend.config import CONFIG

# The "yes" class label used consistently across every head (0 = no, 1 = yes).
YES_LABEL = 1
NO_LABEL = 0


class TrainableHead:
    """A LogisticRegression classifier over frozen embeddings/features.

    Operates on plain numeric features and integer 0/1 labels -- callers
    (image_model.py, text_model.py, combined_model.py) own translating their
    domain enums (PhotoLabel, Verdict, UserDecision) into that shape, since
    that translation differs per model.
    """

    def __init__(self) -> None:
        self._clf: LogisticRegression | None = None
        self._n_examples_seen = 0

    @property
    def is_trained(self) -> bool:
        """True once fit on at least min_training_examples labelled rows."""
        return self._clf is not None and self._n_examples_seen >= CONFIG.model.min_training_examples

    def predict_proba(self, features: np.ndarray) -> float:
        """P(yes) for a single feature vector. Cold start returns the config
        default rather than a fitted-but-meaningless probability."""
        if not self.is_trained:
            return CONFIG.model.cold_start_probability
        assert self._clf is not None
        row = np.asarray(features, dtype=np.float64).reshape(1, -1)
        proba = self._clf.predict_proba(row)[0]
        classes = list(self._clf.classes_)
        return float(proba[classes.index(YES_LABEL)])

    def train(self, features: np.ndarray, labels: np.ndarray) -> None:
        """Fit on a full batch of (features, 0/1 labels).

        Fails loud (design doc §4) on too-little or single-class data rather
        than silently fitting a degenerate model; callers that want a
        graceful skip (e.g. ml/training.py) should check volume themselves
        before calling.
        """
        features = np.asarray(features, dtype=np.float64)
        labels = np.asarray(labels)
        if features.shape[0] != labels.shape[0]:
            raise ValueError(
                f"features/labels length mismatch: {features.shape[0]} vs {labels.shape[0]}"
            )
        if features.shape[0] < CONFIG.model.min_training_examples:
            raise ValueError(
                "need at least CONFIG.model.min_training_examples="
                f"{CONFIG.model.min_training_examples} examples to train, got {features.shape[0]}"
            )
        unique_labels = set(labels.tolist())
        if unique_labels != {YES_LABEL, NO_LABEL}:
            raise ValueError(
                f"training labels must be exactly {{0, 1}}, got {sorted(unique_labels)}"
            )
        clf = LogisticRegression()
        clf.fit(features, labels)
        self._clf = clf
        self._n_examples_seen = features.shape[0]
