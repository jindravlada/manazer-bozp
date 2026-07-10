from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.services.file_location_service import open_path_in_file_manager
from core.services.storage_service import storage_service
from moduly.pravni_pozadavky.import_export.legal_registry_export_service import (
    legal_registry_export_service,
)
from moduly.sprava_dat.sluzby.data_management_settings_service import (
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


class LegalRegistryTransferTab(QWidget):
    """Záložka přenosu Registru právních požadavků."""

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

    def _create_registry_card(self) -> QGroupBox:
        group = QGroupBox("Registr právních požadavků")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        description = QLabel(
            "Slouží k přenosu registru mezi dvěma instalacemi Manažera BOZP."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        includes_label = QLabel("Obsahuje:")
        layout.addWidget(includes_label)
        for item in legal_registry_manifest_service.INCLUDED_ITEMS:
            layout.addWidget(QLabel(f"• {item}"))

        excludes_label = QLabel("Neobsahuje:")
        layout.addWidget(excludes_label)
        for item in legal_registry_manifest_service.EXCLUDED_ITEMS:
            layout.addWidget(QLabel(f"• {item}"))

        warning = QLabel(legal_registry_manifest_service.LINKS_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #8a4b00;")
        layout.addWidget(warning)

        export_title = QLabel("Export registru")
        export_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(export_title)

        self.export_button = QPushButton("Exportovat registr")
        self.export_button.clicked.connect(self._export_registry)
        layout.addWidget(self.export_button)

        self.last_export_label = QLabel()
        self.last_export_label.setWordWrap(True)
        layout.addWidget(self.last_export_label)

        export_manifest_title = QLabel("Manifest posledního exportu:")
        export_manifest_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(export_manifest_title)

        self.export_manifest_label = QLabel()
        self.export_manifest_label.setWordWrap(True)
        self.export_manifest_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.export_manifest_label)

        self.open_export_button = QPushButton("Otevřít umístění exportu")
        self.open_export_button.clicked.connect(self._open_export_location)
        layout.addWidget(self.open_export_button)

        import_title = QLabel("Import registru")
        import_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(import_title)

        self.import_button = QPushButton("Importovat registr")
        self.import_button.clicked.connect(self._import_registry)
        layout.addWidget(self.import_button)

        last_import_title = QLabel("Poslední import registru:")
        last_import_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(last_import_title)

        self.last_import_label = QLabel()
        self.last_import_label.setWordWrap(True)
        layout.addWidget(self.last_import_label)

        self.open_safety_backup_button = QPushButton("Otevřít bezpečnostní zálohu před importem")
        self.open_safety_backup_button.clicked.connect(self._open_safety_backup_location)
        layout.addWidget(self.open_safety_backup_button)

        return group

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
        record = data_management_settings_service.get_last_registry_import()
        if record is None or not record.safety_backup_path:
            QMessageBox.information(
                self,
                "Umístění",
                "Bezpečnostní záloha před importem zatím nebyla vytvořena.",
            )
            return
        open_path_in_file_manager(
            record.safety_backup_path,
            parent=self,
            title="Bezpečnostní záloha před importem",
        )

    def _update_last_export_display(self) -> None:
        record = data_management_settings_service.get_last_registry_export()
        if record is None:
            self.last_export_label.setText("Poslední export registru: nebyl vytvořen.")
            self.export_manifest_label.setText("—")
            self.open_export_button.setEnabled(False)
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
        self.export_manifest_label.setText(
            legal_registry_manifest_service.format_counts_manifest(
                record.manifest.get("record_counts")
            )
        )
        self.open_export_button.setEnabled(True)

    def _update_last_import_display(self) -> None:
        record = data_management_settings_service.get_last_registry_import()
        if record is None:
            self.last_import_label.setText("—")
            self.open_safety_backup_button.setEnabled(False)
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
            f"• zdrojový soubor: {record.source_path}\n"
            f"• bezpečnostní záloha: {record.safety_backup_path}{safety_missing}\n"
            f"• výsledek importu:\n{legal_registry_manifest_service.format_counts_manifest(counts)}"
        )
        self.open_safety_backup_button.setEnabled(bool(record.safety_backup_path))
