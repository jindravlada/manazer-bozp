"""Předmigrační záloha a ochrana při přechodu 3.1.0 → 3.2.0 (MIGRATION-0).

Před první změnou schématu vytvoří ověřený ``*.mbbackup``. Při selhání
zálohy migraci nespouští. Nedokončenou migraci detekuje markerem a odmítne
otevřít napůl změněná data (automatický rollback schématu zatím není).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

from core.backup import (
    BACKUP_EXTENSION,
    create_instance_backup,
    inspect_backup_integrity,
)
from core.backup.package_create import InstanceBackupError

UPGRADE_FROM_VERSION = "3.1.0"
UPGRADE_TO_VERSION = "3.2.0"
TRANSITION_ID = f"{UPGRADE_FROM_VERSION}-to-{UPGRADE_TO_VERSION}"

# Indikátor „pre-risk“ databáze z éry 3.1.0 (Registr rizik ještě neexistoval).
LEGACY_MISSING_TABLE = "hazard_identifications"

InitializeFn = Callable[[], None]


class MigrationGuardError(Exception):
    """Obecná chyba ochrany migrace – aplikaci nelze bezpečně spustit."""


class PreMigrationBackupError(MigrationGuardError):
    """Předmigrační záloha selhala – migrace se nespustila."""


class MigrationIncompleteError(MigrationGuardError):
    """Předchozí migrace nedokončena – DB může být napůl změněná."""


@dataclass(frozen=True)
class PrepareDatabaseResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def migration_state_path(workspace_root: Path) -> Path:
    return Path(workspace_root) / "konfigurace" / "migration_state.json"


def read_migration_state(workspace_root: Path) -> dict:
    path = migration_state_path(workspace_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_migration_state(workspace_root: Path, data: dict) -> None:
    path = migration_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def is_transition_complete(workspace_root: Path, transition_id: str = TRANSITION_ID) -> bool:
    state = read_migration_state(workspace_root)
    completed = state.get("completed_transitions") or []
    return transition_id in completed


def is_migration_in_progress(workspace_root: Path, transition_id: str = TRANSITION_ID) -> bool:
    state = read_migration_state(workspace_root)
    active = state.get("in_progress")
    return isinstance(active, dict) and active.get("transition_id") == transition_id


def mark_migration_in_progress(
    workspace_root: Path,
    *,
    backup_path: Path,
    transition_id: str = TRANSITION_ID,
) -> None:
    state = read_migration_state(workspace_root)
    state["in_progress"] = {
        "transition_id": transition_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "pre_migration_backup": str(backup_path),
    }
    write_migration_state(workspace_root, state)


def mark_migration_complete(
    workspace_root: Path,
    *,
    backup_path: Path | None,
    transition_id: str = TRANSITION_ID,
) -> None:
    state = read_migration_state(workspace_root)
    completed = list(state.get("completed_transitions") or [])
    if transition_id not in completed:
        completed.append(transition_id)
    state["completed_transitions"] = completed
    state["in_progress"] = None
    state["last_failed"] = None
    state["last_completed"] = {
        "transition_id": transition_id,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "pre_migration_backup": str(backup_path) if backup_path else None,
    }
    write_migration_state(workspace_root, state)


def clear_transition_complete(
    workspace_root: Path,
    transition_id: str = TRANSITION_ID,
) -> None:
    """Odstraní transition z completed (např. po obnově starší DB)."""
    state = read_migration_state(workspace_root)
    completed = [
        item
        for item in (state.get("completed_transitions") or [])
        if item != transition_id
    ]
    state["completed_transitions"] = completed
    last = state.get("last_completed")
    if isinstance(last, dict) and last.get("transition_id") == transition_id:
        state["last_completed"] = None
    write_migration_state(workspace_root, state)


def mark_migration_failed(
    workspace_root: Path,
    *,
    backup_path: Path | None,
    error: str,
    transition_id: str = TRANSITION_ID,
) -> None:
    """Označí migraci jako selhanou (ne dokončenou). Uvolní in_progress po rollbacku."""
    state = read_migration_state(workspace_root)
    active = state.get("in_progress")
    if isinstance(active, dict) and active.get("transition_id") == transition_id:
        state["in_progress"] = None
    state["last_failed"] = {
        "transition_id": transition_id,
        "failed_at": datetime.now().isoformat(timespec="seconds"),
        "pre_migration_backup": str(backup_path) if backup_path else None,
        "error": str(error or "").strip(),
    }
    write_migration_state(workspace_root, state)


def is_migration_failed(
    workspace_root: Path, transition_id: str = TRANSITION_ID
) -> bool:
    state = read_migration_state(workspace_root)
    failed = state.get("last_failed")
    return isinstance(failed, dict) and failed.get("transition_id") == transition_id


def sqlite_table_exists(db_path: Path, table_name: str) -> bool:
    if not Path(db_path).is_file():
        return False
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def needs_legacy_upgrade_to_risk_registry(db_path: Path) -> bool:
    """True, pokud DB existuje a ještě nemá tabulky Registru rizik (3.1.0)."""
    path = Path(db_path)
    if not path.is_file():
        return False
    return not sqlite_table_exists(path, LEGACY_MISSING_TABLE)


def allocate_pre_migration_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
    transition_id: str = TRANSITION_ID,
) -> Path:
    """Jednoznačný název; nikdy nepřepisuje existující soubor."""
    backups_dir = Path(backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = f"pre-migration-{transition_id}-{stamp}{BACKUP_EXTENSION}"
    candidate = backups_dir / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = backups_dir / (
            f"pre-migration-{transition_id}-{stamp}-{index}{BACKUP_EXTENSION}"
        )
        if not alt.exists():
            return alt
    raise PreMigrationBackupError(
        "Nelze přidělit unikátní název předmigrační zálohy."
    )


def create_verified_pre_migration_backup(
    *,
    target_path: Path,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> Path:
    """Vytvoří a ověří předmigrační ``*.mbbackup`` (SQLite backup API)."""
    target = Path(target_path)
    if target.exists():
        raise PreMigrationBackupError(
            f"Cíl předmigrační zálohy už existuje: {target}"
        )
    try:
        create_instance_backup(
            target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
            verify=True,
        )
    except (InstanceBackupError, OSError) as exc:
        raise PreMigrationBackupError(
            "Nepodařilo se vytvořit předmigrační zálohu. "
            "Migrace nebyla spuštěna, původní data zůstala beze změny.\n\n"
            f"Detail: {exc}"
        ) from exc

    report = inspect_backup_integrity(target)
    if not report.ok:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        details = "; ".join(issue.message for issue in report.issues[:5])
        raise PreMigrationBackupError(
            "Předmigrační záloha neprošla ověřením integrity. "
            "Migrace nebyla spuštěna, původní data zůstala beze změny.\n\n"
            f"Detail: {details or report.status}"
        )
    return target


def prepare_database_for_startup(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
    initialize_fn: InitializeFn | None = None,
    transition_id: str = TRANSITION_ID,
) -> PrepareDatabaseResult:
    """
    Spouštěcí příprava DB: případná předmigrační záloha, pak ``initialize_database``.

    Pořadí:
    1. Odmítnout pokračování při ``in_progress`` markeru (MIGRATION-0).
    2. AUDIT-SNAPSHOT-0: pokud chybí schema na existující DB → záloha + DDL.
    3. Pokud legacy DB bez Registru rizik → záloha + ověření + marker.
    4. Spustit migrace / ``create_all``.
    5. Dokončit AUDIT-SNAPSHOT-0 marker (čistá instalace).
    6. Označit přechod 3.1→3.2 jako dokončený (záloha se nemaže).
    """
    from core.database.database_initializer import initialize_database
    from core.services.storage_service import storage_service
    from moduly.audity.sluzby.audit_snapshot_schema_migration import (
        needs_audit_snapshot_schema,
        prepare_audit_snapshot_schema,
    )

    if workspace_root is None or database_path is None:
        storage_service.ensure_structure()
        workspace_root = workspace_root or storage_service.base
        database_path = database_path or storage_service.database_path

    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"
    init = initialize_fn or initialize_database

    if is_migration_in_progress(workspace_root, transition_id):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationIncompleteError(
            "Předchozí upgrade databáze nebyl dokončen.\n\n"
            "Aplikace neotevře napůl migrovaná data.\n"
            "Obnovte data z předmigrační zálohy a kontaktujte podporu, "
            "pokud problém přetrvá.\n\n"
            f"Přechod: {transition_id}\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    # AUDIT-SNAPSHOT-0 před create_all — zabrání vzniku tabulky bez zálohy.
    if needs_audit_snapshot_schema(database_path):
        prepare_audit_snapshot_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_intro_schema_migration import (
        needs_audit_intro_schema,
        prepare_audit_intro_schema,
    )

    if needs_audit_intro_schema(database_path):
        prepare_audit_intro_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_extraordinary_schema_migration import (
        needs_audit_extraordinary_schema,
        prepare_audit_extraordinary_schema,
    )

    if needs_audit_extraordinary_schema(database_path):
        prepare_audit_extraordinary_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_extraordinary_2_schema_migration import (
        needs_audit_extraordinary_2_schema,
        prepare_audit_extraordinary_2_schema,
    )

    if needs_audit_extraordinary_2_schema(database_path):
        prepare_audit_extraordinary_2_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_extraordinary_3_schema_migration import (
        needs_audit_extraordinary_3_schema,
        prepare_audit_extraordinary_3_schema,
    )

    if needs_audit_extraordinary_3_schema(database_path):
        prepare_audit_extraordinary_3_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_conclusion_1_schema_migration import (
        needs_audit_conclusion_1_schema,
        prepare_audit_conclusion_1_schema,
    )

    if needs_audit_conclusion_1_schema(database_path):
        prepare_audit_conclusion_1_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration import (
        needs_audit_lead_recommendation_1_schema,
        prepare_audit_lead_recommendation_1_schema,
    )

    if needs_audit_lead_recommendation_1_schema(database_path):
        prepare_audit_lead_recommendation_1_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        needs_method_support_snapshot_1_schema,
        prepare_method_support_snapshot_1_schema,
    )

    if needs_method_support_snapshot_1_schema(database_path):
        prepare_method_support_snapshot_1_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration import (
        needs_external_audit_ea_0_schema,
        prepare_external_audit_ea_0_schema,
    )

    if needs_external_audit_ea_0_schema(database_path):
        prepare_external_audit_ea_0_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.nastaveni.sluzby.person_thp_separation_migration import (
        needs_person_thp_separation,
        prepare_person_thp_separation,
    )

    if needs_person_thp_separation(database_path):
        prepare_person_thp_separation(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    from moduly.audity.sluzby.audit_proverky_section_note_schema_migration import (
        needs_audit_proverky_section_note_schema,
        prepare_audit_proverky_section_note_schema,
    )

    if needs_audit_proverky_section_note_schema(database_path):
        prepare_audit_proverky_section_note_schema(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )

    result: PrepareDatabaseResult

    # Čistá instalace / už migrovaná DB – jen idempotentní initialize.
    if not needs_legacy_upgrade_to_risk_registry(database_path):
        init()
        if (
            database_path.is_file()
            and sqlite_table_exists(database_path, LEGACY_MISSING_TABLE)
            and not is_transition_complete(workspace_root, transition_id)
        ):
            # DB už má Registr rizik (např. vývojová instance) – označit bez nové zálohy.
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=transition_id
            )
        result = PrepareDatabaseResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_legacy_upgrade_needed",
        )
    elif (
        is_transition_complete(workspace_root, transition_id)
        and not needs_legacy_upgrade_to_risk_registry(database_path)
    ):
        # Defenzivní větev (prakticky nedosažitelná po prvním if).
        init()
        result = PrepareDatabaseResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="transition_already_complete",
        )
    elif is_transition_complete(workspace_root, transition_id):
        # Marker hotovo, ale legacy tabulka stále chybí → znovu zálohovat a migrovat.
        result = _run_legacy_upgrade(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
            backups_dir=backups_dir,
            init=init,
            transition_id=transition_id,
        )
    else:
        result = _run_legacy_upgrade(
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
            backups_dir=backups_dir,
            init=init,
            transition_id=transition_id,
        )

    # Po create_all (nová instalace) dokončit marker AUDIT-SNAPSHOT-0.
    prepare_audit_snapshot_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_intro_schema_migration import (
        prepare_audit_intro_schema,
    )

    prepare_audit_intro_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_extraordinary_schema_migration import (
        prepare_audit_extraordinary_schema,
    )

    prepare_audit_extraordinary_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_extraordinary_2_schema_migration import (
        prepare_audit_extraordinary_2_schema,
    )

    prepare_audit_extraordinary_2_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_extraordinary_3_schema_migration import (
        prepare_audit_extraordinary_3_schema,
    )

    prepare_audit_extraordinary_3_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_conclusion_1_schema_migration import (
        prepare_audit_conclusion_1_schema,
    )

    prepare_audit_conclusion_1_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration import (
        prepare_audit_lead_recommendation_1_schema,
    )

    prepare_audit_lead_recommendation_1_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        prepare_method_support_snapshot_1_schema,
    )

    prepare_method_support_snapshot_1_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration import (
        prepare_external_audit_ea_0_schema,
    )

    prepare_external_audit_ea_0_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.nastaveni.sluzby.person_thp_separation_migration import (
        prepare_person_thp_separation,
    )

    prepare_person_thp_separation(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_proverky_section_note_schema_migration import (
        prepare_audit_proverky_section_note_schema,
    )

    prepare_audit_proverky_section_note_schema(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.proverky.sluzby.proverky_planned_section_summary_migration import (
        prepare_proverky_planned_section_summary_migration,
    )

    prepare_proverky_planned_section_summary_migration(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_method_support_backfill_service import (
        prepare_method_support_backfill,
    )

    t_ms = time.perf_counter()
    prepare_method_support_backfill(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )
    method_support_backfill_ms = (time.perf_counter() - t_ms) * 1000

    from moduly.audity.sluzby.audit_method_support_integrity_guard import (
        prepare_method_support_integrity_guard,
    )

    t_ms = time.perf_counter()
    prepare_method_support_integrity_guard(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )
    method_support_integrity_ms = (time.perf_counter() - t_ms) * 1000

    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        prepare_audit_snapshot_backfill,
    )
    from moduly.audity.sluzby.audit_snapshot_schema_migration import (
        schema_is_present as audit_snapshot_schema_present,
    )
    from moduly.audity.sluzby.audit_snapshot_scope_migration import (
        ensure_scope_column,
        prepare_audit_snapshot_scope_fix,
    )

    # Sloupec is_in_scope musí existovat před zápisem backfillu.
    if audit_snapshot_schema_present(database_path):
        ensure_scope_column(database_path)

    # Klasifikace is_in_scope před zapečetěním (NULL by zablokovalo seal).
    prepare_audit_snapshot_scope_fix(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    from moduly.audity.sluzby.audit_snapshot_integrity_service import (
        prepare_audit_snapshot_integrity_seal,
    )

    # AUDIT-SNAPSHOT-URGENT-1: DB-only zapečetění před backfill guardem (bez live JSON).
    prepare_audit_snapshot_integrity_seal(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )

    t_ms = time.perf_counter()
    prepare_audit_snapshot_backfill(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )
    snapshot_backfill_ms = (time.perf_counter() - t_ms) * 1000

    # Idempotentní doběh klasifikace po backfillu.
    prepare_audit_snapshot_scope_fix(
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )
    logger.info(
        "upgrade_guard: method_support_backfill=%.0fms "
        "method_support_integrity=%.0fms snapshot_backfill=%.0fms",
        method_support_backfill_ms,
        method_support_integrity_ms,
        snapshot_backfill_ms,
    )
    return result


def _run_legacy_upgrade(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None,
    backups_dir: Path,
    init: InitializeFn,
    transition_id: str,
) -> PrepareDatabaseResult:
    target = allocate_pre_migration_backup_path(
        backups_dir, transition_id=transition_id
    )
    backup_path = create_verified_pre_migration_backup(
        target_path=target,
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
    )
    mark_migration_in_progress(
        workspace_root, backup_path=backup_path, transition_id=transition_id
    )

    try:
        init()
    except Exception:
        # Marker zůstává – další start odmítne napůl migrovaný stav.
        raise

    mark_migration_complete(
        workspace_root, backup_path=backup_path, transition_id=transition_id
    )
    return PrepareDatabaseResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
        skipped_reason=None,
    )
