"""Tests for build_pending_pool / draw_one (design doc §7)."""

from __future__ import annotations

import random

from backend.domain.enums import Modality
from backend.logic.draw import DrawProfile, build_pending_pool, draw_one


def _profile(
    app_id: str = "tinder",
    profile_id: str = "p1",
    hard_filter_hit: bool = False,
    text_pending: bool = False,
    pending_photo_ids: list[str] | None = None,
) -> DrawProfile:
    return DrawProfile(
        app_id=app_id,
        profile_id=profile_id,
        hard_filter_hit=hard_filter_hit,
        text_pending=text_pending,
        pending_photo_ids=pending_photo_ids if pending_photo_ids is not None else [],
    )


def test_pool_only_reflects_pending_flags() -> None:
    profile = _profile(text_pending=True, pending_photo_ids=["ph1", "ph2"])
    pool = build_pending_pool([profile], hard_filter_enabled=False)
    assert len(pool) == 3
    seen = {(entry.modality, entry.item_id) for entry in pool}
    assert seen == {
        (Modality.TEXT, "p1"),
        (Modality.PHOTO, "ph1"),
        (Modality.PHOTO, "ph2"),
    }


def test_judged_items_never_appear_in_pool() -> None:
    # A profile with nothing pending (already judged) contributes no entries.
    profile = _profile(text_pending=False, pending_photo_ids=[])
    pool = build_pending_pool([profile], hard_filter_enabled=False)
    assert pool == []


def test_hard_filter_enabled_excludes_hit_profiles() -> None:
    hit = _profile(profile_id="p1", hard_filter_hit=True, text_pending=True)
    clean = _profile(profile_id="p2", hard_filter_hit=False, text_pending=True)
    pool = build_pending_pool([hit, clean], hard_filter_enabled=True)
    assert [entry.profile_id for entry in pool] == ["p2"]


def test_hard_filter_disabled_includes_hit_profiles() -> None:
    hit = _profile(profile_id="p1", hard_filter_hit=True, text_pending=True)
    clean = _profile(profile_id="p2", hard_filter_hit=False, text_pending=True)
    pool = build_pending_pool([hit, clean], hard_filter_enabled=False)
    profile_ids = {entry.profile_id for entry in pool}
    assert profile_ids == {"p1", "p2"}


def test_app_with_no_entries_never_selected() -> None:
    profile = _profile(app_id="bumble", text_pending=True)
    pool = build_pending_pool([profile], hard_filter_enabled=False)
    rng = random.Random(0)
    for _ in range(20):
        entry = draw_one(pool, rng)
        assert entry is not None
        assert entry.app_id == "bumble"


def test_seeded_rng_is_deterministic() -> None:
    profile = _profile(text_pending=True, pending_photo_ids=["ph1", "ph2", "ph3"])
    pool = build_pending_pool([profile], hard_filter_enabled=False)
    first = draw_one(pool, random.Random(42))
    second = draw_one(pool, random.Random(42))
    assert first == second


def test_two_app_pool_selects_per_app_then_per_entry() -> None:
    # bumble has 3x as many entries as tinder; if selection were flat over the
    # whole pool, tinder would only be picked ~25% of the time. The draw must
    # pick an app first (uniformly) and then an entry within that app, so
    # tinder should land close to 50%.
    tinder = _profile(app_id="tinder", profile_id="t1", pending_photo_ids=["tph1"])
    bumble = _profile(
        app_id="bumble", profile_id="b1", pending_photo_ids=["bph1", "bph2", "bph3"]
    )
    pool = build_pending_pool([tinder, bumble], hard_filter_enabled=False)
    rng = random.Random(7)
    trials = 2000
    tinder_hits = 0
    for _ in range(trials):
        entry = draw_one(pool, rng)
        assert entry is not None
        if entry.app_id == "tinder":
            tinder_hits += 1
    ratio = tinder_hits / trials
    assert 0.4 < ratio < 0.6


def test_empty_pool_returns_none() -> None:
    rng = random.Random(0)
    assert draw_one([], rng) is None
