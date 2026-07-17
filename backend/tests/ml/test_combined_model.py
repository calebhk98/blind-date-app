"""Tests for backend/ml/combined_model.py (design doc §8)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.config import CONFIG
from backend.domain.enums import UserDecision, Verdict
from backend.ml.combined_model import CAVEAT, CombinedModel


def test_cold_start_returns_config_default_before_training() -> None:
    model = CombinedModel()
    assert not model.is_trained
    assert model.predict_proba(Verdict.YES, Verdict.NO) == CONFIG.model.cold_start_probability


def test_caveat_is_exposed_and_describes_disagreement_only_scope() -> None:
    assert isinstance(CAVEAT, str) and CAVEAT
    assert "disagreement" in CAVEAT


def test_build_features_encodes_verdicts_numerically() -> None:
    assert CombinedModel.build_features(Verdict.YES, Verdict.NO).tolist() == [1.0, 0.0]
    assert CombinedModel.build_features(Verdict.NO, Verdict.YES).tolist() == [0.0, 1.0]
    assert CombinedModel.build_features(Verdict.PENDING, Verdict.PENDING).tolist() == [0.5, 0.5]


def test_build_features_accepts_extra_embedding() -> None:
    features = CombinedModel.build_features(Verdict.YES, Verdict.NO, extra_embedding=np.array([1.0, 2.0]))
    assert features.tolist() == [1.0, 0.0, 1.0, 2.0]


def test_train_then_predict_separates_classes() -> None:
    # Disagreement rows only (this model is only ever trained on review-path
    # data -- see CAVEAT): image=yes/text=no -> user picked yes; the mirror
    # case -> user picked no. Small deterministic noise via extra_embedding
    # keeps rows distinct while preserving the underlying pattern.
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    rng = np.random.default_rng(0)
    rows: list[tuple[Verdict, Verdict, np.ndarray, UserDecision]] = []
    for _ in range(n_per_class):
        rows.append((Verdict.YES, Verdict.NO, rng.normal(scale=0.05, size=2), UserDecision.YES))
    for _ in range(n_per_class):
        rows.append((Verdict.NO, Verdict.YES, rng.normal(scale=0.05, size=2), UserDecision.NO))

    features = np.stack(
        [CombinedModel.build_features(iv, tv, extra) for iv, tv, extra, _ in rows]
    )
    labels = [decision for *_, decision in rows]

    model = CombinedModel()
    model.train(features, labels)

    assert model.is_trained
    # L2 regularization keeps probabilities shy of 0/1 even for a clean linear
    # split with only 2 features -- assert the (large) separation, not extremes.
    assert model.predict_proba(Verdict.YES, Verdict.NO, np.zeros(2)) > 0.8
    assert model.predict_proba(Verdict.NO, Verdict.YES, np.zeros(2)) < 0.2


def test_train_raises_on_features_labels_length_mismatch() -> None:
    model = CombinedModel()
    with pytest.raises(ValueError):
        model.train(np.zeros((3, 2)), [UserDecision.YES, UserDecision.NO])


def test_build_features_raises_on_unexpected_verdict() -> None:
    with pytest.raises(ValueError):
        CombinedModel.build_features("bogus", Verdict.YES)  # type: ignore[arg-type]
