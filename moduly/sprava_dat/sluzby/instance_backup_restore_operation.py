"""BACKUP-UX-2: obnova *.mbbackup mimo GUI vlákno.

Worker dostane jen čistý snapshot cest. Nesmí dostat Qt widget, dialog
ani živou SQLAlchemy session z GUI vlákna.

Bezpečnostní záloha před obnovou běží ve workeru (stejné SQLite backup API
jako ruční záloha). Samotná výměna dat běží v dalším workeru až poté,
co GUI vlákno uzavře globální databázový engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.backup import (
    InstanceRestoreError,
    create_instance_backup,
    restore_instance_backup,
)
from core.widgets.long_operation_runner import LongOperationContext

BACKUP_RESTORE_PROGRESS_TITLE = "Obnova ze zálohy"
BACKUP_RESTORE_PROGRESS_PHASE = (
    "Probíhá obnova dat ze zálohy.\n"
    "Operace může podle velikosti dat chvíli trvat."
)


@dataclass(frozen=True)
class InstanceBackupRestoreSnapshot:
    """Cesty pro worker. Bez Qt objektů a bez DB session."""

    package_path: str
    workspace_root: str
    database_path: str
    settings_path: str | None = None
    safety_target_path: str | None = None


@dataclass
class InstanceBackupRestoreOutcome:
    """Výsledek jedné fáze obnovy. Přenositelný mezi thready (žádné Qt/DB objekty)."""

    safety_path: str | None = None
    restore_result: object | None = None
    restore_error: InstanceRestoreError | None = None
    unexpected_error: str | None = None


def _bind_progress(ctx: LongOperationContext):
    def on_progress(message: str) -> None:
        ctx.set_status(str(message))

    return on_progress


def create_safety_backup_work(
    ctx: LongOperationContext,
    snapshot: object,
) -> InstanceBackupRestoreOutcome:
    """Vytvoří AUTO_BEFORE_RESTORE zálohu. Volat z workeru, ne z GUI vlákna."""
    if not isinstance(snapshot, InstanceBackupRestoreSnapshot):
        raise TypeError(
            "create_safety_backup_work očekává InstanceBackupRestoreSnapshot, "
            f"dostáno {type(snapshot)!r}."
        )
    if not snapshot.safety_target_path:
        raise ValueError("Snapshot nemá cestu pro bezpečnostní zálohu.")

    ctx.set_phase(
        BACKUP_RESTORE_PROGRESS_PHASE,
        indeterminate=True,
        atomic=True,
    )
    ctx.set_status("Vytvářím automatickou bezpečnostní zálohu…")

    settings = Path(snapshot.settings_path) if snapshot.settings_path else None
    result = create_instance_backup(
        snapshot.safety_target_path,
        workspace_root=Path(snapshot.workspace_root),
        database_path=Path(snapshot.database_path),
        settings_path=settings,
        progress_callback=_bind_progress(ctx),
    )
    return InstanceBackupRestoreOutcome(
        safety_path=str(Path(result.path).resolve()),
    )


def restore_instance_backup_work(
    ctx: LongOperationContext,
    snapshot: object,
) -> InstanceBackupRestoreOutcome:
    """Rozbalí a nahradí data ze zálohy. Volat z workeru po dispose engine."""
    if not isinstance(snapshot, InstanceBackupRestoreSnapshot):
        raise TypeError(
            "restore_instance_backup_work očekává InstanceBackupRestoreSnapshot, "
            f"dostáno {type(snapshot)!r}."
        )

    ctx.set_phase(
        BACKUP_RESTORE_PROGRESS_PHASE,
        indeterminate=True,
        atomic=True,
    )

    settings = Path(snapshot.settings_path) if snapshot.settings_path else None
    try:
        result = restore_instance_backup(
            snapshot.package_path,
            workspace_root=Path(snapshot.workspace_root),
            settings_path=settings,
            progress_callback=_bind_progress(ctx),
        )
    except InstanceRestoreError as exc:
        return InstanceBackupRestoreOutcome(restore_error=exc)
    except Exception as exc:  # noqa: BLE001
        return InstanceBackupRestoreOutcome(unexpected_error=str(exc))
    return InstanceBackupRestoreOutcome(restore_result=result)
