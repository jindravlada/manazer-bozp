"""PROVERKY-PLANNED-SECTION-SUMMARY-MIGRATION-1: čisté plánované Prověrky.

Převádí pouze ``notes_mode IS NULL`` u skutečně čistých plánovaných Prověrek
na ``section-summary-v1``. Rozpracované a dokončené záznamy se nemění.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.backup.constants import BACKUP_EXTENSION
from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    create_verified_pre_migration_backup,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_failed,
    mark_migration_in_progress,
    read_migration_state,
    sqlite_table_exists,
)
from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_FINDING,
    ENTITY_INSPECTION,
    ENTITY_PROVERKY,
)
from core.shared.section_summary import NOTES_MODE_SECTION_SUMMARY_V1
from moduly.proverky.constants import INSPECTION_STATUS_PLANOVANO

logger = logging.getLogger(__name__)

TRANSITION_ID = "proverky-planned-section-summary-1"
BACKUP_NAME_PREFIX = "pre_proverky_planned_section_summary_"

SKIP_OTHER_STATUS = "jiny_stav"
SKIP_STARTED_FINISHED = "zahajena_ukoncena"
SKIP_RESULTS = "vysledky"
SKIP_COMMENTS = "komentare"
SKIP_PHOTOS = "fotografie"
SKIP_FINDINGS = "zjisteni"
SKIP_TASKS = "ukoly"
SKIP_ATTACHMENTS = "prilohy"
SKIP_OTHER_DATA = "jina_uzivatelska_data"

SKIP_REASON_ORDER = (
    SKIP_OTHER_STATUS,
    SKIP_STARTED_FINISHED,
    SKIP_RESULTS,
    SKIP_COMMENTS,
    SKIP_PHOTOS,
    SKIP_FINDINGS,
    SKIP_TASKS,
    SKIP_ATTACHMENTS,
    SKIP_OTHER_DATA,
)

_ATTACHMENT_TYPES = (ENTITY_PROVERKY, ENTITY_INSPECTION)
_FINDING_TYPES = (ENTITY_PROVERKY, ENTITY_INSPECTION)
_EMPTY_RESULTS = ("", CONTROL_RESULT_NEKONTROLOVANO)

_PLANNING_COLUMNS = (
    "number",
    "year",
    "planned_month",
    "inspection_date",
    "started_at",
    "finished_at",
    "status",
    "inspection_type",
    "workplace_id",
    "workplace_name",
    "title",
    "silne_stranky",
    "doporuceni_vedouciho",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True)
class PlannedSectionSummaryInventory:
    legacy_ids: tuple[int, ...]
    eligible_ids: tuple[int, ...]
    skipped: dict[int, str]
    skip_counts: dict[str, int]
    planning_snapshot: dict[int, tuple]
    query_count: int


@dataclass(frozen=True)
class PlannedSectionSummaryMigrationResult:
    migrated: bool
    converted_ids: tuple[int, ...] = ()
    skipped: dict[int, str] = field(default_factory=dict)
    pre_migration_backup_path: Path | None = None
    skipped_reason: str | None = None
    inventory: PlannedSectionSummaryInventory | None = None


def allocate_planned_section_summary_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    root = Path(backups_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{BACKUP_NAME_PREFIX}{stamp}{BACKUP_EXTENSION}"
    candidate = root / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = root / f"{BACKUP_NAME_PREFIX}{stamp}_{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise MigrationGuardError(
        "Nelze přidělit unikátní název zálohy "
        "PROVERKY-PLANNED-SECTION-SUMMARY-MIGRATION-1."
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(connection, table):
        return set()
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def needs_proverky_planned_section_summary_migration(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, "bozp_inspections"):
        return False
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        columns = _table_columns(connection, "bozp_inspections")
        return "notes_mode" in columns
    finally:
        connection.close()


def _placeholders(values: list) -> tuple[str, list]:
    return ",".join("?" * len(values)), list(values)


def _fetch_id_set(
    connection: sqlite3.Connection,
    sql: str,
    params: list,
    queries: list[str],
) -> set[int]:
    queries.append(sql)
    return {int(row[0]) for row in connection.execute(sql, params).fetchall() if row[0] is not None}


def collect_planned_section_summary_inventory(
    connection: sqlite3.Connection,
) -> PlannedSectionSummaryInventory:
    queries: list[str] = []
    columns = _table_columns(connection, "bozp_inspections")
    if "notes_mode" not in columns:
        return PlannedSectionSummaryInventory(
            legacy_ids=(),
            eligible_ids=(),
            skipped={},
            skip_counts={reason: 0 for reason in SKIP_REASON_ORDER},
            planning_snapshot={},
            query_count=len(queries),
        )

    planning_select = ", ".join(_PLANNING_COLUMNS)
    col_index = {name: index + 1 for index, name in enumerate(_PLANNING_COLUMNS)}
    sql = (
        f"SELECT id, {planning_select} FROM bozp_inspections "
        "WHERE notes_mode IS NULL"
    )
    queries.append(sql)
    rows = connection.execute(sql).fetchall()
    legacy_ids = tuple(int(row[0]) for row in rows)
    snapshots: dict[int, tuple] = {}
    conclusion_ids: set[int] = set()
    other_status_ids: set[int] = set()
    started_ids: set[int] = set()
    for row in rows:
        inspection_id = int(row[0])
        snapshots[inspection_id] = tuple(row[1:])
        status = str(row[col_index["status"]] or "")
        started_at = row[col_index["started_at"]]
        finished_at = row[col_index["finished_at"]]
        silne = str(row[col_index["silne_stranky"]] or "").strip()
        doporuceni = str(row[col_index["doporuceni_vedouciho"]] or "").strip()
        if status != INSPECTION_STATUS_PLANOVANO:
            other_status_ids.add(inspection_id)
        elif started_at is not None or finished_at is not None:
            started_ids.add(inspection_id)
        if silne or doporuceni:
            conclusion_ids.add(inspection_id)

    result_ids: set[int] = set()
    comment_ids: set[int] = set()
    photo_ids: set[int] = set()
    result_other_ids: set[int] = set()
    finding_ids: set[int] = set()
    task_ids: set[int] = set()
    attachment_ids: set[int] = set()
    summary_ids: set[int] = set()
    override_ids: set[int] = set()
    link_ids: set[int] = set()

    if legacy_ids:
        in_sql, in_params = _placeholders(list(legacy_ids))
        type_sql, type_params = _placeholders(list(_FINDING_TYPES))
        attach_sql, attach_params = _placeholders(list(_ATTACHMENT_TYPES))

        if _table_exists(connection, "control_results"):
            result_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM control_results "
                f"WHERE entity_type = ? AND entity_id IN ({in_sql}) "
                "AND TRIM(COALESCE(result, '')) NOT IN (?, ?)",
                [ENTITY_PROVERKY, *in_params, *_EMPTY_RESULTS],
                queries,
            )
            comment_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM control_results "
                f"WHERE entity_type = ? AND entity_id IN ({in_sql}) "
                "AND TRIM(COALESCE(note, '')) != ''",
                [ENTITY_PROVERKY, *in_params],
                queries,
            )
            photo_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM control_results "
                f"WHERE entity_type = ? AND entity_id IN ({in_sql}) "
                "AND TRIM(COALESCE(photo_path, '')) != ''",
                [ENTITY_PROVERKY, *in_params],
                queries,
            )
            result_other_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM control_results "
                f"WHERE entity_type = ? AND entity_id IN ({in_sql}) "
                "AND ("
                "COALESCE(shared_experience, 0) != 0 "
                "OR TRIM(COALESCE(recorded_by_name, '')) != ''"
                ")",
                [ENTITY_PROVERKY, *in_params],
                queries,
            )

        if _table_exists(connection, "findings"):
            finding_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM findings "
                f"WHERE entity_type IN ({type_sql}) AND entity_id IN ({in_sql})",
                [*type_params, *in_params],
                queries,
            )
            task_ids |= _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM findings "
                f"WHERE entity_type IN ({type_sql}) AND entity_id IN ({in_sql}) "
                "AND task_id IS NOT NULL",
                [*type_params, *in_params],
                queries,
            )
            if _table_exists(connection, "tasks"):
                task_ids |= _fetch_id_set(
                    connection,
                    "SELECT DISTINCT f.entity_id FROM findings AS f "
                    "INNER JOIN tasks AS t ON t.source_module = ? "
                    "AND t.source_record_id = f.id "
                    f"WHERE f.entity_type IN ({type_sql}) "
                    f"AND f.entity_id IN ({in_sql})",
                    [ENTITY_FINDING, *type_params, *in_params],
                    queries,
                )

        if _table_exists(connection, "tasks"):
            task_ids |= _fetch_id_set(
                connection,
                "SELECT DISTINCT source_record_id FROM tasks "
                f"WHERE source_module IN ({attach_sql}) "
                f"AND source_record_id IN ({in_sql})",
                [*attach_params, *in_params],
                queries,
            )

        if _table_exists(connection, "attachments"):
            attachment_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT entity_id FROM attachments "
                f"WHERE entity_type IN ({attach_sql}) AND entity_id IN ({in_sql})",
                [*attach_params, *in_params],
                queries,
            )

        if _table_exists(connection, "inspection_section_summaries"):
            summary_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT inspection_id FROM inspection_section_summaries "
                f"WHERE inspection_id IN ({in_sql})",
                in_params,
                queries,
            )

        if _table_exists(connection, "bozp_inspection_verification_overrides"):
            override_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT inspection_id "
                "FROM bozp_inspection_verification_overrides "
                f"WHERE inspection_id IN ({in_sql})",
                in_params,
                queries,
            )

        if _table_exists(connection, "entity_links"):
            link_ids = _fetch_id_set(
                connection,
                "SELECT DISTINCT source_id FROM entity_links "
                f"WHERE source_type IN ({attach_sql}) AND source_id IN ({in_sql}) "
                "UNION "
                "SELECT DISTINCT target_id FROM entity_links "
                f"WHERE target_type IN ({attach_sql}) AND target_id IN ({in_sql})",
                [*attach_params, *in_params, *attach_params, *in_params],
                queries,
            )

    other_data_ids = (
        conclusion_ids | result_other_ids | summary_ids | override_ids | link_ids
    )
    reason_sets = {
        SKIP_OTHER_STATUS: other_status_ids,
        SKIP_STARTED_FINISHED: started_ids,
        SKIP_RESULTS: result_ids,
        SKIP_COMMENTS: comment_ids,
        SKIP_PHOTOS: photo_ids,
        SKIP_FINDINGS: finding_ids,
        SKIP_TASKS: task_ids,
        SKIP_ATTACHMENTS: attachment_ids,
        SKIP_OTHER_DATA: other_data_ids,
    }

    skipped: dict[int, str] = {}
    eligible: list[int] = []
    for inspection_id in legacy_ids:
        reason = next(
            (
                key
                for key in SKIP_REASON_ORDER
                if inspection_id in reason_sets[key]
            ),
            None,
        )
        if reason is None:
            eligible.append(inspection_id)
        else:
            skipped[inspection_id] = reason

    skip_counts = {
        reason: sum(1 for value in skipped.values() if value == reason)
        for reason in SKIP_REASON_ORDER
    }
    return PlannedSectionSummaryInventory(
        legacy_ids=legacy_ids,
        eligible_ids=tuple(eligible),
        skipped=skipped,
        skip_counts=skip_counts,
        planning_snapshot=snapshots,
        query_count=len(queries),
    )


def _log_inventory(inventory: PlannedSectionSummaryInventory) -> None:
    logger.info(
        "PROVERKY-PLANNED-SECTION-SUMMARY-1 inventura: "
        "legacy=%s eligible=%s eligible_ids=%s skipped=%s "
        "jiny_stav=%s zahajena_ukoncena=%s vysledky=%s komentare=%s "
        "fotografie=%s zjisteni=%s ukoly=%s prilohy=%s jina_data=%s",
        len(inventory.legacy_ids),
        len(inventory.eligible_ids),
        list(inventory.eligible_ids),
        len(inventory.skipped),
        inventory.skip_counts[SKIP_OTHER_STATUS],
        inventory.skip_counts[SKIP_STARTED_FINISHED],
        inventory.skip_counts[SKIP_RESULTS],
        inventory.skip_counts[SKIP_COMMENTS],
        inventory.skip_counts[SKIP_PHOTOS],
        inventory.skip_counts[SKIP_FINDINGS],
        inventory.skip_counts[SKIP_TASKS],
        inventory.skip_counts[SKIP_ATTACHMENTS],
        inventory.skip_counts[SKIP_OTHER_DATA],
    )
    for inspection_id, reason in sorted(inventory.skipped.items()):
        logger.info(
            "PROVERKY-PLANNED-SECTION-SUMMARY-1 přeskočeno id=%s reason=%s",
            inspection_id,
            reason,
        )


def _validate_conversion(
    connection: sqlite3.Connection,
    inventory: PlannedSectionSummaryInventory,
) -> None:
    eligible = list(inventory.eligible_ids)
    if eligible:
        in_sql, in_params = _placeholders(eligible)
        converted = connection.execute(
            "SELECT COUNT(*) FROM bozp_inspections "
            f"WHERE id IN ({in_sql}) AND notes_mode = ?",
            [*in_params, NOTES_MODE_SECTION_SUMMARY_V1],
        ).fetchone()[0]
        if int(converted) != len(eligible):
            raise MigrationGuardError(
                "Validace převodu notes_mode selhala."
            )

    if eligible:
        leftover = connection.execute(
            "SELECT COUNT(*) FROM bozp_inspections "
            f"WHERE notes_mode IS NULL AND id IN ({in_sql})",
            in_params,
        ).fetchone()[0]
        if int(leftover) != 0:
            raise MigrationGuardError("Po převodu zbývají způsobilé legacy záznamy.")

    skipped_ids = list(inventory.skipped)
    if skipped_ids:
        in_sql, in_params = _placeholders(skipped_ids)
        still_legacy = connection.execute(
            "SELECT COUNT(*) FROM bozp_inspections "
            f"WHERE id IN ({in_sql}) AND notes_mode IS NULL",
            in_params,
        ).fetchone()[0]
        if int(still_legacy) != len(skipped_ids):
            raise MigrationGuardError("Přeskočené Prověrky nesmí změnit notes_mode.")

    if eligible:
        in_sql, in_params = _placeholders(eligible)
        planning_select = ", ".join(_PLANNING_COLUMNS)
        rows = connection.execute(
            f"SELECT id, {planning_select} FROM bozp_inspections "
            f"WHERE id IN ({in_sql})",
            in_params,
        ).fetchall()
        for row in rows:
            inspection_id = int(row[0])
            if tuple(row[1:]) != inventory.planning_snapshot[inspection_id]:
                raise MigrationGuardError(
                    f"Změnila se jiná pole než notes_mode (id={inspection_id})."
                )


def apply_planned_section_summary_conversion(
    db_path: Path,
    inventory: PlannedSectionSummaryInventory,
) -> None:
    connection = sqlite3.connect(str(Path(db_path).resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        eligible = list(inventory.eligible_ids)
        if eligible:
            in_sql, in_params = _placeholders(eligible)
            connection.execute(
                "UPDATE bozp_inspections SET notes_mode = ? "
                f"WHERE id IN ({in_sql}) AND notes_mode IS NULL",
                [NOTES_MODE_SECTION_SUMMARY_V1, *in_params],
            )
        _validate_conversion(connection, inventory)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_proverky_planned_section_summary_migration(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> PlannedSectionSummaryMigrationResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace PROVERKY-PLANNED-SECTION-SUMMARY-1 "
            "nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID):
        return PlannedSectionSummaryMigrationResult(
            migrated=False,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return PlannedSectionSummaryMigrationResult(
            migrated=False,
            skipped_reason="no_database",
        )

    if not needs_proverky_planned_section_summary_migration(database_path):
        return PlannedSectionSummaryMigrationResult(
            migrated=False,
            skipped_reason="schema_missing",
        )

    connection = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    try:
        inventory = collect_planned_section_summary_inventory(connection)
    finally:
        connection.close()
    _log_inventory(inventory)

    if not inventory.eligible_ids:
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        logger.info(
            "PROVERKY-PLANNED-SECTION-SUMMARY-1: žádné způsobilé Prověrky, "
            "bez zálohy a bez zápisu."
        )
        return PlannedSectionSummaryMigrationResult(
            migrated=False,
            skipped=dict(inventory.skipped),
            skipped_reason="no_eligible",
            inventory=inventory,
        )

    target = allocate_planned_section_summary_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací "
            "PROVERKY-PLANNED-SECTION-SUMMARY-1."
        ) from exc

    logger.info(
        "PROVERKY-PLANNED-SECTION-SUMMARY-1 záloha: %s",
        backup_path,
    )
    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_planned_section_summary_conversion(database_path, inventory)
        check = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
        try:
            _validate_conversion(check, inventory)
        finally:
            check.close()
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace PROVERKY-PLANNED-SECTION-SUMMARY-1 selhala. "
            "Obnovte data ze zálohy."
        ) from exc

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "PROVERKY-PLANNED-SECTION-SUMMARY-1: převedeno ids=%s záloha=%s",
        list(inventory.eligible_ids),
        backup_path,
    )
    return PlannedSectionSummaryMigrationResult(
        migrated=True,
        converted_ids=inventory.eligible_ids,
        skipped=dict(inventory.skipped),
        pre_migration_backup_path=backup_path,
        inventory=inventory,
    )
