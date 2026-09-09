"""BACKUP-UX-1: vytvoření *.mbbackup mimo GUI vlákno.

Worker dostane jen čistý snapshot cest. Nesmí dostat Qt widget, dialog
ani živou SQLAlchemy session z GUI vlákna. Databázi kopíruje
``create_instance_backup`` vlastním SQLite backup API.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.backup import CreateInstanceBackupResult, create_instance_backup
from core.widgets.long_operation_runner import LongOperationContext

BACKUP_CREATE_PROGRESS_TITLE = "Vytváření zálohy"
BACKUP_CREATE_PROGRESS_PHASE = (
    "Probíhá vytváření zálohy.\n"
    "Operace může podle velikosti dat chvíli trvat."
)


@dataclass(frozen=True)
class InstanceBackupCreateSnapshot:
    """Cesty pro worker. Bez Qt objektů a bez DB session."""

    target_path: str
    workspace_root: str
    database_path: str
    settings_path: str | None = None
    include_exports: bool = False


def create_instance_backup_work(
    ctx: LongOperationContext,
    snapshot: object,
) -> CreateInstanceBackupResult:
    """Vytvoří zálohu. Volat z workeru, ne z GUI vlákna."""
    if not isinstance(snapshot, InstanceBackupCreateSnapshot):
        raise TypeError(
            "create_instance_backup_work očekává InstanceBackupCreateSnapshot, "
            f"dostáno {type(snapshot)!r}."
        )

    ctx.set_phase(
        BACKUP_CREATE_PROGRESS_PHASE,
        indeterminate=True,
        atomic=True,
    )

    def on_progress(message: str) -> None:
        ctx.set_status(str(message))

    settings = Path(snapshot.settings_path) if snapshot.settings_path else None
    return create_instance_backup(
        snapshot.target_path,
        workspace_root=Path(snapshot.workspace_root),
        database_path=Path(snapshot.database_path),
        settings_path=settings,
        include_exports=snapshot.include_exports,
        progress_callback=on_progress,
    )
