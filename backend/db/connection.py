"""SQLite connection helper (design doc §5, §6).

Single place that opens the database so foreign-key enforcement and row access
are configured consistently. The DB path comes from ``config`` -- never
hardcoded.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from backend.config import CONFIG


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with FK enforcement and dict-like rows.

    ``db_path`` defaults to the configured location; pass ``":memory:"`` or a
    temp path in tests.
    """
    path = str(db_path) if db_path is not None else str(CONFIG.storage.db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # Fail loud rather than silently ignoring referential integrity (§4).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on any exception (never swallow)."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
