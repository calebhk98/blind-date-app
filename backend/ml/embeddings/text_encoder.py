"""Frozen text embedding encoder (design doc §5, §8, §8.1).

``SentenceTransformerTextEncoder`` wraps sentence-transformers'
``all-MiniLM-L6-v2`` (see backend/ml/PRETRAINED_MODELS.md for the selection
rationale -- owned by a parallel research task, not this module).
``sentence_transformers`` is NOT installed in every environment (only numpy +
scikit-learn are guaranteed), so it is imported lazily inside ``_load()`` --
never at module import time or in ``__init__`` -- meaning ``import
backend.ml.embeddings.text_encoder`` must always succeed even without the
heavy deps present.

``text_model.py`` depends on the ``Encoder`` protocol (see
``backend/ml/embeddings/__init__.py``), not on this concrete class, so tests
can inject a ``FakeEncoder`` that returns deterministic numpy vectors without
ever touching sentence-transformers.
"""

from __future__ import annotations

import numpy as np

from backend.ml.embeddings import Encoder  # noqa: F401  (re-exported for callers)

# all-MiniLM-L6-v2 embedding dimensionality.
_MINILM_L6_V2_DIM = 384


class SentenceTransformerTextEncoder:
    """Frozen sentence-transformers text encoder. Swappable via constructor.

    Model id defaults to ``all-MiniLM-L6-v2`` per the pretrained-models
    research doc (§5). Nothing heavy is imported until ``encode()`` is first
    called, so simply constructing this object (e.g. as a default arg) is
    safe in environments without sentence-transformers installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dim = _MINILM_L6_V2_DIM
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # lazy: not always installed

        self._model = SentenceTransformer(self.model_name)

    def encode(self, item: object) -> np.ndarray:
        """Encode one piece of bio text into a fixed-length vector."""
        self._load()
        assert self._model is not None
        text = "" if item is None else str(item)
        vector = self._model.encode(text, convert_to_numpy=True)
        return np.asarray(vector, dtype=np.float32)
