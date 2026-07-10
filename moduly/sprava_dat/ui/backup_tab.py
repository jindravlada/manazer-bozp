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
    QSplitter,
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
from moduly.sprava_dat.ui.manifest_presenter import rows_from_backup_manifest, rows_from_integrity_manifest
from moduly.sprava_dat.ui.manifest_table_widget import ManifestTableWidget
from moduly.sprava_dat.ui.ui_styles import CONTENT_OVERVIEW_EMPTY, apply_card_group_style


class BackupTab(QWidget):
    """Záložka kompletní zálohy a obnovy."""

    _MIN_PANEL_WIDTH = 280

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

    def _create_split_panel(self) -> tuple[QWidget, QWidget, QSplitter]:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left.setMinimumWidth(self._MIN_PANEL_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)

        right = QWidget()
        right.setMinimumWidth(self._MIN_PANEL_WIDTH)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 500])

        return left, right, splitter

    def _wrap_manifest_panel(self, title: str, table: ManifestTableWidget, placeholder: QLabel) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 600;")
        frame_layout.addWidget(heading)
        frame_layout.addWidget(placeholder)
        frame_layout.addWidget(table)
        layout.addWidget(frame)
        return panel

    def _create_backup_card(self) -> QGroupBox:
        group = QGroupBox("Kompletní záloha programu")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)

        left, right, splitter = self._create_split_panel()
        left_layout = left.layout()
        assert left_layout is not None
        right_layout = right.layout()
        assert right_layout is not None

        description = QLabel(
            "Vytvoří úplnou zálohu uživatelských dat Manažera BOZP pro obnovu po havárii "
            "nebo přenos na jiné zařízení."
        )
        description.setWordWrap(True)
        left_layout.addWidget(description)

        contents_label = QLabel("Záloha obsahuje:")
        left_layout.addWidget(contents_label)
        for item in backup_manifest_service.full_backup_content_labels():
            left_layout.addWidget(QLabel(f"• {item}"))

        self.create_backup_button = QPushButton("Vytvořit kompletní zálohu")
        self.create_backup_button.clicked.connect(self._create_full_backup)
        left_layout.addWidget(self.create_backup_button)

        self.last_backup_label = QLabel()
        self.last_backup_label.setWordWrap(True)
        left_layout.addWidget(self.last_backup_label)

        self.open_last_backup_button = QPushButton("Otevřít umístění")
        self.open_last_backup_button.clicked.connect(self._open_last_backup_location)
        left_layout.addWidget(self.open_last_backup_button)
        left_layout.addStretch()

        self.backup_manifest_placeholder = QLabel(
            "Přehled obsahu bude dostupný po vytvoření první zálohy."
        )
        self.backup_manifest_placeholder.setWordWrap(True)
        self.backup_manifest_table = ManifestTableWidget()
        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Přehled obsahu poslední zálohy",
                self.backup_manifest_table,
                self.backup_manifest_placeholder,
            )
        )

        layout.addWidget(splitter)
        return group

    def _create_restore_card(self) -> QGroupBox:
        group = QGroupBox("Obnova kompletní zálohy")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)

        left, right, splitter = self._create_split_panel()
        left_layout = left.layout()
        assert left_layout is not None
        right_layout = right.layout()
        assert right_layout is not None

        description = QLabel(
            "Obnoví databázi, číselníky, metodiky a další uživatelská data ze zvolené kompletní zálohy."
        )
        description.setWordWrap(True)
        left_layout.addWidget(description)

        safety_note = QLabel(
            "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu."
        )
        safety_note.setWordWrap(True)
        left_layout.addWidget(safety_note)

        self.restore_backup_button = QPushButton("Obnovit kompletní zálohu")
        self.restore_backup_button.clicked.connect(self._restore_full_backup)
        left_layout.addWidget(self.restore_backup_button)

        pre_restore_title = QLabel("Poslední záloha před obnovou:")
        pre_restore_title.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(pre_restore_title)

        self.pre_restore_label = QLabel()
        self.pre_restore_label.setWordWrap(True)
        left_layout.addWidget(self.pre_restore_label)

        self.open_pre_restore_button = QPushButton("Otevřít umístění")
        self.open_pre_restore_button.clicked.connect(self._open_pre_restore_location)
        left_layout.addWidget(self.open_pre_restore_button)

        restore_result_title = QLabel("Poslední obnova:")
        restore_result_title.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(restore_result_title)

        self.restore_result_label = QLabel()
        self.restore_result_label.setWordWrap(True)
        left_layout.addWidget(self.restore_result_label)
        left_layout.addStretch()

        self.safety_manifest_placeholder = QLabel(
            "Přehled obsahu bezpečnostní zálohy bude dostupný po první obnově."
        )
        self.safety_manifest_placeholder.setWordWrap(True)
        self.safety_manifest_table = ManifestTableWidget()

        self.integrity_manifest_placeholder = QLabel(
            "Výsledek kontroly integrity bude dostupný po první obnově."
        )
        self.integrity_manifest_placeholder.setWordWrap(True)
        self.integrity_manifest_table = ManifestTableWidget()

        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Přehled obsahu bezpečnostní zálohy před obnovou",
                self.safety_manifest_table,
                self.safety_manifest_placeholder,
            )
        )
        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Kontrola integrity poslední obnovy",
                self.integrity_manifest_table,
                self.integrity_manifest_placeholder,
            )
        )

        layout.addWidget(splitter)
        return group

    def refresh(self) -> None:
        self._update_last_backup_display()
        self._update_pre_restore_display()
        self._update_restore_result_display()
        self._update_restore_manifests()

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
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
            self.backup_manifest_placeholder.setVisible(True)
            self.backup_manifest_table.setVisible(False)
            self.backup_manifest_table.setRowCount(0)
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
        self._populate_manifest_table(
            self.backup_manifest_table,
            self.backup_manifest_placeholder,
            rows_from_backup_manifest(record.manifest),
        )

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

    def _update_restore_manifests(self) -> None:
        pre_restore = data_management_settings_service.get_last_pre_restore_backup()
        restore = data_management_settings_service.get_last_restore_result()

        safety_rows = rows_from_backup_manifest(pre_restore.manifest if pre_restore else None)
        self._populate_manifest_table(
            self.safety_manifest_table,
            self.safety_manifest_placeholder,
            safety_rows,
            empty_text="Přehled obsahu bezpečnostní zálohy bude dostupný po první obnově.",
        )

        integrity_rows = rows_from_integrity_manifest(
            (restore or {}).get("integrity_check") if restore else None
        )
        self._populate_manifest_table(
            self.integrity_manifest_table,
            self.integrity_manifest_placeholder,
            integrity_rows,
            empty_text="Výsledek kontroly integrity bude dostupný po první obnově.",
        )

    @staticmethod
    def _populate_manifest_table(
        table: ManifestTableWidget,
        placeholder: QLabel,
        rows: list[tuple[str, str, str]],
        *,
        empty_text: str | None = None,
    ) -> None:
        if not rows:
            placeholder.setText(empty_text or CONTENT_OVERVIEW_EMPTY)
            placeholder.setVisible(True)
            table.setVisible(False)
            table.setRowCount(0)
            return

        placeholder.setVisible(False)
        table.setVisible(True)
        table.set_rows(rows)
