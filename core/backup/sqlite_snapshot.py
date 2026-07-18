"""Konzistentní kopie SQLite databáze přes online backup API."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SqliteSnapshotError(RuntimeError):
    """Chyba při vytváření nebo kontrole SQLite snapshotu."""


def sqlite_integrity_check(db_path: str | Path) -> str:
    """
    Spustí ``PRAGMA integrity_check`` a vrátí výsledek.

    Při úspěchu vrací ``\"ok\"``, jinak text chyb (zkrácený).
    """
    path = Path(db_path)
    if not path.is_file():
        raise SqliteSnapshotError(f"Databáze neexistuje: {path}")

    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    finally:
        connection.close()

    messages = [str(row[0]) for row in rows if row and row[0] is not None]
    if messages == ["ok"]:
        return "ok"
    if not messages:
        return "failed"
    joined = "; ".join(messages)
    if len(joined) > 500:
        return joined[:497] + "..."
    return joined


def read_sqlite_user_version(db_path: str | Path) -> str | None:
    """Vrátí ``PRAGMA user_version`` jako řetězec, nebo ``None`` pokud je 0 / nedostupné."""
    path = Path(db_path)
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            value = connection.execute("PRAGMA user_version").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return None
    if not value:
        return None
    version = int(value[0])
    if version <= 0:
        return None
    return str(version)


def create_sqlite_snapshot(
    source_db: str | Path,
    destination_db: str | Path,
    *,
    pages_per_step: int = 100,
) -> str:
    """
    Vytvoří konzistentní kopii databáze přes ``sqlite3.Connection.backup``.

    Nepoužívá obyčejné ``copy`` / ``shutil.copy2`` živého souboru.

    Returns:
        Výsledek ``integrity_check`` na cílové kopii (``\"ok\"`` nebo popis chyby).
    """
    source = Path(source_db)
    destination = Path(destination_db)

    if not source.is_file():
        raise SqliteSnapshotError(f"Zdrojová databáze neexistuje: {source}")
    if pages_per_step < 1:
        raise ValueError("pages_per_step musí být >= 1")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    source_conn: sqlite3.Connection | None = None
    dest_conn: sqlite3.Connection | None = None
    try:
        source_conn = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(str(destination.resolve()))
        source_conn.backup(dest_conn, pages=pages_per_step)
    except sqlite3.Error as exc:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise SqliteSnapshotError(f"SQLite backup API selhalo: {exc}") from exc
    finally:
        if dest_conn is not None:
            dest_conn.close()
        if source_conn is not None:
            source_conn.close()

    integrity = sqlite_integrity_check(destination)
    if integrity != "ok":
        destination.unlink(missing_ok=True)
        raise SqliteSnapshotError(
            f"Snapshot neprošel integrity_check: {integrity}"
        )
    return integrity
