"""Sdílený workflow kompletní zálohy a obnovy pro Dashboard a Správu dat."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    data_management_settings_service,
)


class FullBackupWorkflowService:
    def create_full_backup(self, parent: QWidget) -> bool:
        default_path = str(backup_service.default_backup_path(BACKUP_TYPE_FULL))
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Uložit – Celková záloha",
            default_path,
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return False
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"

        try:
            result_path = backup_service.create_backup(file_path, backup_type=BACKUP_TYPE_FULL)
            manifest = backup_service.verify_backup_integrity(result_path, backup_type=BACKUP_TYPE_FULL)
        except Exception as exc:
            QMessageBox.critical(
                parent,
                "Kompletní záloha programu",
                f"Zálohu se nepodařilo vytvořit.\n\n{exc}",
            )
            return False

        if not manifest.get("verified"):
            errors = manifest.get("verification_errors") or ["Záloha neprošla ověřením."]
            try:
                Path(result_path).unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.critical(
                parent,
                "Kompletní záloha programu",
                "Záloha byla vytvořena, ale neprošla ověřením a nebude uložena jako úspěšná.\n\n"
                + "\n".join(errors),
            )
            return False

        record = BackupRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(Path(result_path).resolve()),
            manifest=manifest,
            backup_type=BACKUP_TYPE_FULL,
        )
        data_management_settings_service.save_last_backup(record)

        QMessageBox.information(
            parent,
            "Kompletní záloha programu",
            f"Záloha byla vytvořena a ověřena:\n{result_path}",
        )
        return True

    def restore_full_backup(self, parent: QWidget) -> bool:
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Vybrat – Celková obnova",
            str(backup_service.default_backup_path().parent),
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return False

        answer = QMessageBox.question(
            parent,
            "Obnova kompletní zálohy",
            (
                "Obnova přepíše celé pracovní prostředí: databázi, přílohy, exporty, "
                "šablony a editovatelné číselníky.\n\n"
                "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu.\n\n"
                "Pokračovat?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False

        try:
            result = backup_service.restore_backup_with_verified_safety(
                file_path,
                restore_type=BACKUP_TYPE_FULL,
            )
        except Exception as exc:
            QMessageBox.critical(
                parent,
                "Obnova kompletní zálohy",
                f"Obnovu se nepodařilo dokončit.\n\n{exc}",
            )
            return False

        safety_manifest = result.get("safety_backup_manifest") or {}
        safety_record = BackupRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(result.get("safety_backup_path") or ""),
            manifest=safety_manifest,
            backup_type=BACKUP_TYPE_FULL,
        )
        data_management_settings_service.save_last_pre_restore_backup(safety_record)
        data_management_settings_service.save_last_restore_result(result)

        integrity = result.get("integrity_check") or {}
        integrity_status = "úspěšná" if integrity.get("verified") else "neúspěšná"

        QMessageBox.information(
            parent,
            "Obnova kompletní zálohy",
            (
                f"Obnovena záloha:\n{result.get('restored_path')}\n\n"
                f"Bezpečnostní záloha původního stavu:\n{result.get('safety_backup_path')}\n\n"
                f"Čas obnovy: {data_management_settings_service.format_timestamp(result.get('restored_at', ''))}\n"
                f"Kontrola integrity: {integrity_status}"
            ),
        )

        if backup_service.requires_restart_after_restore(BACKUP_TYPE_FULL):
            from PySide6.QtWidgets import QApplication

            QMessageBox.information(
                parent,
                "Obnova kompletní zálohy",
                "Data byla obnovena. Aplikace se nyní ukončí. "
                "Po novém spuštění se načtou obnovená data.",
            )
            QApplication.quit()

        return True


full_backup_workflow_service = FullBackupWorkflowService()
