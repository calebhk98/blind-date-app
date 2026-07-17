"""Test-only doubles shared by test_api.py / test_services.py.

Not a pytest test module itself (no ``test_`` prefix) -- a plain helper.
``FakeAdapter`` is a minimal ``DatingAppAdapter`` double (design doc §3.1)
registered under ``FAKE_APP_ID`` so services/routes can be exercised without
Playwright/Appium ever starting a real browser/driver.
"""

from __future__ import annotations

from backend.adapters.registry import ADAPTERS, register
from backend.domain.types import RawProfile

FAKE_APP_ID = "fakeapp"


class FakeAdapter:
    """Configure via the class-level ``NEXT_PROFILES`` list; inspect calls
    via ``LOGIN_CALLS`` / ``SWIPE_CALLS``. ``reset_fake_adapter()`` clears all
    three -- call it at the top of every test that uses this fake.

    Mirrors the real adapters' own idempotent-swipe contract (design doc
    §3.1/§4: ``swipe`` must be idempotent) via the injected ``swiped_store``,
    so it behaves like the real thing even if a caller's own idempotency
    check were ever bypassed.
    """

    app_id = FAKE_APP_ID

    LOGIN_CALLS: list[None] = []
    SWIPE_CALLS: list[tuple[str, str]] = []
    NEXT_PROFILES: list[RawProfile] = []

    def __init__(self, swiped_store: object) -> None:
        self._swiped_store = swiped_store

    def login(self) -> None:
        type(self).LOGIN_CALLS.append(None)

    def fetch_new_profiles(self, limit: int) -> list[RawProfile]:
        return list(type(self).NEXT_PROFILES)[:limit]

    def swipe(self, profile_id: str, direction: str) -> None:
        if self._swiped_store.is_swiped(profile_id):
            return
        type(self).SWIPE_CALLS.append((profile_id, direction))
        self._swiped_store.mark_swiped(profile_id)

    def get_profile_detail(self, profile_id: str) -> RawProfile:
        for profile in type(self).NEXT_PROFILES:
            if profile.external_id == profile_id:
                return profile
        raise KeyError(profile_id)


def register_fake_adapter() -> None:
    """Idempotent: registering the same class twice is a harmless no-op
    (see ``backend.adapters.registry.register``); only raises on a
    conflicting *different* class for the same app_id."""
    if ADAPTERS.get(FAKE_APP_ID) is None:
        register(FAKE_APP_ID, FakeAdapter)


def reset_fake_adapter() -> None:
    FakeAdapter.LOGIN_CALLS.clear()
    FakeAdapter.SWIPE_CALLS.clear()
    FakeAdapter.NEXT_PROFILES = []
