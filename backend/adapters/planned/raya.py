"""Raya adapter (scaffold -- NOT implemented).

Signup / login: https://www.rayatheapp.com/
Backend: appium
Notes: Invite/approval-only, ~8% acceptance rate. iOS app only. Private membership community.

TODO: implement the hooks and move to backend/adapters/ + register.
"""
from __future__ import annotations

from typing import Any

from backend.adapters.appium_base import AppiumBackendAdapter, ProfileParseError, SwipedStore
from backend.adapters.base import SwipeDir
from backend.domain.types import RawProfile

SIGNUP_URL = "https://www.rayatheapp.com/"


class RayaAdapter(AppiumBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("raya", swiped_store)

    def _capabilities(self) -> dict[str, Any]:
        raise NotImplementedError("Raya adapter not implemented yet")

    def _login_impl(self) -> None:
        raise NotImplementedError("Raya adapter not implemented yet")

    def _fetch_raw(self) -> list[str]:
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str) -> str:
        raise NotImplementedError

    def _parse_profile(self, raw: str) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        raise NotImplementedError
