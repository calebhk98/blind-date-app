"""TinderAdapter (design doc §3.2, GitHub issue #8).

Tinder is a web app, so it's driven via Playwright (``WebBackendAdapter``).
All selectors are module constants so a DOM change only ever touches this
file (design doc §4). None of these have been checked against the live
site -- see the ``# TODO: verify against live Tinder DOM`` markers below.
"""

from __future__ import annotations

from backend.adapters.base import SwipeDir
from backend.adapters.registry import register
from backend.adapters.web_base import ProfileParseError, SwipedStore, WebBackendAdapter, parse_xhtml_fragment
from backend.config import CONFIG
from backend.domain.types import RawPhoto, RawProfile

# TODO: verify against live Tinder DOM -- best-guess selectors, not confirmed
# live. Card markup is assumed to already be well-formed XHTML as extracted
# via Playwright's eval_on_selector_all (outerHTML); if that assumption
# breaks, adjust _fetch_raw/_fetch_detail_raw to extract structured JSON
# instead of raw markup.
TINDER_LOGIN_URL = "https://tinder.com/app/login"
TINDER_FEED_URL = "https://tinder.com/app/recs"
TINDER_CARD_SELECTOR = "article.Tinder-card"
TINDER_CARD_TAG = "article"
TINDER_NAME_TAG = "h2"
TINDER_BIO_TAG = "p"
TINDER_PHOTO_TAG = "img"
TINDER_PHOTO_ORDER_ATTR = "data-order"
TINDER_PROFILE_ID_ATTR = "data-profile-id"
TINDER_LIKE_BUTTON_SELECTOR = "button.Tinder-like"
TINDER_PASS_BUTTON_SELECTOR = "button.Tinder-pass"


class TinderAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("tinder", swiped_store)

    def _login_impl(self) -> None:
        context = self._ensure_context()
        page = context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        # TODO: verify against live Tinder DOM -- real login is likely an
        # interactive phone-number/OTP or OAuth flow. This assumes the
        # persistent session context (see WebBackendAdapter.session_dir) is
        # already authenticated and just confirms the feed renders.
        page.goto(TINDER_LOGIN_URL, timeout=timeout_ms)
        page.wait_for_selector(TINDER_CARD_SELECTOR, timeout=timeout_ms)

    def _fetch_raw(self) -> list[str]:
        context = self._ensure_context()
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        page.goto(TINDER_FEED_URL, timeout=timeout_ms)
        html_list = page.eval_on_selector_all(TINDER_CARD_SELECTOR, "els => els.map(e => e.outerHTML)")
        return [str(html) for html in html_list]

    def _fetch_detail_raw(self, profile_id: str) -> str:
        context = self._ensure_context()
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        page.goto(f"{TINDER_FEED_URL}/{profile_id}", timeout=timeout_ms)
        return str(page.eval_on_selector(TINDER_CARD_SELECTOR, "el => el.outerHTML"))

    def _parse_profile(self, raw: str) -> RawProfile:
        root = parse_xhtml_fragment(raw)
        profile_id = root.get(TINDER_PROFILE_ID_ATTR)
        if not profile_id:
            raise ProfileParseError(f"Tinder card missing {TINDER_PROFILE_ID_ATTR!r} attribute")
        bio_el = root.find(f".//{TINDER_BIO_TAG}")
        bio_text = (bio_el.text or "").strip() if bio_el is not None else ""
        name_el = root.find(f".//{TINDER_NAME_TAG}")
        name_age = (name_el.text or "").strip() if name_el is not None else ""
        photos = sorted(
            (
                RawPhoto(order_index=int(img.get(TINDER_PHOTO_ORDER_ATTR, i)), url=img.get("src"))
                for i, img in enumerate(root.findall(f".//{TINDER_PHOTO_TAG}"))
            ),
            key=lambda photo: photo.order_index,
        )
        return RawProfile(
            app_id=self.app_id,
            external_id=profile_id,
            bio_text=bio_text,
            photos=photos,
            metadata={"name_age": name_age},
        )

    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        context = self._ensure_context()
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        selector = TINDER_LIKE_BUTTON_SELECTOR if direction == "yes" else TINDER_PASS_BUTTON_SELECTOR
        # TODO: verify against live Tinder DOM -- assumes the detail/card for
        # `profile_id` is already the active page.
        page.click(selector, timeout=timeout_ms)


register("tinder", TinderAdapter)
