"""Pure draw engine (design doc §7).

``build_pending_pool`` turns a batch of profiles into the flat list of
un-judged items (text + photos) eligible for the next draw. ``draw_one``
picks a single item from that pool: an app is chosen uniformly among the
apps that still have entries, then an entry is chosen uniformly within that
app, so no single app can dominate the draw just by having more pending
items.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.domain.enums import Modality
from backend.domain.types import PoolEntry


@dataclass(frozen=True)
class DrawProfile:
    """Lightweight input shape consumed by build_pending_pool."""

    app_id: str
    profile_id: str
    hard_filter_hit: bool
    text_pending: bool
    pending_photo_ids: list[str] = field(default_factory=list)


def build_pending_pool(
    profiles: list[DrawProfile], hard_filter_enabled: bool
) -> list[PoolEntry]:
    eligible = _eligible_profiles(profiles, hard_filter_enabled)
    pool: list[PoolEntry] = []
    for profile in eligible:
        pool.extend(_entries_for_profile(profile))
    return pool


def _eligible_profiles(
    profiles: list[DrawProfile], hard_filter_enabled: bool
) -> list[DrawProfile]:
    if not hard_filter_enabled:
        return list(profiles)
    return [profile for profile in profiles if not profile.hard_filter_hit]


def _entries_for_profile(profile: DrawProfile) -> list[PoolEntry]:
    entries = [_text_entry(profile)] if profile.text_pending else []
    return entries + _photo_entries(profile)


def _text_entry(profile: DrawProfile) -> PoolEntry:
    return PoolEntry(
        app_id=profile.app_id,
        modality=Modality.TEXT,
        item_id=profile.profile_id,
        profile_id=profile.profile_id,
        hard_filter_hit=profile.hard_filter_hit,
    )


def _photo_entries(profile: DrawProfile) -> list[PoolEntry]:
    return [
        PoolEntry(
            app_id=profile.app_id,
            modality=Modality.PHOTO,
            item_id=photo_id,
            profile_id=profile.profile_id,
            hard_filter_hit=profile.hard_filter_hit,
        )
        for photo_id in profile.pending_photo_ids
    ]


def draw_one(pool: list[PoolEntry], rng: random.Random) -> PoolEntry | None:
    if not pool:
        return None
    entries_by_app = _group_by_app(pool)
    app_id = rng.choice(sorted(entries_by_app))
    return rng.choice(entries_by_app[app_id])


def _group_by_app(pool: list[PoolEntry]) -> dict[str, list[PoolEntry]]:
    grouped: dict[str, list[PoolEntry]] = {}
    for entry in pool:
        grouped.setdefault(entry.app_id, []).append(entry)
    return grouped
