"""HingeAdapter (design doc §3.2, GitHub issue #10).

Hinge is a native app, so it's driven via Appium (``AppiumBackendAdapter``)
rather than Playwright. All locators are module constants so a UI change
only ever touches this file (design doc §4). None of these have been
checked against the live app -- see the
``# TODO: verify against live Hinge UI tree`` markers below.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from backend.adapters.appium_base import AppiumBackendAdapter, ProfileParseError, SwipedStore
from backend.adapters.base import SwipeDir
from backend.adapters.registry import register
from backend.config import CONFIG
from backend.domain.types import RawPhoto, RawProfile

# TODO: verify against live Hinge UI tree -- best-guess resource-ids, not
# confirmed live. `_fetch_raw`/`_fetch_detail_raw` assume each element's
# outer UI subtree can be read as XML text via `get_attribute("outerXML")`;
# if the live driver doesn't expose that (Appium page-source semantics vary
# by driver/version), fall back to `driver.page_source` and slice it.
HINGE_APP_PACKAGE = "co.hinge.app"
HINGE_CARD_RESOURCE_ID = "co.hinge.app:id/profile_card"
HINGE_PROMPT_RESOURCE_ID = "co.hinge.app:id/prompt_text"
HINGE_PHOTO_RESOURCE_ID = "co.hinge.app:id/photo"
HINGE_LIKE_RESOURCE_ID = "co.hinge.app:id/like_button"
HINGE_PASS_RESOURCE_ID = "co.hinge.app:id/pass_button"


class HingeAdapter(AppiumBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("hinge", swiped_store)

    def _capabilities(self) -> dict[str, Any]:
        return {
            "platformName": "Android",
            "appPackage": HINGE_APP_PACKAGE,
            "automationName": "UiAutomator2",
        }

    def _login_impl(self) -> None:
        driver = self._ensure_driver()
        # TODO: verify against live Hinge app -- real login is likely an
        # interactive phone-number/OTP or SSO flow. This assumes the
        # persisted app session is already authenticated and just waits for
        # the feed to be present.
        driver.implicitly_wait(CONFIG.automation.page_timeout_seconds)
        self._find("id", HINGE_CARD_RESOURCE_ID)

    def _fetch_raw(self) -> list[str]:
        driver = self._ensure_driver()
        cards = driver.find_elements("id", HINGE_CARD_RESOURCE_ID)
        return [str(card.get_attribute("outerXML")) for card in cards]

    def _fetch_detail_raw(self, profile_id: str) -> str:
        card = self._find("id", HINGE_CARD_RESOURCE_ID)
        return str(card.get_attribute("outerXML"))

    def _parse_profile(self, raw: str) -> RawProfile:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ProfileParseError(f"malformed Hinge UI tree: {exc}") from exc
        profile_id = root.get("content-desc")
        if not profile_id:
            raise ProfileParseError("Hinge card missing content-desc identity")
        prompt_el = _find_by_resource_id(root, HINGE_PROMPT_RESOURCE_ID)
        bio_text = prompt_el.get("text", "") if prompt_el is not None else ""
        photos = sorted(
            (
                RawPhoto(order_index=int(el.get("index", i)), url=el.get("content-desc"))
                for i, el in enumerate(_findall_by_resource_id(root, HINGE_PHOTO_RESOURCE_ID))
            ),
            key=lambda photo: photo.order_index,
        )
        return RawProfile(app_id=self.app_id, external_id=profile_id, bio_text=bio_text, photos=photos)

    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        # TODO: verify against live Hinge app -- assumes the detail card for
        # `profile_id` is already the active screen.
        resource_id = HINGE_LIKE_RESOURCE_ID if direction == "yes" else HINGE_PASS_RESOURCE_ID
        self._find("id", resource_id).click()


def _find_by_resource_id(root: ET.Element, resource_id: str) -> ET.Element | None:
    for el in root.iter():
        if el.get("resource-id") == resource_id:
            return el
    return None


def _findall_by_resource_id(root: ET.Element, resource_id: str) -> list[ET.Element]:
    return [el for el in root.iter() if el.get("resource-id") == resource_id]


register("hinge", HingeAdapter)
