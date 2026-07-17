"""Tests for the generic adapter base behaviour (design doc §4): idempotent
swipe and ``DatingAppAdapter`` Protocol conformance.

Uses a fake in-memory swiped-state store and a fake ``WebBackendAdapter``
subclass -- no real browser/driver is ever started, so these tests run with
no playwright installed.
"""

from __future__ import annotations

import pytest

from backend.adapters.base import DatingAppAdapter, SwipeDir
from backend.adapters.web_base import WebBackendAdapter
from backend.domain.types import RawProfile


class FakeSwipedStore:
    """In-memory ``SwipedStore`` stand-in for a SQLite-backed one."""

    def __init__(self) -> None:
        self._swiped: set[str] = set()

    def is_swiped(self, profile_id: str) -> bool:
        return profile_id in self._swiped

    def mark_swiped(self, profile_id: str) -> None:
        self._swiped.add(profile_id)


class FakeWebAdapter(WebBackendAdapter):
    """Minimal concrete adapter proving WebBackendAdapter's contract without
    ever touching Playwright."""

    def __init__(self, swiped_store: FakeSwipedStore) -> None:
        super().__init__("faketinder", swiped_store)
        self.do_swipe_calls: list[tuple[str, SwipeDir]] = []

    def _login_impl(self) -> None:
        pass

    def _fetch_raw(self) -> list[str]:
        return []

    def _fetch_detail_raw(self, profile_id: str) -> str:
        return profile_id

    def _parse_profile(self, raw: str) -> RawProfile:
        return RawProfile(app_id=self.app_id, external_id=raw, bio_text="")

    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        self.do_swipe_calls.append((profile_id, direction))


class ExplodingAdapter(FakeWebAdapter):
    """Adapter whose swipe action always fails, to prove the swiped-store is
    marked only after a successful `_do_swipe`."""

    def _do_swipe(self, profile_id: str, direction: SwipeDir) -> None:
        raise RuntimeError("boom")


@pytest.fixture
def store() -> FakeSwipedStore:
    return FakeSwipedStore()


@pytest.fixture
def adapter(store: FakeSwipedStore) -> FakeWebAdapter:
    return FakeWebAdapter(store)


def test_conforms_to_dating_app_adapter_protocol(adapter: FakeWebAdapter) -> None:
    assert isinstance(adapter, DatingAppAdapter)


def test_swipe_is_idempotent(adapter: FakeWebAdapter) -> None:
    adapter.swipe("profile-1", "yes")
    adapter.swipe("profile-1", "yes")
    assert adapter.do_swipe_calls == [("profile-1", "yes")]


def test_swipe_second_call_is_noop_even_with_different_direction(adapter: FakeWebAdapter) -> None:
    # Once marked swiped, a retry must not re-swipe at all -- not even to
    # "correct" the direction (design doc §4: no double-swipe).
    adapter.swipe("profile-1", "yes")
    adapter.swipe("profile-1", "no")
    assert adapter.do_swipe_calls == [("profile-1", "yes")]


def test_different_profiles_each_swiped_once(adapter: FakeWebAdapter) -> None:
    adapter.swipe("a", "yes")
    adapter.swipe("b", "no")
    adapter.swipe("a", "yes")
    assert adapter.do_swipe_calls == [("a", "yes"), ("b", "no")]


def test_swiped_store_marked_only_after_successful_do_swipe(store: FakeSwipedStore) -> None:
    exploding = ExplodingAdapter(store)
    with pytest.raises(RuntimeError):
        exploding.swipe("profile-2", "no")
    assert store.is_swiped("profile-2") is False


def test_fetch_new_profiles_respects_limit(store: FakeSwipedStore) -> None:
    class MultiProfileAdapter(FakeWebAdapter):
        def _fetch_raw(self) -> list[str]:
            return ["a", "b", "c"]

    adapter = MultiProfileAdapter(store)
    profiles = adapter.fetch_new_profiles(limit=2)
    assert [p.external_id for p in profiles] == ["a", "b"]


def test_get_profile_detail_parses_via_fetch_detail_raw(adapter: FakeWebAdapter) -> None:
    profile = adapter.get_profile_detail("some-id")
    assert profile.external_id == "some-id"
    assert profile.app_id == "faketinder"
