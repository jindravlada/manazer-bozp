from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.services.backup_manifest_service import backup_manifest_service
from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
from core.services.file_location_service import open_path_in_file_manager
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    data_management_settings_service,
)


class BackupTab(QWidget):
    """Záložka kompletní zálohy a obnovy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._create_backup_card())
        layout.addWidget(self._create_restore_card())
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _create_backup_card(self) -> QGroupBox:
        group = QGroupBox("Kompletní záloha programu")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        description = QLabel(
            "Vytvoří úplnou zálohu uživatelských dat Manažera BOZP pro obnovu po havárii "
            "nebo přenos na jiné zařízení."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        contents_label = QLabel("Záloha obsahuje:")
        layout.addWidget(contents_label)
        for item in backup_manifest_service.full_backup_content_labels():
            layout.addWidget(QLabel(f"• {item}"))

        self.create_backup_button = QPushButton("Vytvořit kompletní zálohu")
        self.create_backup_button.clicked.connect(self._create_full_backup)
        layout.addWidget(self.create_backup_button)

        self.last_backup_label = QLabel()
        self.last_backup_label.setWordWrap(True)
        layout.addWidget(self.last_backup_label)

        self.open_last_backup_button = QPushButton("Otevřít umístění")
        self.open_last_backup_button.clicked.connect(self._open_last_backup_location)
        layout.addWidget(self.open_last_backup_button)

        manifest_title = QLabel("Manifest poslední zálohy:")
        manifest_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(manifest_title)

        self.manifest_label = QLabel()
        self.manifest_label.setWordWrap(True)
        self.manifest_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.manifest_label)

        return group

    def _create_restore_card(self) -> QGroupBox:
        group = QGroupBox("Obnova kompletní zálohy")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        description = QLabel(
            "Obnoví databázi, číselníky, metodiky a další uživatelská data ze zvolené kompletní zálohy."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        safety_note = QLabel(
            "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu."
        )
        safety_note.setWordWrap(True)
        layout.addWidget(safety_note)

        self.restore_backup_button = QPushButton("Obnovit kompletní zálohu")
        self.restore_backup_button.clicked.connect(self._restore_full_backup)
        layout.addWidget(self.restore_backup_button)

        pre_restore_title = QLabel("Poslední záloha před obnovou:")
        pre_restore_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(pre_restore_title)

        self.pre_restore_label = QLabel()
        self.pre_restore_label.setWordWrap(True)
        layout.addWidget(self.pre_restore_label)

        self.open_pre_restore_button = QPushButton("Otevřít umístění")
        self.open_pre_restore_button.clicked.connect(self._open_pre_restore_location)
        layout.addWidget(self.open_pre_restore_button)

        restore_result_title = QLabel("Poslední obnova:")
        restore_result_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(restore_result_title)

        self.restore_result_label = QLabel()
        self.restore_result_label.setWordWrap(True)
        layout.addWidget(self.restore_result_label)

        return group

    def refresh(self) -> None:
        self._update_last_backup_display()
        self._update_pre_restore_display()
        self._update_restore_result_display()

    def _create_full_backup(self) -> None:
        default_path = str(backup_service.default_backup_path(BACKUP_TYPE_FULL))
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit – Celková záloha",
            default_path,
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"

        try:
            result_path = backup_service.create_backup(file_path, backup_type=BACKUP_TYPE_FULL)
            manifest = backup_service.verify_backup_integrity(result_path, backup_type=BACKUP_TYPE_FULL)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Kompletní záloha programu",
                f"Zálohu se nepodařilo vytvořit.\n\n{exc}",
            )
            return

        if not manifest.get("verified"):
            errors = manifest.get("verification_errors") or ["Záloha neprošla ověřením."]
            try:
                Path(result_path).unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.critical(
                self,
                "Kompletní záloha programu",
                "Záloha byla vytvořena, ale neprošla ověřením a nebude uložena jako úspěšná.\n\n"
                + "\n".join(errors),
            )
            return

        record = BackupRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(Path(result_path).resolve()),
            manifest=manifest,
            backup_type=BACKUP_TYPE_FULL,
        )
        data_management_settings_service.save_last_backup(record)
        self.refresh()

        QMessageBox.information(
            self,
            "Kompletní záloha programu",
            f"Záloha byla vytvořena a ověřena:\n{result_path}",
        )

    def _restore_full_backup(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat – Celková obnova",
            str(backup_service.default_backup_path().parent),
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return

        answer = QMessageBox.question(
            self,
            "Obnova kompletní zálohy",
            (
                "Obnova přepíše celé pracovní prostředí: databázi, přílohy, exporty, "
                "šablony a editovatelné číselníky.\n\n"
                "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu.\n\n"
                "Pokračovat?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            result = backup_service.restore_backup_with_verified_safety(
                file_path,
                restore_type=BACKUP_TYPE_FULL,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Obnova kompletní zálohy",
                f"Obnovu se nepodařilo dokončit.\n\n{exc}",
            )
            return

        safety_manifest = result.get("safety_backup_manifest") or {}
        safety_record = BackupRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(result.get("safety_backup_path") or ""),
            manifest=safety_manifest,
            backup_type=BACKUP_TYPE_FULL,
        )
        data_management_settings_service.save_last_pre_restore_backup(safety_record)
        data_management_settings_service.save_last_restore_result(result)
        self.refresh()

        integrity = result.get("integrity_check") or {}
        integrity_status = "úspěšná" if integrity.get("verified") else "neúspěšná"

        QMessageBox.information(
            self,
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
                self,
                "Obnova kompletní zálohy",
                "Data byla obnovena. Aplikace se nyní ukončí. "
                "Po novém spuštění se načtou obnovená data.",
            )
            QApplication.quit()

    def _open_last_backup_location(self) -> None:
        record = data_management_settings_service.get_last_backup()
        if record is None or not record.path:
            QMessageBox.information(self, "Umístění", "Poslední záloha nebyla vytvořena.")
            return
        open_path_in_file_manager(record.path, parent=self, title="Umístění zálohy")

    def _open_pre_restore_location(self) -> None:
        record = data_management_settings_service.get_last_pre_restore_backup()
        if record is None or not record.path:
            QMessageBox.information(
                self,
                "Umístění",
                "Záloha před obnovou zatím nebyla vytvořena.",
            )
            return
        open_path_in_file_manager(record.path, parent=self, title="Umístění zálohy")

    def _update_last_backup_display(self) -> None:
        record = data_management_settings_service.get_last_backup()
        if record is None:
            self.last_backup_label.setText("Poslední záloha: nebyla vytvořena.")
            self.open_last_backup_button.setEnabled(False)
            self.manifest_label.setText("—")
            return

        file_name = Path(record.path).name
        missing_note = ""
        if not data_management_settings_service.file_exists(record.path):
            missing_note = "\nSoubor nebyl nalezen."

        self.last_backup_label.setText(
            "Poslední záloha:\n"
            f"• datum a čas: {data_management_settings_service.format_timestamp(record.created_at)}\n"
            f"• název souboru: {file_name}\n"
            f"• cesta: {record.path}{missing_note}"
        )
        self.open_last_backup_button.setEnabled(True)
        self.manifest_label.setText(self._format_manifest(record.manifest))

    def _update_pre_restore_display(self) -> None:
        record = data_management_settings_service.get_last_pre_restore_backup()
        if record is None:
            self.pre_restore_label.setText("—")
            self.open_pre_restore_button.setEnabled(False)
            return

        file_name = Path(record.path).name
        missing_note = ""
        if not data_management_settings_service.file_exists(record.path):
            missing_note = "\nSoubor nebyl nalezen."

        self.pre_restore_label.setText(
            f"• datum a čas: {data_management_settings_service.format_timestamp(record.created_at)}\n"
            f"• název souboru: {file_name}\n"
            f"• cesta: {record.path}{missing_note}"
        )
        self.open_pre_restore_button.setEnabled(True)

    def _update_restore_result_display(self) -> None:
        result = data_management_settings_service.get_last_restore_result()
        if not result:
            self.restore_result_label.setText("—")
            return

        integrity = result.get("integrity_check") or {}
        integrity_status = "úspěšná" if integrity.get("verified") else "neúspěšná"
        self.restore_result_label.setText(
            f"• obnovená záloha: {result.get('restored_path', '—')}\n"
            f"• bezpečnostní záloha: {result.get('safety_backup_path', '—')}\n"
            f"• čas obnovy: {data_management_settings_service.format_timestamp(result.get('restored_at', ''))}\n"
            f"• kontrola integrity: {integrity_status}"
        )

    def _format_manifest(self, manifest: dict | None) -> str:
        if not manifest:
            return "—"

        db_counts = manifest.get("database_counts") or {}
        lines = [
            f"• cesta k databázi: {manifest.get('workspace_database_path', manifest.get('database_path', '—'))}",
            f"• databáze v záloze: {'ano' if manifest.get('database_included') else 'ne'}",
            f"• ZIP lze otevřít: {'ano' if manifest.get('zip_readable') else 'ne'}",
            f"• kontrolní součty ZIPu: {'v pořádku' if manifest.get('zip_crc_ok') else 'chyba'}",
            f"• počet souborů v záloze: {manifest.get('file_count', 0)}",
            f"• globální číselníky: {manifest.get('global_catalogs', 0)}",
            f"• modulové číselníky: {manifest.get('module_catalogs', 0)}",
            f"• auditní metodiky: {manifest.get('audit_methodologies', 0)}",
            f"• metodiky prověrek: {manifest.get('proverky_methodologies', 0)}",
            f"• právní předpisy: {db_counts.get('legal_documents', 0)}",
            f"• řídicí procesy: {db_counts.get('control_processes', 0)}",
            f"• úkoly: {db_counts.get('tasks', 0)}",
            f"• pracovní úrazy: {db_counts.get('accidents', 0)}",
            f"• audity: {db_counts.get('audits', 0)}",
            f"• prověrky: {db_counts.get('inspections', 0)}",
            f"• ověření zálohy: {'úspěšné' if manifest.get('verified') else 'neúspěšné'}",
        ]
        return "\n".join(lines)
