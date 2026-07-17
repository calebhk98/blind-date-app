"""Tests for backend/ml/model_store.py (issue #19).

Covers the acceptance criterion directly: train on synthetic data, persist,
then load in a *fresh* model instance and assert it returns the trained
probabilities rather than the cold-start default. Also covers pruning
(keep-last-N) and the plain save/load/list_versions contract in isolation
from any concrete model class.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.config import CONFIG
from backend.ml import model_store
from backend.ml.combined_model import CombinedModel
from backend.ml.image_model import ImageModel
from backend.tests.ml._helpers import FakeEncoder, make_separable_dataset


@pytest.fixture(autouse=True)
def _isolated_models_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets its own throwaway models dir so runs never collide
    with each other, with a real ``backend/data/models``, or leak state."""
    monkeypatch.setenv("BDA_MODELS_DIR", str(tmp_path / "models"))
    assert CONFIG.storage.models_dir == tmp_path / "models"


def test_load_latest_returns_none_when_nothing_saved() -> None:
    assert model_store.load_latest("nonexistent-model") is None


def test_save_then_load_latest_round_trips_a_plain_object() -> None:
    payload = {"hello": "world", "numbers": [1, 2, 3]}
    path = model_store.save_model("demo", payload)

    assert path.exists()
    loaded = model_store.load_latest("demo")
    assert loaded == payload


def test_list_versions_grows_with_each_save_oldest_first() -> None:
    model_store.save_model("demo", {"v": 1})
    model_store.save_model("demo", {"v": 2})
    model_store.save_model("demo", {"v": 3})

    versions = model_store.list_versions("demo")
    assert len(versions) == 3
    assert [v.timestamp for v in versions] == sorted(v.timestamp for v in versions)


def test_list_versions_excludes_the_latest_pointer_and_other_names() -> None:
    model_store.save_model("alpha", {"v": 1})
    model_store.save_model("beta", {"v": 1})

    alpha_versions = model_store.list_versions("alpha")
    assert len(alpha_versions) == 1
    assert all(v.name == "alpha" for v in alpha_versions)
    # The "-latest.pkl" pointer file must never itself show up as a version.
    assert all("latest" not in v.path.stem.split("-")[1:] for v in alpha_versions)


def test_prune_keeps_only_last_n_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_store, "_KEEP_LAST_N", 3)

    saved_paths = [model_store.save_model("demo", {"v": i}) for i in range(6)]

    versions = model_store.list_versions("demo")
    assert len(versions) == 3
    # The 3 most recently saved snapshots survive; earlier ones are gone.
    surviving_paths = {v.path for v in versions}
    assert surviving_paths == set(saved_paths[-3:])
    for pruned_path in saved_paths[:-3]:
        assert not pruned_path.exists()

    # The latest pointer must still reflect the very last save.
    assert model_store.load_latest("demo") == {"v": 5}


def test_image_model_save_and_load_or_cold_start_returns_trained_probabilities() -> None:
    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    encoder, items, labels = make_separable_dataset(
        n_per_class=n_per_class, yes_prefix="yes", no_prefix="no", photo_label=True
    )
    embeddings = np.stack([encoder.encode(item) for item in items])

    trained_model = ImageModel(encoder=encoder)
    trained_model.train(embeddings, labels)
    assert trained_model.is_trained
    trained_model.save()

    # A brand-new process/instance never sees ``trained_model`` -- only what
    # was persisted to disk. Use a *fresh* FakeEncoder wired to the same
    # overrides (holdout keys) to simulate that isolation.
    fresh_encoder = FakeEncoder(dim=encoder.dim, overrides=dict(encoder.overrides))
    fresh_model = ImageModel.load_or_cold_start(encoder=fresh_encoder)

    assert fresh_model.is_trained
    assert fresh_model.predict_proba("yes_holdout") > 0.9
    assert fresh_model.predict_proba("no_holdout") < 0.1
    # Not the cold-start default.
    assert fresh_model.predict_proba("yes_holdout") != CONFIG.model.cold_start_probability


def test_image_model_load_or_cold_start_without_a_saved_model_is_cold_start() -> None:
    model = ImageModel.load_or_cold_start(encoder=FakeEncoder())
    assert not model.is_trained
    assert model.predict_proba("anything") == CONFIG.model.cold_start_probability


def test_combined_model_save_and_load_or_cold_start_returns_trained_probabilities() -> None:
    from backend.domain.enums import UserDecision, Verdict

    n_per_class = max(15, CONFIG.model.min_training_examples // 2 + 1)
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(n_per_class):
        rows.append((Verdict.YES, Verdict.NO, rng.normal(scale=0.05, size=2), UserDecision.YES))
    for _ in range(n_per_class):
        rows.append((Verdict.NO, Verdict.YES, rng.normal(scale=0.05, size=2), UserDecision.NO))
    features = np.stack([CombinedModel.build_features(iv, tv, extra) for iv, tv, extra, _ in rows])
    labels = [decision for *_, decision in rows]

    trained_model = CombinedModel()
    trained_model.train(features, labels)
    assert trained_model.is_trained
    trained_model.save()

    fresh_model = CombinedModel.load_or_cold_start()
    assert fresh_model.is_trained
    assert fresh_model.predict_proba(Verdict.YES, Verdict.NO, np.zeros(2)) > 0.8
    assert fresh_model.predict_proba(Verdict.NO, Verdict.YES, np.zeros(2)) < 0.2


def test_save_model_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        model_store.save_model("", {"v": 1})
