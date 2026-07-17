"""Facebook Dating adapter (scaffold -- NOT implemented).

Signup / login: https://www.facebook.com/dating
Backend: web
Notes: Feature within Facebook. Browser-accessible. Requires 30+ day old Facebook account.

TODO: implement the hooks and move to backend/adapters/ + register.
"""
from __future__ import annotations

from backend.adapters.web_base import WebBackendAdapter, SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://www.facebook.com/dating"


class FacebookDatingAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("facebook_dating", swiped_store)

    def _login_impl(self) -> None:
        raise NotImplementedError("Facebook Dating adapter not implemented yet")

    def _fetch_raw(self) -> list[str]:
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str) -> str:
        raise NotImplementedError

    def _parse_profile(self, raw: str) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
