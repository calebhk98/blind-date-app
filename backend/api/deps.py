"""Shared FastAPI dependencies (design doc §4).

Deliberately import-light: only stdlib + ``backend.db.connection`` (itself
stdlib-only), so importing ``backend.api.main`` never requires torch /
playwright / Appium. The lazy-import boundary for those heavy deps lives in
each route handler's body, not here (see routes/*.py).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from backend.config import CONFIG
from backend.db.connection import connect


def get_db() -> Iterator[sqlite3.Connection]:
    """Yield a request-scoped SQLite connection at the configured DB path.

    Tests point this at a temp DB via
    ``app.dependency_overrides[get_db] = override`` rather than mutating
    global state.
    """
    conn = connect(CONFIG.storage.db_path)
    try:
        yield conn
    finally:
        conn.close()
