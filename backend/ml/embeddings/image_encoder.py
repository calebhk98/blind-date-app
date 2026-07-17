"""Frozen image embedding encoder (design doc §5, §8, §8.1).

``OpenClipImageEncoder`` wraps open_clip's ViT-B-32, pretrained
"laion2b_s34b_b79k" (see backend/ml/PRETRAINED_MODELS.md for the selection
rationale -- owned by a parallel research task, not this module; the LAION
checkpoint was picked over the OpenAI "openai" checkpoint because the latter's
model card explicitly excludes deployed use, whereas the MIT-licensed LAION
checkpoint has no such restriction and scores slightly higher on zero-shot
benchmarks). ``torch``/``open_clip`` are NOT
installed in every environment (only numpy + scikit-learn are guaranteed), so
they are imported lazily inside ``_load()``/``encode()`` -- never at module
import time or in ``__init__`` -- meaning ``import backend.ml.embeddings.
image_encoder`` must always succeed even without the heavy deps present.

``image_model.py`` depends on the ``Encoder`` protocol (see
``backend/ml/embeddings/__init__.py``), not on this concrete class, so tests
can inject a ``FakeEncoder`` that returns deterministic numpy vectors without
ever touching torch.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.ml.embeddings import Encoder  # noqa: F401  (re-exported for callers)

# ViT-B-32 (open_clip, pretrained="openai") embedding dimensionality.
_OPEN_CLIP_VIT_B_32_DIM = 512


class OpenClipImageEncoder:
    """Frozen open_clip image encoder. Swappable via constructor args.

    Model id defaults to ``ViT-B-32`` / ``laion2b_s34b_b79k`` per the
    pretrained-models research doc (§5). Nothing heavy is imported until
    ``encode()`` is first called, so simply constructing this object (e.g. as
    a default arg) is safe in environments without torch/open_clip installed.
    """

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k") -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.dim = _OPEN_CLIP_VIT_B_32_DIM
        self._model = None
        self._preprocess = None

    def _load(self) -> None:
        if self._model is not None:
            return
        import open_clip  # lazy: not installed in every environment

        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained
        )
        model.eval()
        self._model = model
        self._preprocess = preprocess

    def encode(self, item: object) -> np.ndarray:
        """Encode one image into a fixed-length vector.

        ``item`` may be a ``PIL.Image.Image``, or a path (str/Path) to an
        image file on disk.
        """
        self._load()
        import torch  # lazy: not installed in every environment
        from PIL import Image

        image = item
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        assert self._preprocess is not None and self._model is not None
        tensor = self._preprocess(image).unsqueeze(0)
        with torch.no_grad():
            features = self._model.encode_image(tensor)
        return features.squeeze(0).cpu().numpy().astype(np.float32)
