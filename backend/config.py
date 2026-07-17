"""Single source of truth for all tunable values (design doc §4).

No magic numbers anywhere else in the codebase: tie thresholds, retry counts,
timeouts, model confidence cutoffs, paths, and draw limits all live here.
Values may be overridden via environment variables so a deployment never needs
to edit code to tune behaviour.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repository-root-relative default locations. Everything the tool persists lives
# under ``data/`` which is git-ignored (see .gitignore: *.db / *.sqlite).
_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _BACKEND_DIR / "data"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw) if raw is not None else default


@dataclass(frozen=True)
class VerdictConfig:
    """Thresholds for the pure verdict-aggregation rule (design doc §6.2)."""

    # A profile's photos pass when no_count / relevant_count <= this ratio.
    # A 50/50 split resolves to *yes* (asymmetric cost: a missed match is worse
    # than one extra look-and-decline), so the comparison is ``<=`` against 0.5.
    max_no_ratio: float = field(default_factory=lambda: _env_float("BDA_MAX_NO_RATIO", 0.5))


@dataclass(frozen=True)
class ModelConfig:
    """Model inference behaviour (design doc §8.1)."""

    # Probability returned before a model has been trained (cold start). 0.5 =
    # maximally uncertain. Cold-start handling is model-side only, never UI-side.
    cold_start_probability: float = field(
        default_factory=lambda: _env_float("BDA_COLD_START_PROB", 0.5)
    )
    # Minimum labelled examples before a head is considered "trained".
    min_training_examples: int = field(
        default_factory=lambda: _env_int("BDA_MIN_TRAIN_EXAMPLES", 20)
    )
    # Confidence band treated as "uncertain" for dashboards / logging.
    low_confidence_cutoff: float = field(
        default_factory=lambda: _env_float("BDA_LOW_CONF_CUTOFF", 0.6)
    )
    # Rolling-accuracy window used by ml/accuracy.py.
    accuracy_window: int = field(default_factory=lambda: _env_int("BDA_ACCURACY_WINDOW", 100))


@dataclass(frozen=True)
class AutomationConfig:
    """Retry/timeout knobs shared by every adapter (design doc §4)."""

    max_retries: int = field(default_factory=lambda: _env_int("BDA_MAX_RETRIES", 3))
    retry_backoff_seconds: float = field(
        default_factory=lambda: _env_float("BDA_RETRY_BACKOFF", 2.0)
    )
    page_timeout_seconds: float = field(
        default_factory=lambda: _env_float("BDA_PAGE_TIMEOUT", 30.0)
    )
    default_fetch_limit: int = field(default_factory=lambda: _env_int("BDA_FETCH_LIMIT", 20))

    # Explicit Chromium binary for Playwright. In managed/sandboxed environments
    # the browser is pre-installed at a fixed path rather than downloaded, so
    # WebBackendAdapter launches with this when set (empty = Playwright default).
    chromium_executable_path: str = field(
        default_factory=lambda: os.environ.get("BDA_CHROMIUM_PATH", "")
    )


@dataclass(frozen=True)
class HardFilterConfig:
    """Default hard-filter criteria (design doc §7.4).

    These are only the *defaults*; the live criteria are editable at runtime and
    persisted in the ``settings`` table (see issue #21), so tuning them is an
    in-app action, not a code change. A criterion left at its "unset" value
    (None / empty) is not enforced.
    """

    min_age: int | None = field(
        default_factory=lambda: (int(v) if (v := os.environ.get("BDA_HF_MIN_AGE")) else None)
    )
    max_age: int | None = field(
        default_factory=lambda: (int(v) if (v := os.environ.get("BDA_HF_MAX_AGE")) else None)
    )
    max_distance: int | None = field(
        default_factory=lambda: (int(v) if (v := os.environ.get("BDA_HF_MAX_DIST")) else None)
    )
    # Comma-separated; a profile containing any blocked keyword is filtered.
    blocked_keywords: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            k.strip().lower()
            for k in os.environ.get("BDA_HF_BLOCKED", "").split(",")
            if k.strip()
        )
    )
    # A profile missing any required keyword is filtered.
    required_keywords: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            k.strip().lower()
            for k in os.environ.get("BDA_HF_REQUIRED", "").split(",")
            if k.strip()
        )
    )
    # Session-level default for whether the hard filter excludes from the pool.
    enabled_by_default: bool = field(
        default_factory=lambda: os.environ.get("BDA_HF_ENABLED", "true").lower() == "true"
    )


@dataclass(frozen=True)
class ApiConfig:
    """Local API server settings (design doc §3: React UI talks to FastAPI)."""

    # Origins allowed to call the API from a browser. The Next.js UI runs on
    # :3000 by default; override with a comma-separated BDA_CORS_ORIGINS.
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get(
                "BDA_CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if o.strip()
        )
    )


@dataclass(frozen=True)
class StorageConfig:
    """Local persistence locations (design doc §5: SQLite + filesystem images)."""

    data_dir: Path = field(default_factory=lambda: _env_path("BDA_DATA_DIR", _DEFAULT_DATA_DIR))

    @property
    def db_path(self) -> Path:
        return _env_path("BDA_DB_PATH", self.data_dir / "blind_date.db")

    @property
    def image_dir(self) -> Path:
        return _env_path("BDA_IMAGE_DIR", self.data_dir / "images")

    @property
    def session_dir(self) -> Path:
        """Persistent browser/app session storage (cookies, tokens)."""
        return _env_path("BDA_SESSION_DIR", self.data_dir / "sessions")

    @property
    def models_dir(self) -> Path:
        """Where trained model heads are persisted (issue #19)."""
        return _env_path("BDA_MODELS_DIR", self.data_dir / "models")


@dataclass(frozen=True)
class Config:
    verdict: VerdictConfig = field(default_factory=VerdictConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    hard_filter: HardFilterConfig = field(default_factory=HardFilterConfig)

    def ensure_dirs(self) -> None:
        """Create the local data directories if they do not yet exist."""
        self.storage.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage.image_dir.mkdir(parents=True, exist_ok=True)
        self.storage.session_dir.mkdir(parents=True, exist_ok=True)
        self.storage.models_dir.mkdir(parents=True, exist_ok=True)


# Importable singleton used across the codebase.
CONFIG = Config()
