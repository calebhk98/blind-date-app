"""Execute an approved swipe via the app's adapter (design doc §1, §4).

Swipes only ever happen after explicit user approval (design doc §1) --
nothing in this module decides *whether* to swipe, it only executes a swipe
for a profile that already has a ``final_decision``. Idempotent end-to-end:
``backend.db.repository.is_swiped`` is checked before the adapter is ever
touched, and the ``SwipedStore`` handed to the adapter (see
``_ScopedSwipedStore`` below) defers to that exact same persisted flag, so
the ``profiles.swiped`` row is the single source of swiped truth -- there is
no second, divergent copy of "have we swiped this" inside the adapter.

No app-specific branching (design doc §4): the adapter is always resolved
via ``backend.adapters.registry.get_adapter_class``.
"""

from __future__ import annotations

import sqlite3

from backend.domain.enums import Decision, SwipeDirection


class _ScopedSwipedStore:
    """Adapts ``backend.db.repository``'s ``conn`` + internal-``profile_id``
    calls to the per-adapter ``SwipedStore`` protocol
    (``backend/adapters/_shared.py``), bound to one already-resolved
    profile. The adapter's own idempotency check therefore reads the exact
    same ``profiles.swiped`` flag this module checks up front.
    """

    def __init__(self, conn: sqlite3.Connection, profile_id: str) -> None:
        self._conn = conn
        self._profile_id = profile_id

    def is_swiped(self, profile_id: str) -> bool:  # noqa: ARG002 - see class docstring
        from backend.db import repository

        return repository.is_swiped(self._conn, self._profile_id)

    def mark_swiped(self, profile_id: str) -> None:  # noqa: ARG002 - see class docstring
        from backend.db import repository

        repository.mark_swiped(self._conn, self._profile_id)


def approve(conn: sqlite3.Connection, profile_id: str) -> bool:
    """Execute the swipe for ``profile_id`` if it hasn't happened yet.

    Returns ``True`` if a swipe was actually executed on this call, ``False``
    if the profile was already swiped (idempotent no-op -- the adapter is
    never invoked a second time for the same profile).
    """
    from backend.db import repository

    if repository.is_swiped(conn, profile_id):
        return False

    profile = repository.get_profile(conn, profile_id)
    if profile is None:
        raise ValueError(f"unknown profile_id: {profile_id}")

    decision = Decision(profile["final_decision"])
    if decision == Decision.PENDING:
        raise ValueError(f"profile {profile_id} has no final decision yet; cannot swipe")

    direction = SwipeDirection.YES if decision == Decision.YES else SwipeDirection.NO

    from backend.adapters.registry import get_adapter_class

    adapter_cls = get_adapter_class(profile["app_id"])
    # DatingAppAdapter (backend/adapters/base.py, read-only contract) is a
    # structural Protocol with no declared __init__; every concrete adapter
    # actually requires a SwipedStore constructor arg (backend/adapters/
    # _shared.py::_CommonAdapterBase). mypy can't see that from the Protocol
    # alone -- this is a known typing gap in the given contract, not a bug.
    adapter = adapter_cls(_ScopedSwipedStore(conn, profile_id))  # type: ignore[call-arg]
    try:
        adapter.login()
        adapter.swipe(profile["external_id"], direction.value)
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()

    repository.mark_swiped(conn, profile_id)
    return True
