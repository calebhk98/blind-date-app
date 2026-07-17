"""The League adapter (scaffold -- NOT implemented).

Signup / login: https://www.theleague.com/join/
Backend: web
Notes: Approval/waitlist-based. Requires LinkedIn/Facebook connection. Intelligent matching.

TODO: implement the hooks and move to backend/adapters/ + register.
"""
from __future__ import annotations

from backend.adapters.web_base import WebBackendAdapter, SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://www.theleague.com/join/"


class TheLeagueAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("the_league", swiped_store)

    def _login_impl(self) -> None:
        raise NotImplementedError("The League adapter not implemented yet")

    def _fetch_raw(self) -> list[str]:
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str) -> str:
        raise NotImplementedError

    def _parse_profile(self, raw: str) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
