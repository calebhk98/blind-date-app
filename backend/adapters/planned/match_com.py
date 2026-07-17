"""Match.com adapter (scaffold -- NOT implemented).

Signup / login: https://www.match.com/login
Backend: web
Notes: Full-featured web platform. Email/password or social auth.

TODO: implement the hooks and move to backend/adapters/ + register (see
backend/adapters/DATING_APPS.md). Open/Closed: one new file per app.
"""
from __future__ import annotations

from backend.adapters.web_base import WebBackendAdapter
from backend.adapters._shared import SwipedStore
from backend.domain.types import RawProfile

SIGNUP_URL = "https://www.match.com/login"


class MatchComAdapter(WebBackendAdapter):
    def __init__(self, swiped_store: SwipedStore) -> None:
        super().__init__("match_com", swiped_store)

    def _login_impl(self) -> None:
        raise NotImplementedError("Match.com adapter not implemented yet")

    def _fetch_raw(self):
        raise NotImplementedError

    def _fetch_detail_raw(self, profile_id: str):
        raise NotImplementedError

    def _parse_profile(self, raw) -> RawProfile:
        raise NotImplementedError

    def _do_swipe(self, profile_id: str, direction) -> None:
        raise NotImplementedError
