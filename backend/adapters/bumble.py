"""BumbleAdapter (design doc §3.2, GitHub issue #9).

Bumble is a web app, so it's driven via Playwright (``WebBackendAdapter``).
All selectors are module constants so a DOM change only ever touches this
file (design doc §4). None of these have been checked against the live
site -- see the ``# TODO: verify against live Bumble DOM`` markers below.
"""

from __future__ import annotations

from backend.adapters.base import SwipeDir
from backend.adapters.registry import register
from backend.adapters.web_base import ProfileParseError, SwipedStore, WebBackendAdapter, parse_xhtml_fragment
from backend.config import CONFIG
from backend.domain.types import RawPhoto, RawProfile

# TODO: verify against live Bumble DOM -- best-guess selectors, not
# confirmed live. Card markup is assumed to already be well-formed XHTML as
# extracted via Playwright's eval_on_selector_all (outerHTML); if that
# assumption breaks, adjust _fetch_raw/_fetch_detail_raw to extract
# structured JSON instead of raw markup.
BUMBLE_LOGIN_URL = "https://bumble.com/app/login"
BUMBLE_FEED_URL = "https://bumble.com/app/encounters"
BUMBLE_CARD_SELECTOR = "section.bmbl-profile"
BUMBLE_CARD_TAG = "section"
BUMBLE_NAME_TAG = "h2"
BUMBLE_ABOUT_TAG = "p"
BUMBLE_PHOTO_TAG = "img"
BUMBLE_PHOTO_ORDER_ATTR = "data-index"
BUMBLE_USER_ID_ATTR = "data-user-id"
BUMBLE_LIKE_BUTTON_SELECTOR = "button.encounters-controls__like"
BUMBLE_PASS_BUTTON_SELECTOR = "button.encounters-controls__pass"


class BumbleAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("bumble", swiped_store)

    def _login_impl(self) -> None:
        context = self._ensure_context()
        page = context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        # TODO: verify against live Bumble DOM -- real login is likely an
        # interactive phone-number/OTP or Facebook OAuth flow. This assumes
        # the persistent session context is already authenticated and just
        # confirms the feed renders.
        page.goto(BUMBLE_LOGIN_URL, timeout=timeout_ms)
        page.wait_for_selector(BUMBLE_CARD_SELECTOR, timeout=timeout_ms)

    def _fetch_raw(self) -> list[str]:
        context = self._ensure_context()
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        page.goto(BUMBLE_FEED_URL, timeout=timeout_ms)
        html_list = page.eval_on_selector_all(BUMBLE_CARD_SELECTOR, "els => els.map(e => e.outerHTML)")
        return [str(html) for html in html_list]

    def _fetch_detail_raw(self, profile_id: str) -> str:
        context = self._ensure_context()
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = CONFIG.automation.page_timeout_seconds * 1000
        page.goto(f"{BUMBLE_FEED_URL}/{profile_id}", timeout=timeout_ms)
        return str(page.eval_on_selector(BUMBLE_CARD_SELECTOR, "el => el.outerHTML"))

    def _parse_profile(self, raw: str) -> RawProfile:
        root = parse_xhtml_fragment(raw)
        profile_id = root.get(BUMBLE_USER_ID_ATTR)
        if not profile_id:
            raise ProfileParseError(f"Bumble card missing {BUMBLE_USER_ID_ATTR!r} attribute")
        about_el = root.find(f".//{BUMBLE_ABOUT_TAG}")
        bio_text = (about_el.text or "").strip() if about_el is not None else ""
        name_el = root.find(f".//{BUMBLE_NAME_TAG}")
        name_age = (name_el.text or "").strip() if name_el is not None else ""
        photos = sorted(
            (
                RawPhoto(order_index=int(img.get(BUMBLE_PHOTO_ORDER_ATTR, i)), url=img.get("src"))
                for i, img in enumerate(root.findall(f".//{BUMBLE_PHOTO_TAG}"))
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
        selector = BUMBLE_LIKE_BUTTON_SELECTOR if direction == "yes" else BUMBLE_PASS_BUTTON_SELECTOR
        # TODO: verify against live Bumble DOM -- assumes the detail/card for
        # `profile_id` is already the active page.
        page.click(selector, timeout=timeout_ms)


register("bumble", BumbleAdapter)
