"""Shared idempotent-swipe template and generic fetch/parse plumbing.

``WebBackendAdapter`` (web_base.py) and ``AppiumBackendAdapter``
(appium_base.py) are structurally the same adapter shape driven by two
different automation backends (design doc §3.2): only the browser-vs-driver
lifecycle differs. Everything else -- the idempotent swipe rule (design doc
§4), retry-with-backoff, and the fetch -> parse pipeline -- lives here
exactly once, so the two backends can never drift apart on the
no-double-swipe rule.

``backend/adapters/base.py`` is the read-only ``DatingAppAdapter`` Protocol
contract. This module is *not* part of that contract; it is private
implementation shared by the two concrete bases and must not be imported
from app adapters directly (go through ``web_base``/``appium_base``).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

from backend.adapters.base import SwipeDir
from backend.config import CONFIG
from backend.domain.types import RawProfile

T = TypeVar("T")


class ProfileParseError(RuntimeError):
    """Raised when an app-specific parser cannot build a valid RawProfile.

    Fail loud (design doc §4): adapters must never return a half-populated
    RawProfile. They raise this (or let ``RawProfile.__post_init__``'s own
    ``ValueError`` propagate) instead of guessing at missing fields.
    """


@runtime_checkable
class SwipedStore(Protocol):
    """Swiped-state persistence, injected so tests can use an in-memory fake
    and real adapters use a SQLite-backed store (see backend/db/connection.py).
    """

    def is_swiped(self, profile_id: str) -> bool: ...

    def mark_swiped(self, profile_id: str) -> None: ...


class _CommonAdapterBase(ABC):
    """Everything generic to *any* automation backend (design doc §3.1/§4):
    idempotent swipe, retry-with-backoff, and the fetch -> parse pipeline.

    ``WebBackendAdapter`` and ``AppiumBackendAdapter`` add only the
    browser/driver-lifecycle plumbing specific to their automation backend;
    they must not re-implement anything defined here (single source of
    truth, especially for the no-double-swipe rule).
    """

    app_id: str

    def __init__(self, app_id: str, swiped_store: SwipedStore) -> None:
        self.app_id = app_id
        self._swiped_store = swiped_store

    # -- DatingAppAdapter protocol -------------------------------------

    def login(self) -> None:
        self._with_retry(self._login_impl)

    def fetch_new_profiles(self, limit: int) -> list[RawProfile]:
        raw_items = self._with_retry(self._fetch_raw)
        return self._parse_profiles(raw_items)[:limit]

    def swipe(self, profile_id: str, direction: SwipeDir) -> None:
        """Idempotent swipe (design doc §4): a duplicate call is a no-op.

        The store is only marked *after* a successful ``_do_swipe``, so a
        crash mid-swipe leaves the profile retryable instead of falsely
        marked done.
        """
        if self._swiped_store.is_swiped(profile_id):
            return
        self._do_swipe(profile_id, direction)
        self._swiped_store.mark_swiped(profile_id)

    def get_profile_detail(self, profile_id: str) -> RawProfile:
        raw = self._with_retry(lambda: self._fetch_detail_raw(profile_id))
        return self._parse_profile(raw)

    # -- generic helpers -------------------------------------------------

    def _with_retry(self, fn: Callable[[], T]) -> T:
        """Call ``fn``, retrying with exponential backoff per
        ``CONFIG.automation``. Fails loud: once retries are exhausted the
        last exception propagates -- never swallowed.
        """
        max_retries = CONFIG.automation.max_retries
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - re-raised below, never swallowed
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(CONFIG.automation.retry_backoff_seconds * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def _parse_profiles(self, raw_items: Sequence[Any]) -> list[RawProfile]:
        """Parse every raw fetched item via the app-specific hook.

        A single malformed item raises (fail loud) rather than being
        dropped or emitted as a half-populated RawProfile.
        """
        return [self._parse_profile(raw) for raw in raw_items]

    # -- abstract hooks: implemented per app -----------------------------

    @abstractmethod
    def _login_impl(self) -> None:
        """Perform the app-specific login/session-restore flow."""

    @abstractmethod
    def _fetch_raw(self) -> Sequence[Any]:
        """Fetch the raw feed; return one opaque item per profile card."""

    @abstractmethod
    def _fetch_detail_raw(self, profile_id: str) -> Any:
        """Fetch the raw detail payload for a single profile."""

    @abstractmethod
    def _parse_profile(self, raw: Any) -> RawProfile:
        """Translate one raw item into a RawProfile.

        Must raise (typically ``ProfileParseError``) rather than return a
        half-populated RawProfile.
        """

    @abstractmethod
    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        """Perform the app-specific swipe action. Must raise on failure."""
