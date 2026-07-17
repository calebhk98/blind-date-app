"""Frozen embedding encoders (design doc §5, §8).

Both ``image_encoder.py`` and ``text_encoder.py`` implement the same tiny
``Encoder`` interface so the trainable heads in ``ml/image_model.py`` and
``ml/text_model.py`` never need to know which concrete encoder they're
holding -- production code injects the real (lazy-heavy-import) encoder,
tests inject a deterministic ``FakeEncoder``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Encoder(Protocol):
    """Minimal interface every embedding encoder (real or fake) must satisfy."""

    dim: int

    def encode(self, item: object) -> np.ndarray:
        """Return a 1-D float32 embedding vector of length ``self.dim``."""
        ...
