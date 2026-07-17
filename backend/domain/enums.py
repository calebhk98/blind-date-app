"""Enumerations shared across the whole backend (design doc §6).

These enums are the single source of truth for the string values used in the
SQLite CHECK constraints. The DB schema must reference exactly these values --
see ``sql_values()`` helpers used by the migration generator/tests.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """String-valued enum whose members compare equal to their raw string."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def sql_check(cls, column: str) -> str:
        """Render a CHECK constraint body for use in migrations, e.g.
        ``image_verdict IN ('pending','yes','no')``."""
        joined = ", ".join(f"'{v}'" for v in cls.values())
        return f"{column} IN ({joined})"


class Verdict(_StrEnum):
    """Per-modality verdict on a profile (image_verdict / text_verdict)."""

    PENDING = "pending"
    YES = "yes"
    NO = "no"


class PhotoLabel(_StrEnum):
    """Per-photo human judgment (design doc §6.1 photos.label)."""

    PENDING = "pending"
    YES = "yes"
    NO = "no"
    NOT_RELEVANT = "not_relevant"


class Decision(_StrEnum):
    """final_decision on a profile."""

    PENDING = "pending"
    YES = "yes"
    NO = "no"


class DecisionSource(_StrEnum):
    """How final_decision was reached (design doc §6.1)."""

    AUTO = "auto"
    REVIEW = "review"


class TriggerReason(_StrEnum):
    """Why a profile was routed to full-profile review (design doc §6.1)."""

    SPLIT_DECISION = "split_decision"
    ALL_NOT_RELEVANT = "all_not_relevant"


class UserDecision(_StrEnum):
    """Terminal yes/no captured on the review path (review_decisions)."""

    YES = "yes"
    NO = "no"


class ModelName(_StrEnum):
    """Which model produced a prediction (design doc §8.2)."""

    IMAGE = "image"
    TEXT = "text"
    COMBINED = "combined"


class BackendType(_StrEnum):
    """Automation backend serving an app (design doc §6.1 apps.backend_type)."""

    WEB = "web"
    APPIUM = "appium"


class Modality(_StrEnum):
    """Draw-pool entry modality (design doc §7)."""

    PHOTO = "photo"
    TEXT = "text"


class SwipeDirection(_StrEnum):
    """Direction passed to adapter.swipe (design doc §3.1)."""

    YES = "yes"
    NO = "no"
