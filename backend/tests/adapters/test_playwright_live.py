"""Live-browser integration test for the web adapters.

Unlike the mocked parsing tests, this launches a REAL Chromium via Playwright
and drives the exact selector-extraction path ``_fetch_raw`` uses
(``eval_on_selector_all`` + ``XMLSerializer``), then feeds the browser-rendered
markup through the adapter's real ``_parse_profile``. It proves the web
automation path end-to-end without needing a live Tinder login.

Skipped automatically when Playwright or a usable Chromium binary isn't
present, so the suite still runs in minimal environments.
"""

from __future__ import annotations

import glob
import os

import pytest

from backend.adapters.tinder import TINDER_CARD_SELECTOR, TinderAdapter
from backend.config import CONFIG

playwright_api = pytest.importorskip("playwright.sync_api")


def _resolve_chromium() -> str | None:
    """Find a Chromium executable: config first, then a pre-installed one."""
    configured = CONFIG.automation.chromium_executable_path
    if configured and os.path.isfile(configured):
        return configured
    for pattern in (
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        "/opt/pw-browsers/chromium-*/chrome-linux/headless_shell",
    ):
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    return None


class _FakeSwipedStore:
    def is_swiped(self, profile_id: str) -> bool:
        return False

    def mark_swiped(self, profile_id: str) -> None:
        pass


# A page whose <article> matches the adapter's real card selector. Note the
# void <img> is written HTML-style (unclosed) on purpose -- the browser renders
# it and XMLSerializer produces well-formed XHTML the parser can consume.
_LIVE_PAGE = """
<html><body>
  <article class="Tinder-card" data-profile-id="tndr-live-1">
    <h2>Riley, 31</h2>
    <p>Real browser bio: climbing and espresso.</p>
    <img data-order="0" src="https://images.tinder.com/live-a.jpg">
    <img data-order="1" src="https://images.tinder.com/live-b.jpg">
  </article>
</body></html>
"""


def test_tinder_parse_against_real_browser() -> None:
    chromium = _resolve_chromium()
    if chromium is None:
        pytest.skip("no Chromium binary available for a live browser test")

    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium, headless=True)
        page = browser.new_page()
        page.set_content(_LIVE_PAGE)
        # Exactly what _fetch_raw does: serialize matched cards to XHTML.
        cards = page.eval_on_selector_all(
            TINDER_CARD_SELECTOR, "els => els.map(e => new XMLSerializer().serializeToString(e))"
        )
        browser.close()

    assert len(cards) == 1
    profile = TinderAdapter(_FakeSwipedStore())._parse_profile(cards[0])
    assert profile.external_id == "tndr-live-1"
    assert profile.bio_text == "Real browser bio: climbing and espresso."
    assert [photo.url for photo in profile.photos] == [
        "https://images.tinder.com/live-a.jpg",
        "https://images.tinder.com/live-b.jpg",
    ]
