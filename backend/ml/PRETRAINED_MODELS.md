# Pretrained Model Research — Frozen Encoders + Tiny Heads

Design doc §5 ("frozen encoder + trainable head, minimize fine-tuning / labelled data") and §8/§8.1
(image model, text model, combined model). GitHub issue #11.

**Ground truth from the codebase**: every head in this app
(`backend/ml/_head.py::TrainableHead`) is a plain `sklearn.linear_model.LogisticRegression` fit on
frozen embeddings. Nothing here proposes fine-tuning a transformer — the only thing this document
picks is *which frozen encoder produces the embeddings*, and confirms the dimensionality the head
must be sized for. `backend/ml/embeddings/image_encoder.py` and `text_encoder.py` already implement
the recommendations below; this doc is the rationale + comparison trail for those choices.

All model facts below were pulled live from the Hugging Face Hub (config.json / README front-matter
of each repo) on 2026-07-17, cross-checked with web search. Every row cites its source.

---

## 1. Image embedding encoders (frozen)

| Model (HF id) | Embed dim | Params (measured) | License | Notes / CPU feasibility |
|---|---|---|---|---|
| [`openai/clip-vit-base-patch32`](https://huggingface.co/openai/clip-vit-base-patch32) | 512 (joint projection) | ~151M (605 MB fp32 `pytorch_model.bin`) | **No SPDX tag on the Hub.** Model card explicitly states: *"Any deployed use case of the model — whether commercial or not — is currently out of scope"* and *"surveillance and facial recognition are always out-of-scope regardless of performance."* ⚠️ | Cheapest CLIP variant (patch32 → 49 patches/image at 224px). Comfortable CPU inference (~tens of ms/image). |
| [`openai/clip-vit-large-patch14`](https://huggingface.co/openai/clip-vit-large-patch14) | 768 | ~428M (1.71 GB safetensors) | Same restrictive model-card language as above ⚠️ | 24-layer ViT-L/14; noticeably slower on CPU (patch14 → 256 patches/image), overkill for a binary head. |
| [`laion/CLIP-ViT-B-32-laion2B-s34B-b79K`](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K) (open_clip `ViT-B-32` / `pretrained="laion2b_s34b_b79k"`) | 512 | ~151M | **MIT**, explicit `license: mit` tag | Same architecture/cost as `clip-vit-base-patch32`, trained on LAION-2B. Reports *higher* zero-shot ImageNet accuracy than the OpenAI ViT-B/32 checkpoint (~66.6% vs ~63.3%, per LAION/open_clip results) with no license caveat. Drop-in for open_clip (same `dim=512`). |
| [`laion/CLIP-ViT-L-14-laion2B-s32B-b82K`](https://huggingface.co/laion/CLIP-ViT-L-14-laion2B-s32B-b82K) (open_clip `ViT-L-14` / `pretrained="laion2b_s32b_b82k"`) | 768 | ~428M | **MIT** | Same cost profile as `clip-vit-large-patch14`, no license caveat. |
| [`google/siglip-base-patch16-224`](https://huggingface.co/google/siglip-base-patch16-224) | 768 | ~203M (813 MB) | **Apache-2.0** | Sigmoid loss instead of CLIP's softmax contrastive loss; generally reports better zero-shot/retrieval accuracy per-parameter than CLIP. Patch16 costs more than CLIP's patch32 default. |
| [`google/siglip2-base-patch16-224`](https://huggingface.co/google/siglip2-base-patch16-224) | 768 | ~375M (1.5 GB) — larger than SigLIP1-base | **Apache-2.0** | Newer (2025) SigLIP2 training recipe (adds captioning + self-distillation objectives); best accuracy of the SigLIP family at "base" size but heavier than SigLIP1-base and CLIP-B/32. |
| [`facebook/dinov2-small`](https://huggingface.co/facebook/dinov2-small) | 384 | ~22M (88 MB) | **Apache-2.0** | Pure vision, self-supervised (DINOv2, [arXiv:2304.07193](https://arxiv.org/abs/2304.07193)) — no text tower at all, so it's cheaper than every CLIP/SigLIP option above at a comparable quality tier. No text-image alignment, which is irrelevant here since the head only ever needs a photo → yes/no classifier, not zero-shot text matching. DINOv2 features are specifically known for strong linear-probe transfer, which is exactly the "frozen encoder + tiny linear head" use case. |
| [`facebook/dinov2-base`](https://huggingface.co/facebook/dinov2-base) | 768 | ~86.6M (346 MB) | **Apache-2.0** | Same architecture family, larger; still cheaper than CLIP-B/32 for a comparable size class. |

### Recommendation: image encoder

**Keep `open_clip` `ViT-B-32`, but pin `pretrained="laion2b_s34b_b79k"` instead of `"openai"`.**

- `backend/ml/embeddings/image_encoder.py` already hardcodes `ViT-B-32` at `dim=512` — this is the
  right architecture pick for a CPU-first personal tool: patch32 is the cheapest ViT config in the
  CLIP/SigLIP family, the 512-dim embedding keeps the logistic-regression head tiny (512 weights,
  trivially trainable on the handful of labelled photos a single user will produce), and CLIP's
  web-scale contrastive pretraining bakes in a mix of semantic *and* stylistic/aesthetic signal
  (alt-text supervision correlates with photo quality/composition, not just object identity), which
  is a good general-purpose feature space for a subjective "yes/no on this photo" classifier.
- The *only* change worth making is the pretrained-weights tag: `pretrained="openai"` (current
  default) carries OpenAI's model-card restriction against "deployed" use, explicitly including
  facial-recognition-adjacent uses — this app processes photos of real people, so it sits close
  enough to that line to be worth avoiding. `pretrained="laion2b_s34b_b79k"` is the same
  architecture, same 512-dim output (zero code changes beyond the string), **MIT-licensed**, and
  benchmarks *at or above* the OpenAI weights on zero-shot accuracy.
- Runner-up: `facebook/dinov2-small` (384-dim, Apache-2.0, smallest/cheapest of all options, pure
  vision SSL known for strong linear-probe transfer) is a credible alternative if CLIP embeddings
  ever underperform for this specific yes/no task — worth keeping in mind as a swap-in (the `Encoder`
  protocol in `backend/ml/embeddings/__init__.py` is already designed for exactly this kind of
  swap). Not picked as the default only because CLIP's joint text-image pretraining gives it a
  slightly broader semantic feature space "for free," which may matter once the combined model
  wants richer signal than a bare verdict pair.
- SigLIP/SigLIP2 and CLIP-L/14 are not recommended as defaults: all three cost 2–3x the compute of
  ViT-B/32 for CPU inference with no clear win-size for a *linear* head trained on tens–hundreds of
  labelled examples (the head, not the encoder, is the bottleneck on data — a bigger embedding just
  means a bigger head to fit with the same tiny label budget).

---

## 2. Text / bio sentence-embedding encoders (frozen)

| Model (HF id) | Embed dim | Params (measured) | License | MTEB avg (English, 56 tasks) | Notes |
|---|---|---|---|---|---|
| [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | 384 | 22.7M (91 MB) | **Apache-2.0** | ~56.1 ([MinishLab/model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md)) | Trained on 1B+ sentence pairs; the de-facto lightweight default. Raw text in, no prompt/prefix engineering. |
| [`sentence-transformers/all-mpnet-base-v2`](https://huggingface.co/sentence-transformers/all-mpnet-base-v2) | 768 | ~109M | **Apache-2.0** | ~57.8 | Best of the classic `sentence-transformers` "all-*" family; ~3x the params of MiniLM for ~+1.7 MTEB points. |
| [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) | 384 | 33.4M (133 MB) | **MIT** | **62.17** (per model card) | Same 384-dim as MiniLM — a drop-in swap with no head-size change. Meaningfully stronger on MTEB. |
| [`BAAI/bge-base-en-v1.5`](https://huggingface.co/BAAI/bge-base-en-v1.5) | 768 | ~109M | **MIT** | **63.55** (per model card) | Best quality in this table; 2x the size of `bge-small`. |
| [`thenlper/gte-small`](https://huggingface.co/thenlper/gte-small) | 384 | 33.4M | **MIT** | 61.36 (per model card) | Comparable to `bge-small-en-v1.5` in size/quality. |
| [`thenlper/gte-base`](https://huggingface.co/thenlper/gte-base) | 768 | ~109M | **MIT** | 62.39 (per model card) | Comparable to `bge-base-en-v1.5`. |
| [`intfloat/e5-small-v2`](https://huggingface.co/intfloat/e5-small-v2) | 384 | ~33M | **MIT** | ~59.9 (MTEB leaderboard) | **Requires `"query: "` / `"passage: "` text prefixes at inference time** — the model card states skipping this causes a real performance drop. Adds implementation surface (encoder must know which prefix a bio counts as) for a 384-dim model that still scores below `bge-small-en-v1.5`. |
| [`intfloat/e5-base-v2`](https://huggingface.co/intfloat/e5-base-v2) | 768 | ~109M | **MIT** | ~61.5 | Same prefix requirement as `e5-small-v2`. |

### Recommendation: text encoder

**Keep `sentence-transformers/all-MiniLM-L6-v2`** (already the default in
`backend/ml/embeddings/text_encoder.py`, `dim=384`).

- Apache-2.0, ~91 MB, fast CPU inference, and — importantly for a low-maintenance personal
  project — **zero prompt-prefix convention to get right**. `e5-*` models silently degrade if you
  forget the `"query: "`/`"passage: "` prefix; `bge-*` recommends (but does not strictly require)
  an instruction prefix for *query*-side text specifically. MiniLM and mpnet take raw text as-is,
  which matches how `text_encoder.py` calls `.encode(text)` today with no prefix logic.
  Adding prefix handling would be extra logic + extra failure mode for a personal tool with one
  reviewer and no query/passage asymmetry (a bio is just a bio, not a search query).
- The ~6-point MTEB gap vs. `bge-small-en-v1.5`/`gte-small` matters less here than it would for a
  retrieval system: MTEB's average is dominated by retrieval/clustering/reranking tasks, whereas
  this app's actual need is "does this short casual bio's *semantic content* separate cleanly
  enough for a linear head trained on a few dozen examples" — a much lower bar, and MiniLM's STS
  (semantic textual similarity) subscores are close to the larger models'.
- **Concrete, low-risk upgrade path if quality ever becomes a bottleneck**: switch to
  `BAAI/bge-small-en-v1.5`. It's also 384-dim (no head resize needed, no `_head.py` change), also
  MIT-licensed, and scores ~6 points higher on MTEB. This is the natural next step, not `e5-*`
  (prefix complexity) or the `768`-dim models (2x embedding size → 2x head weights to fit on the
  same small label budget, for a ~1.5-point MTEB gain over `bge-small`).

---

## 3. Warm-start / preference-signal models (optional extra feature, not encoders)

These are models that predict something *closer to* "would a person like this photo" than a raw
CLIP/DINOv2 embedding does — the idea being that concatenating their scalar output onto the frozen
embedding could give the tiny logistic-regression head a "warmer" starting signal than a bare
512-dim CLIP vector, before any user labels exist.

| Model (HF id) | Predicts | License | Caveat |
|---|---|---|---|
| [`shunk031/aesthetics-predictor-v1-vit-large-patch14`](https://huggingface.co/shunk031/aesthetics-predictor-v1-vit-large-patch14) (HF wrapper of [LAION-AI/aesthetic-predictor](https://github.com/LAION-AI/aesthetic-predictor)) | A single scalar "general aesthetic quality" score (1–10-ish), a linear probe on CLIP ViT-L/14 embeddings trained on the [AVA dataset](https://github.com/imfing/ava_downloader) (~250K photos with crowd-sourced 1–10 aesthetic ratings). This is about photographic quality (composition, lighting, focus) — **not** about the subject's appearance. | Apache-2.0 (source repo [christophschuhmann/improved-aesthetic-predictor](https://github.com/christophschuhmann/improved-aesthetic-predictor)); HF wrapper package [shunk031/simple-aesthetics-predictor](https://github.com/shunk031/simple-aesthetics-predictor) is MIT. | Trained on a general "is this a good photo" crowd — biased toward professional/artistic photography norms (AVA is a photography-competition dataset), not dating-profile snapshots. Score correlates with lighting/focus/composition, which is legitimate general signal, but the *target label distribution* is not this user's taste. |
| [`shunk031/aesthetics-predictor-v2-sac-logos-ava1-l14-linearMSE`](https://huggingface.co/shunk031/aesthetics-predictor-v2-sac-logos-ava1-l14-linearMSE) | Same idea, "improved" V2 predictor trained on SAC + LAION-Logos + AVA (a broader, noisier mix). | Same lineage/license as above. | Same caveat; the LAION-Logos component makes this variant arguably *less* relevant to portrait photos than V1. |
| [`cafeai/cafe_aesthetic`](https://huggingface.co/cafeai/cafe_aesthetic) | Binary `aesthetic` / `not_aesthetic` classifier, fine-tuned on `microsoft/beit-base-patch16-384`, trained on ~3.5K anime/manga + real images for Stable-Diffusion dataset curation. | **AGPL-3.0** ⚠️ (copyleft — flag before shipping anything that bundles this weight) | Domain mismatch (anime/manga-oriented dataset curation, not real dating photos) *and* a restrictive license. Not recommended. |
| [`yuvalkirstain/PickScore_v1`](https://huggingface.co/yuvalkirstain/PickScore_v1) ([paper](https://arxiv.org/abs/2305.01569)) | A CLIP-H finetune that scores *generated* images against a *text prompt* for human-preference ranking (trained on the Pick-a-Pic dataset of AI-generated image comparisons). | MIT (per [GitHub repo](https://github.com/yuvalkirstain/PickScore)) | Wrong domain entirely — it ranks synthetic text-to-image outputs against their prompts, not real photos of people. Not applicable here. |

### Facial-attractiveness / attribute models — explicit ethical caveat

I could not find a Hugging-Face-hosted, permissively-licensed, well-documented **general facial
attractiveness scorer** worth recommending. The closest public work is research built on datasets
like SCUT-FBP5500, which the bias literature flags directly:

- Facial beauty prediction models trained on datasets like SCUT-FBP and MEBeauty have been shown to
  **encode measurable ethnic/demographic bias** — see
  [*Analysis of Bias in Deep Learning Facial Beauty Regressors*](https://arxiv.org/html/2509.24138v1)
  (arXiv:2509.24138) and
  [*Ethically aligned Deep Learning: Unbiased Facial Aesthetic Prediction*](https://arxiv.org/abs/2111.05149)
  (arXiv:2111.05149). Rater-pool composition (who rated the training images, and their own
  in-group preference) leaks directly into the model's notion of "attractive."
- **This matters even more, not less, for a strictly personal single-user tool.** Any external
  attractiveness model bakes in *someone else's* (a research dataset's rater pool's) aesthetic
  preference. Feeding that into this app would inject a foreign, demographically-biased prior into
  a system whose entire design goal (design doc §5/§8) is to learn **one specific individual's**
  preference from their own labels — the opposite of what an attractiveness-scorer feature would
  do. It would not "warm start" the head toward this user's taste; it would bias it toward the
  training dataset raters' taste, which the user would then have to actively out-train with labels.
  There is also no ethical argument for training/serving a facial-attractiveness-scoring feature
  even in a private single-user tool — the bias and objectification concerns in the cited papers
  apply to the *model*, not just to its public deployment.
- **Recommendation: do not use a facial-attractiveness/attribute model, as a feature or otherwise.**

### How a warm-start feature *could* be wired in (if ever pursued) vs. why it's likely skippable

`backend/ml/combined_model.py::build_features` already supports exactly this pattern — it
concatenates an optional `extra_embedding` onto the base `[image_verdict, text_verdict]` vector, and
the same trick would work in `image_model.py` (concatenate a scalar aesthetic score onto the 512-dim
CLIP embedding before calling `TrainableHead.train`/`predict_proba`). If pursued: run
`shunk031/aesthetics-predictor-v1-vit-large-patch14` once per photo, append its scalar output as a
513th feature.

That said, **it's probably not worth doing for v1**:

1. It adds a second frozen model (another ~1.2 GB download, another lazy-import path, another
   `Encoder`-shaped thing to maintain) for one extra scalar feature.
2. `TrainableHead` is a plain logistic regression fit on whatever data exists — with `sklearn`'s
   default L2 regularization it will happily learn to ignore an uninformative extra feature, so the
   theoretical downside of *not* adding it is small.
3. CLIP/open_clip embeddings already implicitly encode a lot of "generic photo quality" signal
   (alt-text-supervised pretraining correlates with composition/lighting), so the AVA-aesthetic
   scalar is likely partially redundant with what the frozen embedding already provides.
4. The actual bottleneck for this app is **label volume from one user**, not head expressiveness —
   a warmer starting *feature space* helps most when you have zero-shot / near-zero-shot
   requirements; this app's cold-start behavior is already handled explicitly and separately in
   `ml/_head.py` (`cold_start_probability`), which is a cleaner solution to "no labels yet" than
   trying to encode a proxy preference into the feature space.

**Verdict: skip the aesthetic-predictor warm start for v1.** Revisit only if the tiny head
under-performs on pure embeddings once real labels exist — the two are only ~2 lines apart
(`np.concatenate` in `build_features`/encoder `encode()`), so it's cheap to add later rather than
now.

---

## 4. Implementation recommendation

Exact HF ids / package versions to load, matching what `backend/ml/embeddings/*.py` already assumes:

### Image encoder — `open_clip`

```python
# backend/ml/embeddings/image_encoder.py
import open_clip

model, _, preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32",
    pretrained="laion2b_s34b_b79k",  # MIT-licensed weights; see §1 rationale above.
    # pretrained="openai" also works (dim is identical, 512) but carries the
    # OpenAI CLIP model-card restriction against deployed/facial-adjacent use.
)
model.eval()
# embedding dim to size the LogisticRegression head for:
IMAGE_EMBED_DIM = 512
```

Install:
```
pip install open_clip_torch torch pillow
```

### Text encoder — `sentence-transformers`

```python
# backend/ml/embeddings/text_encoder.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
# embedding dim to size the LogisticRegression head for:
TEXT_EMBED_DIM = 384
```

Install:
```
pip install sentence-transformers torch
```
(`sentence-transformers` pulls in `torch` + `transformers` transitively; no separate pin needed.)

### Combined model

No pretrained encoder of its own — per `backend/ml/combined_model.py`, its input is the 2-dim
`[image_verdict, text_verdict]` pair (already produced by the two models above), optionally
concatenated with a raw embedding via `extra_embedding`. Nothing to install beyond what the two
encoders above already need.

### Lazy import discipline (already implemented, documented here for the next person)

Dev/CI environments only guarantee `numpy` + `scikit-learn` — `torch`, `open_clip`, and
`sentence-transformers` are **not** installed there. Both encoder modules already follow the
required pattern:

- `import torch` / `import open_clip` / `from sentence_transformers import SentenceTransformer` only
  happen inside `_load()` / `encode()`, never at module top-level or in `__init__`.
- `import backend.ml.embeddings.image_encoder` (and `text_encoder`) must succeed with only
  `numpy`/`scikit-learn` present — the `Encoder` protocol (`backend/ml/embeddings/__init__.py`) lets
  tests inject a `FakeEncoder` that returns deterministic vectors without ever touching the heavy
  deps.
- Keep this pattern for any future encoder swap (e.g. `bge-small-en-v1.5`, DINOv2): add the new
  class, keep heavy imports inside `_load()`/`encode()`, and update the `dim` constant to match the
  table above.

### Caching embeddings

Because the encoders are **frozen** (never fine-tuned), an embedding is a pure function of
`(model_id, pretrained_tag_or_revision, input_bytes)` — safe to cache indefinitely with no
invalidation logic beyond "did the model choice change."

- Key: a content hash of the input (`sha256` of image bytes, or of the normalized bio string) plus
  the encoder identity (e.g. `"open_clip:ViT-B-32:laion2b_s34b_b79k"` /
  `"sentence-transformers:all-MiniLM-L6-v2"`), so switching encoders in the future can't silently
  serve stale-dimension vectors from the cache.
- Storage: simplest option is a table/blob column (`embedding_cache(key TEXT PRIMARY KEY, vector
  BLOB, dim INT)`) in the existing SQLite DB (`backend/db/`), storing `vector.astype(np.float32).tobytes()`;
  a flat `.npy`/`.npz` file keyed by hash is an equally fine alternative for a single-user tool with
  no concurrent-writer concerns.
- Payoff: every `predict_proba` / re-scoring pass over previously-seen photos or bios (e.g.
  re-running the combined model, or re-drawing a profile) becomes a cache hit instead of a
  forward pass through a 22M–150M-parameter network — meaningful on CPU-only hardware.
