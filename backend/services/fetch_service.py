"""Pull fresh profiles from an app adapter and persist them (design doc §3,
§4). Side-effecting: talks to the adapter (Playwright/Appium, resolved via
``backend.adapters.registry`` and imported lazily) and to
``backend.db.repository`` (also lazily imported). Saves photo bytes under
``CONFIG.storage.image_dir`` -- never a hardcoded path.

No app-specific branching (design doc §4): the adapter is always resolved
via ``backend.adapters.registry.get_adapter_class``.
"""

from __future__ import annotations

import sqlite3
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from backend.config import CONFIG
from backend.domain.types import RawPhoto, RawProfile


class _NullSwipedStore:
    """Adapter construction requires a ``SwipedStore`` (see
    ``backend/adapters/_shared.py``), but fetching never calls
    ``adapter.swipe()`` -- fetching profiles doesn't swipe them. This is an
    inert placeholder so fetch_service doesn't need a full external_id-keyed
    swipe store just to satisfy the constructor.
    """

    def is_swiped(self, profile_id: str) -> bool:  # noqa: ARG002
        return False

    def mark_swiped(self, profile_id: str) -> None:  # noqa: ARG002
        return None


def fetch_new_profiles(
    conn: sqlite3.Connection, app_id: str, limit: int | None = None
) -> list[str]:
    """Fetch up to ``limit`` new profiles for ``app_id`` via its adapter,
    persist profile + photo rows, and save photo bytes under
    ``CONFIG.storage.image_dir``. Returns the newly inserted profile_ids.
    """
    from backend.adapters.registry import get_adapter_class
    from backend.db import repository

    fetch_limit = limit if limit is not None else CONFIG.automation.default_fetch_limit
    adapter_cls = get_adapter_class(app_id)
    # See the matching comment in swipe_service.py: DatingAppAdapter is a
    # Protocol with no declared __init__, but every concrete adapter requires
    # a SwipedStore constructor arg -- known typing gap, not a bug.
    adapter = adapter_cls(_NullSwipedStore())  # type: ignore[call-arg]
    try:
        adapter.login()
        raw_profiles = adapter.fetch_new_profiles(fetch_limit)
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    return [_persist_profile(conn, repository, raw) for raw in raw_profiles]


def _persist_profile(conn: sqlite3.Connection, repository: Any, raw: RawProfile) -> str:
    profile_id = str(uuid.uuid4())
    repository.insert_profile(
        conn,
        profile_id=profile_id,
        app_id=raw.app_id,
        external_id=raw.external_id,
        bio_text=raw.bio_text,
        hard_filter_hit=_hard_filter_hit(raw),
    )
    for photo in raw.photos:
        _persist_photo(conn, repository, profile_id, photo)
    return profile_id


def _hard_filter_hit(raw: RawProfile) -> bool:  # noqa: ARG001 - see docstring
    """Whether ``raw`` trips the hard filter.

    No dedicated hard-filter pure-logic module exists yet (design doc §4
    reserves that as its own single-source-of-truth rule, analogous to
    ``logic/verdict.py``/``logic/decision.py``); ``RawProfile.metadata`` is
    deliberately opaque per-adapter data (see ``domain/types.py``), so the
    only safe, app-agnostic default here is "no hit" until that rule lands.
    """
    return False


def _persist_photo(conn: sqlite3.Connection, repository: Any, profile_id: str, photo: RawPhoto) -> None:
    photo_id = str(uuid.uuid4())
    file_path = _save_photo_bytes(profile_id, photo_id, photo)
    repository.insert_photo(
        conn,
        photo_id=photo_id,
        profile_id=profile_id,
        file_path=str(file_path),
        order_index=photo.order_index,
    )


def _save_photo_bytes(profile_id: str, photo_id: str, photo: RawPhoto) -> Path:
    CONFIG.storage.image_dir.mkdir(parents=True, exist_ok=True)
    dest = CONFIG.storage.image_dir / f"{photo_id}.jpg"
    if photo.image_bytes is not None:
        dest.write_bytes(photo.image_bytes)
    elif photo.url is not None:
        with urllib.request.urlopen(photo.url) as response:  # noqa: S310 - adapter-supplied URL
            dest.write_bytes(response.read())
    else:
        raise ValueError(
            f"RawPhoto (profile {profile_id}, order {photo.order_index}) has neither "
            "url nor image_bytes"
        )
    return dest
