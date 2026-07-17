"""Taimi adapter (scaffold -- NOT implemented).

Signup / login: https://web.taimi.com/
Backend: web
Notes: LGBTQ+ dating app. Web version available. Social + dating features.

TODO: implement the hooks and move to backend/adapters/ + register.
"""
from __future__ import annotations

from backend.adapters.web_base import WebBackendAdapter, SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://web.taimi.com/"


class TaimiAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("taimi", swiped_store)

    def _login_impl(self) -> None:
        raise NotImplementedError("Taimi adapter not implemented yet")

    def _fetch_raw(self) -> list[str]:
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str) -> str:
        raise NotImplementedError

    def _parse_profile(self, raw: str) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
