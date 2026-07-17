"""The common adapter contract (design doc §3.1).

Every dating app -- whether automated via Playwright (web) or Appium (native) --
implements this Protocol, so the orchestrator can drive any app without knowing
which backend serves it. Concrete base classes (WebBackendAdapter,
AppiumBackendAdapter) live in sibling modules; app-specific subclasses each get
their own file so a UI change only ever breaks one adapter (§4).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from backend.domain.types import RawProfile

SwipeDir = Literal["yes", "no"]


@runtime_checkable
class DatingAppAdapter(Protocol):
    """Common contract implemented by every app adapter (design doc §3.1)."""

    #: Stable identifier for the app this adapter serves, e.g. "tinder".
    app_id: str

    def login(self) -> None:
        """Establish (or restore) an authenticated session."""
        ...

    def fetch_new_profiles(self, limit: int) -> list[RawProfile]:
        """Return up to ``limit`` freshly-surfaced profiles as RawProfile."""
        ...

    def swipe(self, profile_id: str, direction: SwipeDir) -> None:
        """Execute a single swipe. MUST be idempotent (design doc §4): a retry
        after a partial failure must not double-swipe or swipe the wrong way."""
        ...

    def get_profile_detail(self, profile_id: str) -> RawProfile:
        """Return the full detail for a single profile."""
        ...
