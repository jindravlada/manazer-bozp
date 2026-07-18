from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.services.file_location_service import open_path_in_file_manager
from moduly.sprava_dat.sluzby.codebook_catalog_service import codebook_catalog_service
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    data_management_settings_service,
)
from moduly.sprava_dat.sluzby.data_management_status_service import (
    data_management_status_service,
)
from moduly.sprava_dat.ui.manifest_presenter import STATUS_ATTENTION, STATUS_OK
from moduly.sprava_dat.ui.ui_styles import apply_card_group_style
from moduly.sprava_dat.ui.tab_constants import (
    TAB_BACKUP,
    TAB_CODEBOOKS,
    TAB_DIAGNOSTICS,
    TAB_TRANSFER,
)


class SummaryTab(QWidget):
    """Rychlý souhrn stavu dat a posledních operací."""

    def __init__(
        self,
        navigate_callback: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._navigate = navigate_callback
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

        self.status_title = QLabel("Stav dat")
        self.status_title.setStyleSheet("font-weight: 700; font-size: 16px;")
        layout.addWidget(self.status_title)

        self.status_value = QLabel()
        self.status_value.setWordWrap(True)
        layout.addWidget(self.status_value)

        self.warnings_label = QLabel()
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        layout.addWidget(self._create_backup_restore_row())
        layout.addWidget(self._create_registry_section())
        layout.addWidget(self._create_codebooks_section())
        layout.addWidget(self._create_diagnostics_section())
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _create_backup_restore_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("summaryBackupRestoreRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)

        backup_group = self._create_backup_section()
        restore_group = self._create_restore_section()
        backup_group.setMinimumWidth(280)
        restore_group.setMinimumWidth(280)
        row_layout.addWidget(backup_group, 1)
        row_layout.addWidget(restore_group, 1)
        return row

    def _create_backup_section(self) -> QGroupBox:
        group = QGroupBox("Kompletní záloha")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        self.backup_summary_label = QLabel()
        self.backup_summary_label.setWordWrap(True)
        layout.addWidget(self.backup_summary_label)

        buttons = QHBoxLayout()
        self.open_backup_button = QPushButton("Otevřít umístění")
        self.open_backup_button.clicked.connect(self._open_backup_location)
        buttons.addWidget(self.open_backup_button)
        buttons.addWidget(self._nav_button(f"Přejít na {TAB_BACKUP}", TAB_BACKUP))
        buttons.addStretch()
        layout.addLayout(buttons)
        return group

    def _create_restore_section(self) -> QGroupBox:
        group = QGroupBox("Obnova kompletní zálohy")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        self.restore_summary_label = QLabel()
        self.restore_summary_label.setWordWrap(True)
        layout.addWidget(self.restore_summary_label)

        buttons = QHBoxLayout()
        self.open_restore_safety_button = QPushButton("Otevřít umístění bezpečnostní zálohy")
        self.open_restore_safety_button.clicked.connect(self._open_restore_safety_location)
        buttons.addWidget(self.open_restore_safety_button)
        buttons.addWidget(self._nav_button(f"Přejít na {TAB_BACKUP}", TAB_BACKUP))
        buttons.addStretch()
        layout.addLayout(buttons)
        return group

    def _create_registry_section(self) -> QGroupBox:
        group = QGroupBox("Registr právních požadavků")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        self.registry_summary_label = QLabel()
        self.registry_summary_label.setWordWrap(True)
        layout.addWidget(self.registry_summary_label)

        buttons = QHBoxLayout()
        self.open_registry_button = QPushButton("Otevřít umístění")
        self.open_registry_button.clicked.connect(self._open_registry_location)
        buttons.addWidget(self.open_registry_button)
        buttons.addWidget(self._nav_button("Přejít na Přenos dat", TAB_TRANSFER))
        buttons.addStretch()
        layout.addLayout(buttons)
        return group

    def _create_codebooks_section(self) -> QGroupBox:
        group = QGroupBox("Číselníky")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        self.codebooks_summary_label = QLabel()
        self.codebooks_summary_label.setWordWrap(True)
        layout.addWidget(self.codebooks_summary_label)

        buttons = QHBoxLayout()
        self.open_codebooks_button = QPushButton("Otevřít umístění")
        self.open_codebooks_button.clicked.connect(self._open_codebooks_location)
        buttons.addWidget(self.open_codebooks_button)
        buttons.addWidget(self._nav_button("Přejít na Číselníky", TAB_CODEBOOKS))
        buttons.addStretch()
        layout.addLayout(buttons)
        return group

    def _create_diagnostics_section(self) -> QGroupBox:
        group = QGroupBox("Diagnostika")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        self.diagnostics_summary_label = QLabel()
        self.diagnostics_summary_label.setWordWrap(True)
        layout.addWidget(self.diagnostics_summary_label)

        buttons = QHBoxLayout()
        buttons.addWidget(self._nav_button("Přejít na Diagnostiku", TAB_DIAGNOSTICS))
        buttons.addStretch()
        layout.addLayout(buttons)
        return group

    def _nav_button(self, text: str, tab_key: str) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda: self._navigate(tab_key))
        return button

    def refresh(self) -> None:
        status, warnings = data_management_status_service.compute_status()
        self.status_value.setText(f"Stav dat: {status}")
        if status == STATUS_ATTENTION:
            self.status_value.setStyleSheet("color: #8a4b00; font-weight: 600;")
        else:
            self.status_value.setStyleSheet("color: #1b5e20; font-weight: 600;")

        if warnings:
            self.warnings_label.setText("\n".join(f"• {warning}" for warning in warnings))
        else:
            self.warnings_label.setText("• Všechny známé operace jsou v pořádku.")

        self._update_backup_section()
        self._update_restore_section()
        self._update_registry_section()
        self._update_codebooks_section()
        self._update_diagnostics_section()

    def _update_backup_section(self) -> None:
        record = data_management_settings_service.get_last_backup()
        status = data_management_status_service.backup_status_text()
        if record is None:
            self.backup_summary_label.setText(
                "Datum a čas: —\nNázev souboru: —\nStav: nikdy nevytvořena"
            )
            self.open_backup_button.setEnabled(False)
            return

        self.backup_summary_label.setText(
            f"Datum a čas: {data_management_settings_service.format_timestamp(record.created_at)}\n"
            f"Název souboru: {Path(record.path).name}\n"
            f"Stav: {status}"
        )
        self.open_backup_button.setEnabled(bool(record.path))

    def _update_restore_section(self) -> None:
        restore = data_management_settings_service.get_last_restore_result()
        pre_restore = data_management_settings_service.get_last_pre_restore_backup()
        status = data_management_status_service.restore_status_text()
        if restore is None:
            self.restore_summary_label.setText(
                "Datum a čas: —\nObnovený soubor: —\nBezpečnostní záloha: —\nStav obnovy: dosud neprovedena"
            )
            self.open_restore_safety_button.setEnabled(False)
            return

        restored_name = Path(str(restore.get("restored_path") or "")).name or "—"
        safety_path = (
            pre_restore.path
            if pre_restore is not None
            else str(restore.get("safety_backup_path") or "—")
        )
        self.restore_summary_label.setText(
            f"Datum a čas: {data_management_settings_service.format_timestamp(restore.get('restored_at', ''))}\n"
            f"Obnovený soubor: {restored_name}\n"
            f"Bezpečnostní záloha: {safety_path}\n"
            f"Stav obnovy: {status}"
        )
        self.open_restore_safety_button.setEnabled(bool(safety_path and safety_path != "—"))

    def _update_registry_section(self) -> None:
        export = data_management_settings_service.get_last_registry_export()
        import_record = data_management_settings_service.get_last_registry_import()
        status = data_management_status_service.registry_status_text()

        export_time = (
            data_management_settings_service.format_timestamp(export.created_at)
            if export is not None
            else "—"
        )
        import_time = (
            data_management_settings_service.format_timestamp(import_record.created_at)
            if import_record is not None
            else "—"
        )
        self.registry_summary_label.setText(
            f"Poslední export: {export_time}\n"
            f"Poslední import: {import_time}\n"
            f"Stav poslední operace: {status}"
        )
        has_location = export is not None and bool(export.path)
        self.open_registry_button.setEnabled(has_location)

    def _update_codebooks_section(self) -> None:
        export = data_management_settings_service.get_last_codebooks_export()
        import_record = data_management_settings_service.get_last_codebooks_import()
        status = data_management_status_service.codebooks_status_text()
        count = codebook_catalog_service.count_all()

        export_time = (
            data_management_settings_service.format_timestamp(export.created_at)
            if export is not None
            else "—"
        )
        import_time = (
            data_management_settings_service.format_timestamp(import_record.created_at)
            if import_record is not None
            else "—"
        )
        self.codebooks_summary_label.setText(
            f"Poslední export: {export_time}\n"
            f"Poslední import: {import_time}\n"
            f"Počet evidovaných číselníků: {count}\n"
            f"Stav poslední operace: {status}"
        )
        self.open_codebooks_button.setEnabled(export is not None and bool(export.path))

    def _update_diagnostics_section(self) -> None:
        diagnostic = data_management_settings_service.get_last_diagnostic()
        if diagnostic is None:
            self.diagnostics_summary_label.setText("Diagnostika zatím nebyla spuštěna.")
            return

        self.diagnostics_summary_label.setText(
            f"Datum: {data_management_settings_service.format_timestamp(diagnostic.get('created_at', ''))}\n"
            f"Výsledek: {diagnostic.get('summary', '—')}"
        )

    def _open_backup_location(self) -> None:
        record = data_management_settings_service.get_last_backup()
        if record is None or not record.path:
            return
        open_path_in_file_manager(record.path, parent=self, title="Umístění zálohy")

    def _open_restore_safety_location(self) -> None:
        pre_restore = data_management_settings_service.get_last_pre_restore_backup()
        path = pre_restore.path if pre_restore is not None else ""
        if not path:
            restore = data_management_settings_service.get_last_restore_result()
            path = str((restore or {}).get("safety_backup_path") or "")
        if not path:
            return
        open_path_in_file_manager(path, parent=self, title="Bezpečnostní záloha")

    def _open_registry_location(self) -> None:
        export = data_management_settings_service.get_last_registry_export()
        if export is None or not export.path:
            return
        open_path_in_file_manager(export.path, parent=self, title="Umístění exportu")

    def _open_codebooks_location(self) -> None:
        export = data_management_settings_service.get_last_codebooks_export()
        if export is None or not export.path:
            return
        open_path_in_file_manager(export.path, parent=self, title="Umístění exportu číselníků")
