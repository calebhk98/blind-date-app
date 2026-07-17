"""Christian Mingle adapter (scaffold -- NOT implemented).

Signup / login: https://login.christianmingle.com/
Backend: web
Notes: Christian-focused dating site. Free signup, premium for messaging. Traditional web + app.

TODO: implement the hooks and move to backend/adapters/ + register.
"""
from __future__ import annotations

from backend.adapters.web_base import WebBackendAdapter, SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://login.christianmingle.com/"


class ChristianMingleAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("christian_mingle", swiped_store)

    def _login_impl(self) -> None:
        raise NotImplementedError("Christian Mingle adapter not implemented yet")

    def _fetch_raw(self) -> list[str]:
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str) -> str:
        raise NotImplementedError

    def _parse_profile(self, raw: str) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
