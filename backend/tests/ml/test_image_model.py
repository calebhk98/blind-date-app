"""Tests for backend/ml/image_model.py (design doc §8.1)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.config import CONFIG
from backend.domain.enums import PhotoLabel
from backend.ml.image_model import ImageModel
from backend.tests.ml._helpers import FakeEncoder, make_separable_dataset


def test_cold_start_returns_config_default_before_training() -> None:
    model = ImageModel(encoder=FakeEncoder())
    assert not model.is_trained
    assert model.predict_proba("any_photo") == CONFIG.model.cold_start_probability


def test_cold_start_below_min_training_examples() -> None:
    # Even after a fit, too few examples must still read as cold start --
    # covered indirectly by _head, but re-asserted here at the model level.
    encoder = FakeEncoder(overrides={"a": np.full(8, 5.0), "b": np.full(8, -5.0)})
    model = ImageModel(encoder=encoder)
    with pytest.raises(ValueError):
        # Below CONFIG.model.min_training_examples -> _head fails loud.
        model.train(np.stack([encoder.encode("a"), encoder.encode("b")]), [PhotoLabel.YES, PhotoLabel.NO])
    assert not model.is_trained
    assert model.predict_proba("a") == CONFIG.model.cold_start_probability


def test_train_then_predict_separates_classes() -> None:
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    encoder, items, labels = make_separable_dataset(
        n_per_class=n_per_class, yes_prefix="yes", no_prefix="no", photo_label=True
    )
    model = ImageModel(encoder=encoder)
    embeddings = np.stack([encoder.encode(item) for item in items])

    model.train(embeddings, labels)

    assert model.is_trained
    assert model.predict_proba("yes_holdout") > 0.9
    assert model.predict_proba("no_holdout") < 0.1


def test_not_relevant_excluded_from_training() -> None:
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    encoder, items, labels = make_separable_dataset(
        n_per_class=n_per_class, yes_prefix="yes", no_prefix="no", photo_label=True
    )
    # Junk not_relevant rows sit exactly on the decision boundary (all
    # zeros); if they leaked into training they would wreck the separator.
    junk_items = [f"junk_{i}" for i in range(10)]
    for item in junk_items:
        encoder.overrides[item] = np.zeros(encoder.dim)
    all_items = items + junk_items
    all_labels = labels + [PhotoLabel.NOT_RELEVANT] * len(junk_items)
    embeddings = np.stack([encoder.encode(item) for item in all_items])

    model = ImageModel(encoder=encoder)
    model.train(embeddings, all_labels)

    assert model.is_trained
    assert model.predict_proba("yes_holdout") > 0.9
    assert model.predict_proba("no_holdout") < 0.1


def test_train_raises_if_only_not_relevant_labels_given() -> None:
    encoder = FakeEncoder()
    model = ImageModel(encoder=encoder)
    embeddings = np.zeros((3, encoder.dim))
    with pytest.raises(ValueError):
        model.train(embeddings, [PhotoLabel.NOT_RELEVANT] * 3)


def test_train_raises_on_embeddings_labels_length_mismatch() -> None:
    encoder = FakeEncoder()
    model = ImageModel(encoder=encoder)
    with pytest.raises(ValueError):
        model.train(np.zeros((3, encoder.dim)), [PhotoLabel.YES, PhotoLabel.NO])


def test_import_does_not_require_torch() -> None:
    # Sanity: default constructor must not eagerly import torch/open_clip.
    model = ImageModel()
    assert model.encoder.dim > 0
    assert not model.is_trained
