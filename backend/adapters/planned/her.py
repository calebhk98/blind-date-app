"""HER adapter (scaffold -- NOT implemented).

Signup / login: https://weareher.com/
Backend: appium
Notes: Mobile-app-only for LGBTQ+ women/non-binary people. iOS/Android via
Appium. Facebook or Instagram auth. No traditional web login UI.

TODO: implement the hooks and move to backend/adapters/ + register (see
backend/adapters/DATING_APPS.md). Open/Closed: one new file per app.
"""
from __future__ import annotations

from typing import Any

from backend.adapters.appium_base import AppiumBackendAdapter
from backend.adapters._shared import SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://weareher.com/"


class HERAdapter(AppiumBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("her", swiped_store)

    def _capabilities(self) -> dict[str, Any]:
        raise NotImplementedError("HER adapter not implemented yet")

    def _login_impl(self) -> None:
        raise NotImplementedError("HER adapter not implemented yet")

    def _fetch_raw(self):
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str):
        raise NotImplementedError

    def _parse_profile(self, raw) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
