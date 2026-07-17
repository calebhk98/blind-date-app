# CLAUDE.md — Blind Date App (personal dating-app aggregator)

Guidance for Claude/agents working in this repo. Keep it current: when you hit
an environment quirk or a convention worth remembering, add it here.

## What this is
A personal tool that aggregates profiles across dating apps, splits photo vs.
text judgment to reduce halo-effect bias, executes user-approved swipes, and
trains three small models (image / text / combined) on the user's judgments.
See the technical design doc and `backend/README.md` for the architecture and
the §4 engineering conventions (TDD, single source of truth, no app-specific
logic in the orchestrator, fail-loud, config-not-magic-numbers, idempotent
swipes, versioned migrations, type hints).

## Layout
- `backend/` — Python/FastAPI orchestrator, adapters (Playwright + Appium), ML.
  `logic/` is pure; `services/`, `adapters/`, `db/` are side-effecting. Full map
  in `backend/README.md`.
- `src/` — Next.js 15 React review UI (talks to FastAPI over HTTP).
- `backend/adapters/planned/` — unregistered scaffold adapters for apps not yet
  implemented; catalog + signup URLs in `backend/adapters/DATING_APPS.md`.

## Running / testing
- Tests run **from the repo root**: `python3 -m pytest` (config in `pytest.ini`;
  discovers `backend/tests`). mypy config lives in `backend/pyproject.toml`
  (`python3 -m mypy --config-file backend/pyproject.toml backend`).
- UI: `npm run build` / `npx tsc --noEmit` / `npx eslint src`.
- Migrations: `python3 -m backend.db.migrate` (idempotent, auto-discovers
  `backend/db/migrations/*.sql` in filename order).

## ⚠️ Environment quirks (this sandbox)
- **Pre-installed Python deps only:** `pytest, mypy, fastapi, httpx, pydantic,
  numpy, scikit-learn` are installed. `torch, sentence-transformers,
  open-clip-torch, playwright, Appium-Python-Client` are **not** pre-installed
  (installable via `pip`, but torch is heavy). **Lazy-import** heavy libs inside
  functions so modules import and unit tests run without them — the ML tests
  inject a `FakeEncoder`; adapters mock the browser/driver.
- **Playwright works, but the browser is pre-installed, not downloadable.**
  Do NOT run `playwright install`. Chromium lives at
  `/opt/pw-browsers/chromium-*/chrome-linux/chrome` (glob it — the build number
  changes, e.g. `chromium-1194`). Launch with `executable_path=` that binary, or
  set `BDA_CHROMIUM_PATH` (config: `AutomationConfig.chromium_executable_path`,
  which `WebBackendAdapter` uses). The live browser test
  (`backend/tests/adapters/test_playwright_live.py`) auto-resolves it and skips
  if absent — run the suite with `BDA_CHROMIUM_PATH=/opt/pw-browsers/chromium-*/chrome-linux/chrome`
  to exercise it.
- **Real browser markup ≠ XHTML.** Browsers emit HTML5 void tags (`<img>`,
  `<br>`) that `ElementTree` rejects. Web adapters serialize matched cards with
  `XMLSerializer` (well-formed) instead of `outerHTML`, and
  `parse_xhtml_fragment` strips the XHTML namespace so bare-tag lookups match.
  Keep that pattern for new web adapters.
- **Appium / Android — SDK downloads and installs here** (`dl.google.com` is
  reachable through the proxy). Installed stack (redo in a fresh session):
  - Android SDK at `/opt/android-sdk` (`export ANDROID_HOME=/opt/android-sdk`):
    cmdline-tools + platform-tools (`adb 1.0.41`). **Gotcha:** the cmdline-tools
    zip is `commandlinetools-linux-<build>_latest.zip` — **one word**
    `commandlinetools`, not `commandline-tools` (the hyphenated name 404s). Get
    the current `<build>` from `https://dl.google.com/android/repository/repository2-1.xml`.
  - `appium` 3.5.2 (global npm) + `uiautomator2` driver 8.1.0
    (`appium driver install uiautomator2`).
  - `adb` runs (`adb devices` shows none until one is attached).
  - **The one real blocker is a device.** No `/dev/kvm`, so a *local* Android
    emulator has no hardware acceleration and won't boot usefully. To actually
    exercise the Appium adapters (Hinge + `appium`-classified planned apps),
    attach a **physical device** or a **remote/cloud emulator over TCP**
    (`adb connect host:port`), then point Appium at it.
- **SQLite + FastAPI TestClient:** TestClient runs handlers in a worker thread,
  and a `:memory:` connection can't cross threads. In API tests use a **file DB**
  and a `get_db` override that opens a **fresh connection per request** (see
  `backend/tests/api/test_api.py` / `test_photos.py`).
- **Outbound HTTPS** goes through the agent proxy (Java truststore + proxy are
  pre-set via `JAVA_TOOL_OPTIONS`). If a download fails TLS/gets 403/407, see
  `/root/.ccr/README.md`; never disable TLS verification.
- **Local data** (`backend/data/`: SQLite, images, sessions, models) is
  git-ignored. Paths come from `backend/config.py` — never hardcode them.

## Working through GitHub issues (agent workflow)
Repo: `calebhk98/blind-date-app`. **Drive delegated work through issues, not
long prompts.** The issue body is the spec; the agent prompt should carry only
generic get-up-to-speed context (repo layout, env quirks above, the contracts an
agent imports) that doesn't belong in the issue itself.

Every agent assigned an issue must:
1. **Read the issue and its comments first** — load the GitHub tools with
   `ToolSearch "select:mcp__github__issue_read,mcp__github__add_issue_comment"`,
   then `issue_read` (owner `calebhk98`, repo `blind-date-app`) including
   comments, so it has full context and doesn't repeat prior work.
2. **Do the work described in the issue.**
3. **Post a progress comment on the issue when done** (`add_issue_comment`):
   what was implemented, files touched, test results, assumptions/follow-ups.
   This is our durable, long-term tracking log.

When new gaps or follow-ups are discovered, file a new issue (with acceptance
criteria + dependencies) rather than burying the work in a prompt. Keep the
epic (#18) checklist current.

## Guardrails
- Personal tool: **every swipe is user-approved** (design doc §1). No bulk
  auto-swiping.
- Adapter selectors are best-effort until verified against the live app; keep
  the `# TODO: verify against live <app>` markers.
- Don't put app-specific logic outside its adapter (no `if app_id == ...` in
  `api/`, `services/`, or `logic/`).
