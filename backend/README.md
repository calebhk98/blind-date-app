# Blind Date App — Backend

Python/FastAPI orchestrator, app adapters (Playwright + Appium), and the ML
pipeline for the personal dating-app aggregator. See the technical design doc
for the full rationale; this README is the map.

## Layout

```
backend/
  config.py            # SINGLE source of truth for all tunables (§4)
  domain/
    enums.py           # Verdict, PhotoLabel, Decision, ... (SoT for DB CHECK values)
    types.py           # RawProfile, RawPhoto, PoolEntry, VerdictResult, ...
  db/
    connection.py      # connect()/transaction() helpers (FK on, config-driven path)
    migrations/        # versioned .sql migrations (§4: never hand-edit schema)
    migrate.py         # migration runner
  logic/               # PURE functions only, no I/O (§4)
    verdict.py         # aggregate_image_verdict  (§6.2)
    decision.py        # resolve_final_decision   (§6.3)
    draw.py            # build_pending_pool / draw_one (§7)
  adapters/
    base.py            # DatingAppAdapter Protocol (§3.1)
    web_base.py        # WebBackendAdapter (Playwright, abstract)
    appium_base.py     # AppiumBackendAdapter (abstract)
    tinder.py bumble.py hinge.py   # one file per app (§3.2)
    registry.py        # app_id -> adapter class (keeps orchestrator app-agnostic)
  ml/
    embeddings/        # frozen encoders (image + text)
    image_model.py text_model.py combined_model.py
    training.py accuracy.py
    PRETRAINED_MODELS.md   # research output (§5, §8)
  services/            # side-effecting orchestration (fetch, swipe, verdict engine)
  api/
    main.py            # FastAPI app
    routes/            # one handler per file (§4)
  tests/               # pytest, mirrors package layout; TDD (§4)
```

## Conventions (design doc §4)

- **TDD**: test before implementation for every pure unit.
- **Pure vs side-effecting**: `logic/` is pure (trivially unit-tested);
  `adapters/`, `services/`, `db/` writes are side-effecting.
- **Single source of truth**: verdict rule, final-decision rule, and draw-pool
  filter each live in exactly one function.
- **No app-specific logic outside its adapter** — no `if app_id == "tinder"`
  anywhere in `api/`, `services/`, or `logic/`.
- **Fail loud**: no silent `except: pass`; a catch re-raises, logs with context,
  or explicitly marks a profile failed-to-parse.
- **Config, not magic numbers**: import from `backend.config.CONFIG`.
- **Type hints everywhere**; `mypy backend` should stay clean.

## Running

```bash
pip install -r backend/requirements.txt
python -m backend.db.migrate          # apply migrations
uvicorn backend.api.main:app --reload # start the API
pytest                                # run the test suite (from repo root)
```
