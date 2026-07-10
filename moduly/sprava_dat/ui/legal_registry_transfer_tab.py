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

from core.services.backup_service import BACKUP_TYPE_FULL
from core.services.file_location_service import open_path_in_file_manager
from core.services.storage_service import storage_service
from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
    legal_registry_export_service,
)
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    RegistryExportRecord,
    RegistryImportRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.sluzby.legal_registry_manifest_service import (
    legal_registry_manifest_service,
)
from moduly.sprava_dat.sluzby.legal_registry_transfer_service import (
    legal_registry_transfer_service,
)
from moduly.sprava_dat.ui.manifest_table_widget import ManifestTableWidget
from moduly.sprava_dat.ui.ui_styles import CONTENT_OVERVIEW_EMPTY, apply_card_group_style


class LegalRegistryTransferTab(QWidget):
    """Záložka přenosu Registru právních požadavků."""

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
        layout.addWidget(self._create_registry_card())
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

    def _wrap_manifest_panel(
        self,
        title: str,
        table: ManifestTableWidget,
        placeholder: QLabel,
    ) -> QWidget:
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

    def _create_registry_card(self) -> QGroupBox:
        group = QGroupBox("Registr právních požadavků")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        layout.addWidget(self._create_controls_section())
        layout.addWidget(self._create_overview_section())
        layout.addWidget(self._create_explanation_section())
        return group

    def _create_controls_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("registryControlsSection")
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        export_box = QGroupBox("Export registru")
        apply_card_group_style(export_box)
        export_layout = QVBoxLayout(export_box)
        self.export_button = QPushButton("Exportovat registr")
        self.export_button.clicked.connect(self._export_registry)
        export_layout.addWidget(self.export_button)
        self.last_export_label = QLabel()
        self.last_export_label.setWordWrap(True)
        export_layout.addWidget(self.last_export_label)
        self.open_export_button = QPushButton("Otevřít umístění")
        self.open_export_button.clicked.connect(self._open_export_location)
        export_layout.addWidget(self.open_export_button)
        export_layout.addStretch()

        import_box = QGroupBox("Import registru")
        apply_card_group_style(import_box)
        import_layout = QVBoxLayout(import_box)
        self.import_button = QPushButton("Importovat registr")
        self.import_button.clicked.connect(self._import_registry)
        import_layout.addWidget(self.import_button)
        self.last_import_label = QLabel()
        self.last_import_label.setWordWrap(True)
        import_layout.addWidget(self.last_import_label)
        self.open_safety_backup_button = QPushButton("Otevřít bezpečnostní zálohu před importem")
        self.open_safety_backup_button.clicked.connect(self._open_safety_backup_location)
        import_layout.addWidget(self.open_safety_backup_button)
        import_layout.addStretch()

        export_box.setMinimumWidth(self._MIN_PANEL_WIDTH)
        import_box.setMinimumWidth(self._MIN_PANEL_WIDTH)
        layout.addWidget(export_box, 1)
        layout.addWidget(import_box, 1)
        return section

    def _create_overview_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)

        left, right, splitter = self._create_split_panel()
        left_layout = left.layout()
        assert left_layout is not None
        right_layout = right.layout()
        assert right_layout is not None

        self.export_manifest_placeholder = QLabel(
            "Přehled obsahu bude dostupný po vytvoření prvního exportu."
        )
        self.export_manifest_placeholder.setWordWrap(True)
        self.export_manifest_table = ManifestTableWidget()
        left_layout.addWidget(
            self._wrap_manifest_panel(
                "Přehled obsahu exportu",
                self.export_manifest_table,
                self.export_manifest_placeholder,
            )
        )

        self.import_manifest_placeholder = QLabel(
            "Výsledek importu bude dostupný po prvním importu."
        )
        self.import_manifest_placeholder.setWordWrap(True)
        self.import_manifest_table = ManifestTableWidget()
        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Výsledek posledního importu",
                self.import_manifest_table,
                self.import_manifest_placeholder,
            )
        )

        layout.addWidget(splitter)
        return section

    def _create_explanation_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("registryExplanationSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        description = QLabel(legal_registry_manifest_service.DESCRIPTION)
        description.setWordWrap(True)
        layout.addWidget(description)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(16)

        includes_box = QWidget()
        includes_layout = QVBoxLayout(includes_box)
        includes_layout.setContentsMargins(0, 0, 0, 0)
        includes_layout.addWidget(QLabel("Obsahuje"))
        for item in legal_registry_manifest_service.INCLUDED_ITEMS:
            includes_layout.addWidget(QLabel(f"✔ {item}"))
        includes_layout.addStretch()

        excludes_box = QWidget()
        excludes_layout = QVBoxLayout(excludes_box)
        excludes_layout.setContentsMargins(0, 0, 0, 0)
        excludes_layout.addWidget(QLabel("Neobsahuje"))
        for item in legal_registry_manifest_service.EXCLUDED_ITEMS:
            excludes_layout.addWidget(QLabel(f"✖ {item}"))
        excludes_layout.addStretch()

        columns_layout.addWidget(includes_box, 1)
        columns_layout.addWidget(excludes_box, 1)
        layout.addWidget(columns)

        warning = QLabel(legal_registry_manifest_service.LINKS_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #8a4b00; font-weight: 600;")
        layout.addWidget(warning)
        return section

    def refresh(self) -> None:
        self._update_last_export_display()
        self._update_last_import_display()

    def _export_registry(self) -> None:
        default_name = legal_registry_export_service.build_default_filename()
        default_path = str(storage_service.exports_dir / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export registru právních požadavků",
            default_path,
            "JSON soubory (*.json);;Všechny soubory (*)",
        )
        if not file_path:
            return

        try:
            legal_registry_export_service.export_to_file(file_path)
            manifest = legal_registry_manifest_service.verify_export_file(file_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Export registru", str(exc))
            return

        if not manifest.get("verified"):
            errors = manifest.get("verification_errors") or ["Export neprošel ověřením."]
            try:
                Path(file_path).unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.critical(
                self,
                "Export registru",
                "Export byl vytvořen, ale neprošel ověřením a nebude uložen jako úspěšný.\n\n"
                + "\n".join(errors),
            )
            return

        record = RegistryExportRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(Path(file_path).resolve()),
            manifest=manifest,
        )
        data_management_settings_service.save_last_registry_export(record)
        self.refresh()

        QMessageBox.information(
            self,
            "Export registru",
            f"Registr byl exportován a ověřen:\n{file_path}",
        )

    def _import_registry(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import registru právních požadavků",
            str(storage_service.exports_dir),
            "JSON soubory (*.json);;Všechny soubory (*)",
        )
        if not file_path:
            return

        confirmed = QMessageBox.warning(
            self,
            "Import registru",
            (
                "Import nahradí aktuální data Registru právních požadavků.\n\n"
                "Před importem bude automaticky vytvořena kompletní bezpečnostní záloha "
                "aktuálního stavu aplikace.\n\n"
                "Auditní metodiky, prověrky, rizika a ostatní moduly nebudou importovány.\n\n"
                "Pokračovat?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        try:
            result = legal_registry_transfer_service.import_with_verified_safety(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Import registru", f"Import se nepodařilo dokončit.\n\n{exc}")
            return

        safety_manifest = result.get("safety_backup_manifest") or {}
        data_management_settings_service.save_last_registry_pre_import_backup(
            BackupRecord(
                created_at=datetime.now().isoformat(timespec="seconds"),
                path=str(result.get("safety_backup_path") or ""),
                manifest=safety_manifest,
                backup_type=BACKUP_TYPE_FULL,
            )
        )
        record = RegistryImportRecord(
            created_at=result.get("imported_at") or datetime.now().isoformat(timespec="seconds"),
            source_path=result.get("source_path") or str(Path(file_path).resolve()),
            safety_backup_path=result.get("safety_backup_path") or "",
            import_result=result,
        )
        data_management_settings_service.save_last_registry_import(record)
        self.refresh()

        counts = result.get("record_counts") or {}
        QMessageBox.information(
            self,
            "Import registru",
            (
                f"Registr byl importován ze souboru:\n{result.get('source_path')}\n\n"
                f"{legal_registry_manifest_service.format_counts_manifest(counts)}\n\n"
                f"Bezpečnostní záloha původního stavu:\n{result.get('safety_backup_path')}\n\n"
                f"{result.get('methodology_warning')}"
            ),
        )

    def _open_export_location(self) -> None:
        record = data_management_settings_service.get_last_registry_export()
        if record is None or not record.path:
            QMessageBox.information(self, "Umístění", "Poslední export registru zatím nebyl vytvořen.")
            return
        open_path_in_file_manager(record.path, parent=self, title="Umístění exportu")

    def _open_safety_backup_location(self) -> None:
        pre_import = data_management_settings_service.get_last_registry_pre_import_backup()
        path = pre_import.path if pre_import is not None else ""
        if not path:
            record = data_management_settings_service.get_last_registry_import()
            path = record.safety_backup_path if record is not None else ""
        if not path:
            QMessageBox.information(
                self,
                "Umístění",
                "Bezpečnostní záloha před importem zatím nebyla vytvořena.",
            )
            return
        open_path_in_file_manager(
            path,
            parent=self,
            title="Bezpečnostní záloha před importem",
        )

    def _update_last_export_display(self) -> None:
        record = data_management_settings_service.get_last_registry_export()
        if record is None:
            self.last_export_label.setText("Poslední export registru: nebyl vytvořen.")
            self.open_export_button.setEnabled(False)
            self._populate_manifest_table(
                self.export_manifest_table,
                self.export_manifest_placeholder,
                [],
                empty_text="Přehled obsahu bude dostupný po vytvoření prvního exportu.",
            )
            return

        file_name = Path(record.path).name
        missing_note = ""
        if not data_management_settings_service.file_exists(record.path):
            missing_note = "\nSoubor nebyl nalezen."

        self.last_export_label.setText(
            "Poslední export registru:\n"
            f"• datum a čas: {data_management_settings_service.format_timestamp(record.created_at)}\n"
            f"• soubor: {file_name}\n"
            f"• cesta: {record.path}{missing_note}"
        )
        self.open_export_button.setEnabled(True)
        self._populate_manifest_table(
            self.export_manifest_table,
            self.export_manifest_placeholder,
            legal_registry_manifest_service.rows_from_record_counts(
                record.manifest.get("record_counts"),
                verified=bool(record.manifest.get("verified")),
            ),
        )

    def _update_last_import_display(self) -> None:
        record = data_management_settings_service.get_last_registry_import()
        if record is None:
            self.last_import_label.setText("Poslední import registru: nebyl proveden.")
            self.open_safety_backup_button.setEnabled(False)
            self._populate_manifest_table(
                self.import_manifest_table,
                self.import_manifest_placeholder,
                [],
                empty_text="Výsledek importu bude dostupný po prvním importu.",
            )
            return

        import_result = record.import_result or {}
        counts = import_result.get("record_counts") or {}
        safety_missing = ""
        if record.safety_backup_path and not data_management_settings_service.file_exists(
            record.safety_backup_path
        ):
            safety_missing = "\nBezpečnostní záloha nebyla nalezena."

        self.last_import_label.setText(
            "Poslední import registru:\n"
            f"• datum a čas: {data_management_settings_service.format_timestamp(record.created_at)}\n"
            f"• importovaný soubor: {record.source_path}\n"
            f"• bezpečnostní záloha: {record.safety_backup_path}{safety_missing}\n"
            f"• výsledek importu: {legal_registry_manifest_service.format_counts_manifest(counts).replace(chr(10), ', ')}"
        )
        self.open_safety_backup_button.setEnabled(bool(record.safety_backup_path))
        self._populate_manifest_table(
            self.import_manifest_table,
            self.import_manifest_placeholder,
            legal_registry_manifest_service.rows_from_record_counts(counts, verified=True),
        )
