"""Normalized data types shared across adapters, logic, ML, and API.

``RawProfile`` is the adapter output contract (design doc §3.1): every adapter,
web or Appium, translates its app's raw UI tree into this shape so the
orchestrator never needs to know which backend served a profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.domain.enums import (
    Decision,
    DecisionSource,
    Modality,
    PhotoLabel,
    Verdict,
)


@dataclass(frozen=True)
class RawPhoto:
    """A single photo as scraped from an app, before local persistence."""

    order_index: int
    # Exactly one of url / local bytes is expected to be populated by an adapter.
    url: str | None = None
    image_bytes: bytes | None = None


@dataclass(frozen=True)
class RawProfile:
    """Normalized profile emitted by any adapter (design doc §3.1)."""

    app_id: str
    external_id: str
    bio_text: str
    photos: list[RawPhoto] = field(default_factory=list)
    # Adapter-specific extras (age, distance, prompts...) kept opaque so the
    # orchestrator stays app-agnostic. Never branched on outside the adapter.
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Fail loud (design doc §4): a profile with no identity is corrupt data
        # and must never enter the store silently.
        if not self.external_id:
            raise ValueError("RawProfile.external_id must be non-empty")
        if not self.app_id:
            raise ValueError("RawProfile.app_id must be non-empty")


@dataclass(frozen=True)
class VerdictResult:
    """Output of the pure image-verdict aggregation (design doc §6.2).

    ``route_to_review`` is True with ``verdict is None`` when every photo was
    labelled not_relevant (routes to full-profile review, no verdict set).
    """

    verdict: Verdict | None
    route_to_review: bool = False


@dataclass(frozen=True)
class DecisionResult:
    """Output of the pure final-decision logic (design doc §6.3)."""

    decision: Decision | None
    source: DecisionSource | None
    route_to_review: bool = False
    trigger_reason: str | None = None


@dataclass(frozen=True)
class PoolEntry:
    """One draw-pool entry: a single un-judged item (design doc §7)."""

    app_id: str
    modality: Modality
    item_id: str  # photo_id for photo entries, profile_id for text entries
    profile_id: str
    hard_filter_hit: bool = False


@dataclass(frozen=True)
class JudgedPhoto:
    """Minimal photo shape consumed by the verdict aggregation rule."""

    photo_id: str
    label: PhotoLabel
