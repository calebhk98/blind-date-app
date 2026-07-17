"""Parsing tests for each app adapter's `_parse_profile` (design doc §3.2).

Each adapter gets a small, documented fixture -- an XHTML snippet for
Tinder/Bumble, an XML UI-tree for Hinge -- fed directly to `_parse_profile`.
No browser/driver is ever started, so these run with no playwright/appium
installed.
"""

from __future__ import annotations

import pytest

from backend.adapters.bumble import BumbleAdapter
from backend.adapters.hinge import HingeAdapter
from backend.adapters.tinder import TinderAdapter
from backend.adapters.web_base import ProfileParseError


class FakeSwipedStore:
    def __init__(self) -> None:
        self._swiped: set[str] = set()

    def is_swiped(self, profile_id: str) -> bool:
        return profile_id in self._swiped

    def mark_swiped(self, profile_id: str) -> None:
        self._swiped.add(profile_id)


# -- Tinder ----------------------------------------------------------------

TINDER_FIXTURE = """
<article data-profile-id="tndr-abc123">
  <h2>Jane, 28</h2>
  <p>Loves hiking and dogs. Coffee snob.</p>
  <img data-order="0" src="https://images.tinder.com/a.jpg" />
  <img data-order="1" src="https://images.tinder.com/b.jpg" />
</article>
""".strip()


def test_tinder_parse_profile() -> None:
    adapter = TinderAdapter(FakeSwipedStore())
    profile = adapter._parse_profile(TINDER_FIXTURE)
    assert profile.app_id == "tinder"
    assert profile.external_id == "tndr-abc123"
    assert profile.bio_text == "Loves hiking and dogs. Coffee snob."
    assert profile.metadata["name_age"] == "Jane, 28"
    assert [p.url for p in profile.photos] == [
        "https://images.tinder.com/a.jpg",
        "https://images.tinder.com/b.jpg",
    ]
    assert [p.order_index for p in profile.photos] == [0, 1]


def test_tinder_parse_profile_missing_id_raises() -> None:
    adapter = TinderAdapter(FakeSwipedStore())
    with pytest.raises(ProfileParseError):
        adapter._parse_profile("<article><p>no id here</p></article>")


def test_tinder_parse_profile_malformed_markup_raises() -> None:
    adapter = TinderAdapter(FakeSwipedStore())
    with pytest.raises(ProfileParseError):
        adapter._parse_profile("<article data-profile-id='x'><p>unclosed</article>")


# -- Bumble ------------------------------------------------------------------

BUMBLE_FIXTURE = """
<section data-user-id="bmbl_777">
  <h2>Alex, 31</h2>
  <p>Backpacker. Trivia night regular.</p>
  <img data-index="0" src="https://bumble.example/img1.jpg" />
  <img data-index="1" src="https://bumble.example/img2.jpg" />
</section>
""".strip()


def test_bumble_parse_profile() -> None:
    adapter = BumbleAdapter(FakeSwipedStore())
    profile = adapter._parse_profile(BUMBLE_FIXTURE)
    assert profile.app_id == "bumble"
    assert profile.external_id == "bmbl_777"
    assert profile.bio_text == "Backpacker. Trivia night regular."
    assert profile.metadata["name_age"] == "Alex, 31"
    assert [p.url for p in profile.photos] == [
        "https://bumble.example/img1.jpg",
        "https://bumble.example/img2.jpg",
    ]
    assert [p.order_index for p in profile.photos] == [0, 1]


def test_bumble_parse_profile_missing_id_raises() -> None:
    adapter = BumbleAdapter(FakeSwipedStore())
    with pytest.raises(ProfileParseError):
        adapter._parse_profile("<section><p>no id here</p></section>")


# -- Hinge (Appium UI tree, XML) ---------------------------------------------

HINGE_FIXTURE = """
<android.widget.FrameLayout resource-id="co.hinge.app:id/profile_card" content-desc="hnge-555">
  <android.widget.TextView resource-id="co.hinge.app:id/prompt_text" text="Two truths and a lie: I once met a president." />
  <android.widget.ImageView resource-id="co.hinge.app:id/photo" index="0" content-desc="https://hinge.example/p0.jpg" />
  <android.widget.ImageView resource-id="co.hinge.app:id/photo" index="1" content-desc="https://hinge.example/p1.jpg" />
</android.widget.FrameLayout>
""".strip()


def test_hinge_parse_profile() -> None:
    adapter = HingeAdapter(FakeSwipedStore())
    profile = adapter._parse_profile(HINGE_FIXTURE)
    assert profile.app_id == "hinge"
    assert profile.external_id == "hnge-555"
    assert profile.bio_text == "Two truths and a lie: I once met a president."
    assert [p.url for p in profile.photos] == [
        "https://hinge.example/p0.jpg",
        "https://hinge.example/p1.jpg",
    ]
    assert [p.order_index for p in profile.photos] == [0, 1]


def test_hinge_parse_profile_missing_id_raises() -> None:
    adapter = HingeAdapter(FakeSwipedStore())
    with pytest.raises(ProfileParseError):
        adapter._parse_profile(
            '<android.widget.FrameLayout resource-id="co.hinge.app:id/profile_card" />'
        )


def test_hinge_parse_profile_malformed_markup_raises() -> None:
    adapter = HingeAdapter(FakeSwipedStore())
    with pytest.raises(ProfileParseError):
        adapter._parse_profile("<not><valid</not>")
