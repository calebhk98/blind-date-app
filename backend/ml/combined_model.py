"""Combined model: reconciles image_verdict + text_verdict for profiles
routed to full-profile review (design doc §8, §6.3).

Input features are ``[image_verdict, text_verdict]`` encoded numerically
(pending/no/yes -> 0.5/0.0/1.0), optionally concatenated with raw embeddings
for future extensibility. The label is ``review_decisions.user_decision``.

CAVEAT (see the module-level ``CAVEAT`` constant, exposed so the API layer
can surface it wherever this model's prediction is shown): review_decisions
rows only ever exist for profiles that already hit a split-decision or
all-not-relevant trigger (design doc §6.3), so this model is trained
EXCLUSIVELY on disagreement / no-relevant-photo cases. It never sees a
profile the cheap per-modality models agreed on. It therefore answers "given
disagreement, which side should win", not "given any profile, yes or no".

Cold-start handling (same rule as image_model.py/text_model.py) lives
entirely in ``ml/_head.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from backend.domain.enums import UserDecision, Verdict
from backend.ml._head import NO_LABEL, TrainableHead, YES_LABEL

CAVEAT = (
    "This model only ever sees disagreement / no-relevant-photo cases, so it "
    "answers 'given disagreement, which side should win', not 'given any "
    "profile, yes or no'."
)

_VERDICT_TO_FLOAT = {Verdict.YES: 1.0, Verdict.NO: 0.0, Verdict.PENDING: 0.5}
_DECISION_TO_INT = {UserDecision.YES: YES_LABEL, UserDecision.NO: NO_LABEL}


class CombinedModel:
    """Predicts P(yes) for a profile given its per-modality verdicts."""

    def __init__(self) -> None:
        self._head = TrainableHead()

    @property
    def is_trained(self) -> bool:
        return self._head.is_trained

    @staticmethod
    def build_features(
        image_verdict: Verdict,
        text_verdict: Verdict,
        extra_embedding: np.ndarray | None = None,
    ) -> np.ndarray:
        """Encode [image_verdict, text_verdict] (+ optional raw embedding)."""
        if image_verdict not in _VERDICT_TO_FLOAT or text_verdict not in _VERDICT_TO_FLOAT:
            raise ValueError(
                f"unexpected Verdict pair for combined features: {image_verdict!r}, {text_verdict!r}"
            )
        base = np.array(
            [_VERDICT_TO_FLOAT[image_verdict], _VERDICT_TO_FLOAT[text_verdict]],
            dtype=np.float64,
        )
        if extra_embedding is None:
            return base
        return np.concatenate([base, np.asarray(extra_embedding, dtype=np.float64)])

    def predict_proba(
        self,
        image_verdict: Verdict,
        text_verdict: Verdict,
        extra_embedding: np.ndarray | None = None,
    ) -> float:
        """P(yes) given the two per-modality verdicts for a profile."""
        features = self.build_features(image_verdict, text_verdict, extra_embedding)
        return self._head.predict_proba(features)

    def train(self, features: np.ndarray, labels: Sequence[UserDecision]) -> None:
        """Fit the head on pre-built feature rows + UserDecision labels.

        Callers (ml/training.py) are responsible for only ever sourcing
        ``features``/``labels`` from review-path rows (review_decisions) --
        that constraint is a data-sourcing concern, not something this class
        can enforce given only numeric features.
        """
        features = np.asarray(features)
        if len(labels) != features.shape[0]:
            raise ValueError(
                f"features/labels length mismatch: {features.shape[0]} vs {len(labels)}"
            )
        for label in labels:
            if label not in _DECISION_TO_INT:
                raise ValueError(f"unexpected UserDecision for training: {label!r}")
        int_labels = np.array([_DECISION_TO_INT[label] for label in labels])
        self._head.train(features, int_labels)
