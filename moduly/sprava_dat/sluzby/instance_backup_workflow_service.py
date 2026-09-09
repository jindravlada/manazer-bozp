"""UI workflow pro zálohu / ověření / obnovu instance (*.mbbackup) – BACKUP-2c."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from core.backup import (
    BACKUP_EXTENSION,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    INTEGRITY_VALID_WITH_WARNINGS,
    RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
    RESTORE_ERR_FAILED_BEFORE_SWAP,
    RESTORE_ERR_ROLLBACK_FAILED,
    VERDICT_INCOMPLETE,
    CreateInstanceBackupResult,
    InstanceRestoreError,
    auto_before_restore_backup_filename,
    create_instance_backup,
    default_instance_backup_filename,
    find_recovery_markers,
    inspect_backup_integrity,
    read_recovery_marker,
    restore_instance_backup,
)
from core.backup.package_create import resolve_settings_file
from core.services.storage_service import storage_service
from core.widgets.long_operation_dialog import LongOperationDialog
from core.widgets.long_operation_runner import LongOperationRunner
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BACKUP_TYPE_INSTANCE,
    BackupRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.sluzby.instance_backup_create_operation import (
    BACKUP_CREATE_PROGRESS_TITLE,
    InstanceBackupCreateSnapshot,
    create_instance_backup_work,
)
from moduly.sprava_dat.ui.instance_backup_dialogs import (
    BackupProgressDialog,
    ContinueWithoutSafetyBackupDialog,
    MessageWithDetailsDialog,
    RestoreConfirmDialog,
)

logger = logging.getLogger(__name__)

_STATUS_LABELS = {
    INTEGRITY_VALID: "Platná",
    INTEGRITY_VALID_WITH_WARNINGS: "Platná s upozorněními",
    INTEGRITY_INVALID: "Neplatná",
}

_RESTORE_USER_MESSAGES = {
    RESTORE_ERR_FAILED_BEFORE_SWAP: (
        "Obnova selhala dříve, než došlo k výměně dat. "
        "Současná pracovní data nebyla změněna."
    ),
    RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK: (
        "Obnova selhala po výměně dat, ale původní data byla úspěšně vrácena "
        "automatickým rollbackem."
    ),
    RESTORE_ERR_ROLLBACK_FAILED: (
        "Kritická chyba: obnova selhala a automatický návrat původních dat "
        "se nepodařil. Aplikaci neukončujte a nemažte pracovní adresáře."
    ),
}


class InstanceBackupWorkflowService:
    """Napojení core.backup API na UI Správy dat."""

    def __init__(self) -> None:
        self._restore_blocked = False
        self._active_markers: list[Path] = []
        self._operation_running = False
        self._create_runner: LongOperationRunner | None = None
        self._create_progress_dialog: LongOperationDialog | None = None

    @property
    def restore_blocked(self) -> bool:
        return self._restore_blocked

    @property
    def active_markers(self) -> list[Path]:
        return list(self._active_markers)

    def refresh_recovery_markers(self) -> list[Path]:
        markers = find_recovery_markers(storage_service.base.parent)
        self._active_markers = markers
        self._restore_blocked = bool(markers)
        return markers

    def check_recovery_markers_at_startup(self, parent: QWidget | None = None) -> bool:
        """
        Zkontroluje recovery markery při startu.

        Returns:
            True pokud je obnova zablokována kvůli markeru.
        """
        markers = self.refresh_recovery_markers()
        if not markers:
            return False

        lines = [
            "<b>Byla zjištěna nedokončená obnova dat.</b>",
            "",
            "Aplikace našla technický marker probíhající obnovy. "
            "Data mohla zůstat v nekonzistentním stavu.",
            "",
            "Co dělat:",
            "• Aplikaci můžete používat pro prohlížení, ale <b>neobnovujte</b> "
            "další zálohu.",
            "• Nemazejte pracovní adresáře ani soubory markeru.",
            "• Kontaktujte podporu / použijte diagnostiku ve Správě dat.",
            "",
            "Nalezené markery:",
        ]
        details_parts: list[str] = []
        for marker in markers:
            lines.append(f"• {marker}")
            try:
                payload = read_recovery_marker(marker)
                details_parts.append(
                    f"{marker}\n"
                    f"  fáze: {payload.get('phase')}\n"
                    f"  zahájeno: {payload.get('started_at')}\n"
                    f"  workspace: {payload.get('workspace_root')}\n"
                    f"  rollback: {payload.get('rollback_workspace')}\n"
                )
            except Exception as exc:  # noqa: BLE001
                details_parts.append(f"{marker}\n  (nelze načíst: {exc})\n")

        dialog = MessageWithDetailsDialog(
            parent,
            title="Nedokončená obnova dat",
            message="<br>".join(lines),
            details="\n".join(details_parts),
            level="critical",
        )
        dialog.exec()
        return True

    def show_recovery_diagnostics(self, parent: QWidget) -> None:
        markers = self.refresh_recovery_markers()
        if not markers:
            QMessageBox.information(
                parent,
                "Diagnostika obnovy",
                "Žádný recovery marker nebyl nalezen. Obnova není blokována.",
            )
            return
        details = []
        for marker in markers:
            try:
                payload = read_recovery_marker(marker)
                details.append(str(payload))
            except Exception as exc:  # noqa: BLE001
                details.append(f"{marker}: {exc}")
        MessageWithDetailsDialog(
            parent,
            title="Diagnostika obnovy",
            message=(
                f"Nalezeno markerů: <b>{len(markers)}</b>.<br><br>"
                + "<br>".join(f"• {m}" for m in markers)
                + "<br><br>Další obnovu nelze spustit, dokud nebude stav vyřešen."
            ),
            details="\n\n".join(details),
            level="critical",
        ).exec()

    def create_instance_backup_ui(self, parent: QWidget) -> bool:
        if self._operation_running:
            QMessageBox.warning(parent, "Záloha", "Jiná operace právě probíhá.")
            return False

        storage_service.ensure_structure()
        default_name = default_instance_backup_filename()
        default_path = storage_service.backups_dir / default_name
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Uložit zálohu",
            str(default_path),
            f"Záloha Manažera BOZP (*{BACKUP_EXTENSION})",
        )
        if not file_path:
            return False
        if not file_path.lower().endswith(BACKUP_EXTENSION):
            file_path += BACKUP_EXTENSION

        settings_file = resolve_settings_file()
        snapshot = InstanceBackupCreateSnapshot(
            target_path=str(file_path),
            workspace_root=str(Path(storage_service.base).resolve()),
            database_path=str(Path(storage_service.database_path).resolve()),
            settings_path=str(settings_file.resolve()) if settings_file else None,
        )

        runner = LongOperationRunner(parent)
        dialog = LongOperationDialog(
            parent,
            title=BACKUP_CREATE_PROGRESS_TITLE,
            runner=runner,
            delay_ms=0,
            allow_cancel=False,
        )
        self._create_runner = runner
        self._create_progress_dialog = dialog

        outcome: dict[str, object] = {"result": None, "error": None}

        def on_succeeded(result: object) -> None:
            outcome["result"] = result

        def on_failed(message: str) -> None:
            outcome["error"] = message

        loop = QEventLoop(parent)
        runner.succeeded.connect(on_succeeded)
        runner.failed.connect(on_failed)
        runner.finished.connect(loop.quit)

        blocked: list[QWidget] = []
        for attr in (
            "create_mbbackup_button",
            "verify_mbbackup_button",
            "restore_mbbackup_button",
        ):
            widget = getattr(parent, attr, None)
            if isinstance(widget, QWidget):
                blocked.append(widget)

        self._operation_running = True
        try:
            if not runner.start(
                create_instance_backup_work,
                snapshot,
                blocked_widgets=blocked or None,
            ):
                QMessageBox.warning(parent, "Záloha", "Jiná operace právě probíhá.")
                return False
            loop.exec()
        finally:
            self._operation_running = False
            self._create_runner = None
            self._create_progress_dialog = None
            dialog.complete()
            dialog.deleteLater()

        error = outcome["error"]
        if error is not None:
            MessageWithDetailsDialog(
                parent,
                title="Vytvoření zálohy",
                message="Zálohu se nepodařilo vytvořit.",
                details=str(error),
                level="critical",
            ).exec()
            return False

        result = outcome["result"]
        if result is None or not hasattr(result, "path") or not hasattr(result, "metadata"):
            MessageWithDetailsDialog(
                parent,
                title="Vytvoření zálohy",
                message="Zálohu se nepodařilo vytvořit kvůli neočekávané chybě.",
                details="Worker nevrátil výsledek zálohy.",
                level="critical",
            ).exec()
            return False

        self.persist_last_instance_backup(cast(CreateInstanceBackupResult, result))

        meta = result.metadata
        coverage_note = ""
        if result.coverage_verdict == VERDICT_INCOMPLETE:
            listed = ", ".join(result.unknown_workspace_roots) or "neznámé"
            coverage_note = (
                f"<br><br><b>Záloha není bezvýhradně úplná (INCOMPLETE).</b> "
                f"Neznámé datové kořeny nebyly vloženy do archivu: "
                f"<code>{listed}</code>."
            )
        summary = (
            f"<b>Záloha byla úspěšně vytvořena.</b><br><br>"
            f"Soubor: <code>{result.path}</code><br>"
            f"Vytvořeno: {meta.created_at}<br>"
            f"Verze aplikace: {meta.app_version}<br>"
            f"Souborů v balíčku: {len(meta.files)}<br>"
            f"Integrita DB: {result.database_integrity}"
            f"{coverage_note}"
        )
        MessageWithDetailsDialog(
            parent,
            title="Vytvoření zálohy",
            message=summary,
            details=(
                f"format_version={meta.format_version}\n"
                f"package_kind={meta.package_kind}\n"
                f"total_content_size={meta.total_content_size}\n"
                f"platform={meta.platform}"
            ),
        ).exec()
        return True

    @staticmethod
    def persist_last_instance_backup(result: CreateInstanceBackupResult) -> BackupRecord:
        """Uloží metadata poslední kompletní zálohy (*.mbbackup) pro Souhrn / Stav dat."""
        meta = result.metadata
        coverage = getattr(result, "coverage_verdict", None)
        unknown = getattr(result, "unknown_workspace_roots", ())
        if not isinstance(coverage, str):
            coverage = None
        try:
            unknown_list = [str(item) for item in (unknown or ()) if isinstance(item, str)]
        except TypeError:
            unknown_list = []
        record = BackupRecord(
            created_at=str(
                meta.created_at or datetime.now().isoformat(timespec="seconds")
            ),
            path=str(Path(result.path).resolve()),
            manifest={
                "verified": bool(result.verified),
                "package_kind": meta.package_kind,
                "format_version": meta.format_version,
                "app_version": meta.app_version,
                "file_count": len(meta.files),
                "database_integrity": result.database_integrity,
                "backup_format": "mbbackup",
                **({"coverage_verdict": coverage} if coverage is not None else {}),
                "unknown_workspace_roots": unknown_list,
            },
            backup_type=BACKUP_TYPE_INSTANCE,
        )
        data_management_settings_service.save_last_backup(record)
        return record

    def verify_instance_backup_ui(self, parent: QWidget) -> bool:
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Vybrat zálohu k ověření",
            str(storage_service.backups_dir),
            f"Záloha Manažera BOZP (*{BACKUP_EXTENSION})",
        )
        if not file_path:
            return False

        report = inspect_backup_integrity(file_path)
        status_label = _STATUS_LABELS.get(report.status, report.status)
        issues = report.issues
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        lines = [
            f"<b>Stav zálohy: {status_label}</b>",
            f"Soubor: <code>{file_path}</code>",
        ]
        if report.metadata is not None:
            lines.extend(
                [
                    f"Vytvořeno: {report.metadata.created_at}",
                    f"Verze aplikace: {report.metadata.app_version}",
                    f"Souborů zkontrolováno: {report.files_checked}",
                ]
            )
        if errors:
            lines.append("<br><b>Problémy:</b>")
            lines.extend(f"• {e.message}" for e in errors[:12])
            if len(errors) > 12:
                lines.append(f"• … a dalších {len(errors) - 12}")
        if warnings:
            lines.append("<br><b>Upozornění:</b>")
            lines.extend(f"• {w.message}" for w in warnings[:12])

        details = "\n".join(
            f"[{i.severity}] {i.code}: {i.message}" for i in issues
        )
        level = "critical" if report.status == INTEGRITY_INVALID else "info"
        MessageWithDetailsDialog(
            parent,
            title="Ověření zálohy",
            message="<br>".join(lines),
            details=details,
            level=level,
        ).exec()
        return report.ok

    def restore_instance_backup_ui(self, parent: QWidget) -> bool:
        if self._operation_running:
            QMessageBox.warning(parent, "Obnova", "Jiná operace právě probíhá.")
            return False

        self.refresh_recovery_markers()
        if self._restore_blocked:
            MessageWithDetailsDialog(
                parent,
                title="Obnova zakázána",
                message=(
                    "Obnovu nelze spustit, protože existuje recovery marker "
                    "nedokončené obnovy.<br><br>"
                    "Zobrazte diagnostiku a stav nevyřešte ručním mazáním souborů."
                ),
                details="\n".join(str(m) for m in self._active_markers),
                level="critical",
            ).exec()
            return False

        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Vybrat zálohu k obnově",
            str(storage_service.backups_dir),
            f"Záloha Manažera BOZP (*{BACKUP_EXTENSION})",
        )
        if not file_path:
            return False

        report = inspect_backup_integrity(file_path)
        if report.status == INTEGRITY_INVALID or not report.ok:
            MessageWithDetailsDialog(
                parent,
                title="Obnova zakázána",
                message=(
                    "<b>Záloha je neplatná a nelze ji obnovit.</b><br><br>"
                    "Nejdříve vyberte jinou zálohu nebo použijte akci Ověřit zálohu."
                ),
                details="\n".join(
                    f"[{i.severity}] {i.code}: {i.message}" for i in report.errors
                ),
                level="critical",
            ).exec()
            return False

        # VALID_WITH_WARNINGS je povoleno (report.ok == True)
        meta = report.metadata
        created = meta.created_at if meta else "neznámé"
        app_ver = meta.app_version if meta else "neznámá"
        warning_note = ""
        if report.status == INTEGRITY_VALID_WITH_WARNINGS:
            warning_lines = "<br>".join(f"• {w.message}" for w in report.warnings[:8])
            warning_note = (
                "<br><br><b>Omezení této zálohy:</b> balíček není poškozený "
                "a lze ho obnovit."
                f"<br>{warning_lines}"
            )

        summary = (
            f"Soubor: <code>{file_path}</code><br>"
            f"Datum vytvoření zálohy: <b>{created}</b><br>"
            f"Verze aplikace v záloze: <b>{app_ver}</b><br><br>"
            f"Současná pracovní data (databáze, přílohy, nastavení…) "
            f"<b>budou nahrazena</b> obsahem této zálohy.<br><br>"
            f"Před obnovou bude automaticky vytvořena kompletní bezpečnostní "
            f"záloha aktuálních dat."
            f"{warning_note}"
        )
        confirm = RestoreConfirmDialog(parent, summary_text=summary)
        if confirm.exec() != RestoreConfirmDialog.DialogCode.Accepted:
            return False

        progress = BackupProgressDialog(parent, title="Probíhá obnova")
        progress.set_status("Vytvářím automatickou bezpečnostní zálohu…")
        progress.show()
        QApplication.processEvents()
        self._operation_running = True

        safety_path: Path | None = None
        try:

            def on_safety_progress(message: str) -> None:
                progress.set_status(message)
                QApplication.processEvents()

            safety_path = self._create_auto_before_restore_backup(
                progress_callback=on_safety_progress
            )
        except Exception as exc:  # noqa: BLE001
            progress.allow_close()
            progress.close()
            self._operation_running = False
            logger.warning(
                "Automatická bezpečnostní záloha před obnovou selhala: %s",
                exc,
            )
            crisis = ContinueWithoutSafetyBackupDialog(parent)
            if crisis.exec() != ContinueWithoutSafetyBackupDialog.DialogCode.Accepted:
                return False
            logger.warning(
                "Uživatel vědomě pokračoval v obnově bez vytvoření "
                "automatické bezpečnostní zálohy."
            )
            progress = BackupProgressDialog(parent, title="Probíhá obnova")
            progress.set_status("Pokračuji obnovou bez bezpečnostní zálohy…")
            progress.show()
            QApplication.processEvents()
            self._operation_running = True

        try:
            from core.database.session import dispose_database_engine

            progress.set_status("Uzavírám databázová připojení…")
            QApplication.processEvents()
            dispose_database_engine()

            def on_progress(message: str) -> None:
                progress.set_status(message)
                QApplication.processEvents()

            result = restore_instance_backup(
                file_path,
                progress_callback=on_progress,
            )
        except InstanceRestoreError as exc:
            progress.allow_close()
            progress.close()
            self._show_restore_error(parent, exc)
            self.refresh_recovery_markers()
            return False
        except Exception as exc:  # noqa: BLE001
            progress.allow_close()
            progress.close()
            MessageWithDetailsDialog(
                parent,
                title="Obnova ze zálohy",
                message="Obnova selhala kvůli neočekávané chybě.",
                details=str(exc),
                level="critical",
            ).exec()
            self.refresh_recovery_markers()
            return False
        finally:
            self._operation_running = False
            progress.allow_close()
            progress.close()

        warnings_text = ""
        if result.warnings:
            warnings_text = "<br><br><b>Upozornění:</b><br>" + "<br>".join(
                f"• {w}" for w in result.warnings
            )

        safety_text = ""
        if safety_path is not None:
            safety_text = (
                "<br><br>Před obnovou byla automaticky vytvořena bezpečnostní "
                "záloha aktuálních dat.<br>"
                f"Soubor: <code>{safety_path.name}</code><br>"
                f"Umístění: <code>{safety_path.parent}</code>"
            )

        MessageWithDetailsDialog(
            parent,
            title="Obnova dokončena",
            message=(
                "<b>Záloha byla úspěšně obnovena.</b><br><br>"
                f"Workspace: <code>{result.workspace_root}</code><br>"
                f"Integrita DB: {result.database_integrity}<br>"
                "Pro načtení obnovených dat je nutný <b>restart aplikace</b>."
                f"{safety_text}"
                f"{warnings_text}"
            ),
            details="\n".join(result.notes or []),
        ).exec()

        QMessageBox.information(
            parent,
            "Restart aplikace",
            "Data byla obnovena. Aplikace se nyní bezpečně ukončí.\n"
            "Po novém spuštění se načtou obnovená data.",
        )
        QApplication.quit()
        return True

    def _create_auto_before_restore_backup(
        self,
        *,
        progress_callback=None,
    ) -> Path:
        """Kompletní nouzová záloha aktuálních dat před obnovou (BACKUP-RESTORE-SAFE-1).

        Soubor se nikdy automaticky nemaže – ani při úspěšné, ani při neúspěšné obnově.
        """
        storage_service.ensure_structure()
        target = storage_service.backups_dir / auto_before_restore_backup_filename()
        result = create_instance_backup(
            target,
            progress_callback=progress_callback,
        )
        return Path(result.path).resolve()

    def _show_restore_error(self, parent: QWidget, exc: InstanceRestoreError) -> None:
        code = exc.code
        user = _RESTORE_USER_MESSAGES.get(
            code,
            "Obnova se nepodařila dokončit.",
        )
        extra = ""
        if code == RESTORE_ERR_FAILED_BEFORE_SWAP:
            extra = "<br><br>Původní data zůstala beze změny."
        elif code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK:
            extra = "<br><br>Původní data byla úspěšně vrácena."
        elif code == RESTORE_ERR_ROLLBACK_FAILED:
            marker = exc.marker_path or "—"
            paths = "<br>".join(f"• {p}" for p in (exc.preserved_paths or [])[:20])
            extra = (
                f"<br><br><b>Recovery marker:</b> <code>{marker}</code><br>"
                f"Zachované cesty:<br>{paths or '—'}"
            )

        cause = f" ({exc.cause_code})" if exc.cause_code else ""
        MessageWithDetailsDialog(
            parent,
            title="Obnova ze zálohy",
            message=f"{user}{extra}",
            details=f"kód={code}{cause}\nfáze={exc.phase}\n{exc}",
            level="critical",
        ).exec()


instance_backup_workflow_service = InstanceBackupWorkflowService()
