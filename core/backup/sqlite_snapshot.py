"""Konzistentní kopie SQLite databáze přes online backup API."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SqliteSnapshotError(RuntimeError):
    """Chyba při vytváření nebo kontrole SQLite snapshotu."""


def _pragma_check_result(db_path: Path, pragma: str) -> str:
    try:
        connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        try:
            rows = connection.execute(pragma).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return f"error: {exc}"

    messages = [str(row[0]) for row in rows if row and row[0] is not None]
    if messages == ["ok"]:
        return "ok"
    if not messages:
        return "failed"
    joined = "; ".join(messages)
    if len(joined) > 500:
        return joined[:497] + "..."
    return joined


def sqlite_integrity_check(db_path: str | Path) -> str:
    """
    Spustí ``PRAGMA integrity_check`` a vrátí výsledek.

    Při úspěchu vrací ``\"ok\"``, jinak text chyb (zkrácený).
    """
    path = Path(db_path)
    if not path.is_file():
        raise SqliteSnapshotError(f"Databáze neexistuje: {path}")
    return _pragma_check_result(path, "PRAGMA integrity_check")


def sqlite_quick_check(db_path: str | Path) -> str:
    """Spustí ``PRAGMA quick_check`` (rychlejší kontrola)."""
    path = Path(db_path)
    if not path.is_file():
        raise SqliteSnapshotError(f"Databáze neexistuje: {path}")
    return _pragma_check_result(path, "PRAGMA quick_check")


def is_sqlite_database_empty(db_path: str | Path) -> bool:
    """
    True, pokud soubor chybí / má nulovou velikost, nebo nemá žádné uživatelské objekty
    v ``sqlite_master`` (kromě interních).
    """
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return True
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type IN ('table', 'index', 'view', 'trigger') "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return True
    return not row or int(row[0]) == 0


def inspect_sqlite_file(db_path: str | Path) -> dict[str, object]:
    """
    Souhrn kontrol SQLite souboru pro metadata / integrity report.

    Keys: size, empty, integrity_check, quick_check
    """
    path = Path(db_path)
    if not path.is_file():
        raise SqliteSnapshotError(f"Databáze neexistuje: {path}")

    size = path.stat().st_size
    empty = is_sqlite_database_empty(path)
    if size <= 0:
        return {
            "size": size,
            "empty": True,
            "integrity_check": "failed",
            "quick_check": "failed",
        }

    try:
        integrity = sqlite_integrity_check(path)
    except SqliteSnapshotError as exc:
        integrity = f"error: {exc}"
    try:
        quick = sqlite_quick_check(path)
    except SqliteSnapshotError as exc:
        quick = f"error: {exc}"

    return {
        "size": size,
        "empty": empty,
        "integrity_check": integrity,
        "quick_check": quick,
    }


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
