"""Migration runner (design doc §6).

Applies every ``.sql`` file in ``backend/db/migrations`` that has not yet been
recorded in the ``schema_version`` table, in filename order. Each migration
runs inside its own transaction (commit on success, rollback on any error --
see ``backend.db.connection.transaction``). Safe to re-run: already-applied
migrations are skipped.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from backend.db.connection import connect, transaction

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_FILENAME_RE = re.compile(r"^(\d+)_.*\.sql$")


def _migration_files() -> list[tuple[int, Path]]:
    """All migration files under ``MIGRATIONS_DIR``, sorted by version number."""
    files: list[tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = _FILENAME_RE.match(path.name)
        if match is None:
            raise ValueError(f"Migration filename does not match NNNN_name.sql: {path.name}")
        files.append((int(match.group(1)), path))
    files.sort(key=lambda item: item[0])
    return files


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Versions already recorded in ``schema_version``.

    ``schema_version`` itself is created by migration 0001, so before that has
    ever run the table won't exist yet -- treat that as "nothing applied" (do
    not pre-create the table here, or 0001's own ``CREATE TABLE
    schema_version`` would fail on the duplicate).
    """
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if table_exists is None:
        return set()
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return {row[0] for row in rows}


def _split_statements(sql: str) -> list[str]:
    """Split a migration file into individual statements on ';'.

    Deliberately naive (no string-literal-aware parsing): fine for DDL-only
    migrations with no semicolons inside quoted values. ``sqlite3.executescript``
    is avoided on purpose -- it issues an implicit COMMIT of any pending
    transaction before it runs, which silently breaks the atomicity a
    migration needs (a failed statement would leave earlier CREATE TABLEs
    committed instead of rolled back).
    """
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every not-yet-applied migration, in order. Returns the list of
    newly-applied version numbers (empty list if nothing was pending)."""
    already_applied = _applied_versions(conn)

    applied_now: list[int] = []
    for version, path in _migration_files():
        if version in already_applied:
            continue
        statements = _split_statements(path.read_text())
        conn.execute("BEGIN")
        with transaction(conn):
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) "
                "VALUES (?, CURRENT_TIMESTAMP)",
                (version,),
            )
        applied_now.append(version)

    return applied_now


def main() -> None:
    conn = connect()
    try:
        applied = apply_migrations(conn)
        if applied:
            print(f"Applied migrations: {applied}")
        else:
            print("No pending migrations.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
