"""Záloha před první migrací existující databáze na schéma 4.1.3.

Použije stejný předmigrační balíček ``*.mbbackup`` jako ostatní přechody.
SQLite backup API uloží konzistentní kopii. Původní soubor databáze zůstává
na svém místě. Další start hotovou zálohu nepřepíše.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Callable

from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    allocate_pre_migration_backup_path,
    create_verified_pre_migration_backup,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_in_progress,
    read_migration_state,
)

logger = logging.getLogger(__name__)

TRANSITION_ID = "4.1.2-to-4.1.3"
_THP_COLUMNS = (
    "personal_number",
    "workplace_id",
    "is_thp",
    "may_examine",
    "updated_at",
)
_EXAM_TABLES = (
    "test_exams",
    "test_exam_examiners",
    "test_exam_validity_tracking",
)
_VALIDITY_IDENTITY = ("employee_source", "employee_id", "test_definition_id")

MigrateFn = Callable[[], None]


def needs_employee_central_413_schema(db_path: Path) -> bool:
    """True, pokud existující soubor ještě nemá schéma centrální evidence 4.1.3."""
    path = Path(db_path)
    if not path.is_file():
        return False
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        tables = _table_names(connection)
        if "thp_workers" in tables:
            columns = _column_names(connection, "thp_workers")
            if any(column not in columns for column in _THP_COLUMNS):
                return True
            if "thp_worker_roles" not in tables:
                return True
        if "test_employees" in tables and "test_employee_central_links" not in tables:
            return True
        for table_name in _EXAM_TABLES:
            if table_name not in tables:
                continue
            if "employee_source" not in _column_names(connection, table_name):
                return True
            if _employee_fk_targets_test_employees(connection, table_name):
                return True
        if "test_exam_validity_tracking" in tables and not _validity_identity_is_current(
            connection
        ):
            return True
        return False
    finally:
        connection.close()


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_employee_central_413_schema(path)


def guard_employee_central_413_migration(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None,
    migrate: MigrateFn,
) -> Path | None:
    """Před migrací staré databáze vytvoří ověřenou zálohu a teprve potom migruje.

    Čistá instalace a databáze, která schéma 4.1.3 už má, zálohu nevytváří.
    Selhání zálohy migraci nespustí. Nedokončený přechod další start zastaví,
    aby se záloha nepřepsala a migrace nepokračovala na rozdělaných datech.
    """
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace databáze na verzi 4.1.3 nebyla dokončena.\n\n"
            "Aplikace nespustí další změnu schématu a zálohu nepřepíše.\n"
            "Obnovte data z předmigrační zálohy.\n\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if not database_path.is_file() or not needs_employee_central_413_schema(
        database_path
    ):
        migrate()
        _mark_complete_when_schema_is_present(workspace_root, database_path)
        return None

    backups_dir = workspace_root / "zalohy"
    target = allocate_pre_migration_backup_path(
        backups_dir,
        transition_id=TRANSITION_ID,
    )
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise PreMigrationBackupError(
            "Před změnou databáze na verzi 4.1.3 se nepodařilo vytvořit "
            "nebo ověřit zálohu. Migrace nebyla spuštěna a původní databáze "
            "zůstala na svém místě beze změny.\n\n"
            f"{exc}"
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        migrate()
    except MigrationGuardError:
        raise
    except Exception as exc:
        raise MigrationGuardError(
            "Migrace databáze na verzi 4.1.3 selhala.\n\n"
            "Další spuštění zálohu nepřepíše a v migraci nebude pokračovat. "
            "Obnovte data z předmigrační zálohy.\n\n"
            f"Záloha: {backup_path}\n"
            f"Detail: {exc}"
        ) from exc

    if not schema_is_present(database_path):
        raise MigrationGuardError(
            "Migrace databáze na verzi 4.1.3 schéma nedokončila.\n\n"
            "Další spuštění zálohu nepřepíše a v migraci nebude pokračovat. "
            "Obnovte data z předmigrační zálohy.\n\n"
            f"Záloha: {backup_path}"
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "Migrace 4.1.3: schéma je hotové, předmigrační záloha %s",
        backup_path,
    )
    return backup_path


def _mark_complete_when_schema_is_present(
    workspace_root: Path,
    database_path: Path,
) -> None:
    if is_transition_complete(workspace_root, TRANSITION_ID):
        return
    if not schema_is_present(database_path):
        return
    mark_migration_complete(
        workspace_root,
        backup_path=None,
        transition_id=TRANSITION_ID,
    )


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return {str(row[1]) for row in rows}


def _employee_fk_targets_test_employees(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    rows = connection.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
    return any(
        str(row[3]) == "employee_id" and str(row[2]) == "test_employees" for row in rows
    )


def _validity_identity_is_current(connection: sqlite3.Connection) -> bool:
    if "employee_source" not in _column_names(connection, "test_exam_validity_tracking"):
        return False
    if _employee_fk_targets_test_employees(connection, "test_exam_validity_tracking"):
        return False
    indexes = connection.execute(
        'PRAGMA index_list("test_exam_validity_tracking")'
    ).fetchall()
    unique_keys: list[tuple[str, ...]] = []
    for index in indexes:
        if int(index[2]) != 1:
            continue
        info = connection.execute(f'PRAGMA index_info("{index[1]}")').fetchall()
        columns = tuple(str(row[2]) for row in info)
        if columns == ("id",):
            continue
        unique_keys.append(columns)
    return unique_keys == [_VALIDITY_IDENTITY]
