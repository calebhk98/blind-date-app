"""Tests for backend/ml/text_model.py (design doc §8.1)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.config import CONFIG
from backend.domain.enums import Verdict
from backend.ml.text_model import TextModel
from backend.tests.ml._helpers import FakeEncoder, make_separable_dataset


def test_cold_start_returns_config_default_before_training() -> None:
    model = TextModel(encoder=FakeEncoder())
    assert not model.is_trained
    assert model.predict_proba("some bio text") == CONFIG.model.cold_start_probability


def test_train_then_predict_separates_classes() -> None:
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    encoder, items, labels = make_separable_dataset(
        n_per_class=n_per_class, yes_prefix="yes", no_prefix="no", photo_label=False
    )
    model = TextModel(encoder=encoder)
    embeddings = np.stack([encoder.encode(item) for item in items])

    model.train(embeddings, labels)

    assert model.is_trained
    assert model.predict_proba("yes_holdout") > 0.9
    assert model.predict_proba("no_holdout") < 0.1


def test_pending_excluded_from_training() -> None:
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    encoder, items, labels = make_separable_dataset(
        n_per_class=n_per_class, yes_prefix="yes", no_prefix="no", photo_label=False
    )
    # Unlabelled (pending) rows sit exactly on the decision boundary; if they
    # leaked into training they would wreck the separator.
    pending_items = [f"pending_{i}" for i in range(10)]
    for item in pending_items:
        encoder.overrides[item] = np.zeros(encoder.dim)
    all_items = items + pending_items
    all_labels = labels + [Verdict.PENDING] * len(pending_items)
    embeddings = np.stack([encoder.encode(item) for item in all_items])

    model = TextModel(encoder=encoder)
    model.train(embeddings, all_labels)

    assert model.is_trained
    assert model.predict_proba("yes_holdout") > 0.9
    assert model.predict_proba("no_holdout") < 0.1


def test_train_raises_if_only_pending_labels_given() -> None:
    encoder = FakeEncoder()
    model = TextModel(encoder=encoder)
    embeddings = np.zeros((3, encoder.dim))
    with pytest.raises(ValueError):
        model.train(embeddings, [Verdict.PENDING] * 3)


def test_train_raises_on_embeddings_labels_length_mismatch() -> None:
    encoder = FakeEncoder()
    model = TextModel(encoder=encoder)
    with pytest.raises(ValueError):
        model.train(np.zeros((3, encoder.dim)), [Verdict.YES, Verdict.NO])


def test_import_does_not_require_sentence_transformers() -> None:
    # Sanity: default constructor must not eagerly import sentence_transformers.
    model = TextModel()
    assert model.encoder.dim > 0
    assert not model.is_trained
