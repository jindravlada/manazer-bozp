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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.backup_service import BACKUP_TYPE_FULL
from core.services.file_location_service import open_path_in_file_manager
from core.services.storage_service import storage_service
from moduly.sprava_dat.sluzby.codebook_catalog_service import (
    MODULE_ORDER,
    CodebookEntry,
    codebook_catalog_service,
)
from moduly.sprava_dat.sluzby.codebook_export_service import codebook_export_service
from moduly.sprava_dat.sluzby.codebook_import_service import codebook_import_service
from moduly.sprava_dat.sluzby.codebook_manifest_service import codebook_manifest_service
from moduly.sprava_dat.sluzby.codebook_transfer_service import codebook_transfer_service
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    CodebooksExportRecord,
    CodebooksImportRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.ui.manifest_table_widget import ManifestTableWidget
from moduly.sprava_dat.ui.ui_styles import CONTENT_OVERVIEW_EMPTY, apply_card_group_style


GROUP_PREFIX = "group:"

class CodebooksTab(QWidget):
    """Záložka centrální správy číselníků."""

    _MIN_PANEL_WIDTH = 280

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_entry: CodebookEntry | None = None
        self._selected_group: str | None = None
        self._last_single_export_path: str = ""
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

        layout.addWidget(self._create_catalog_card())
        layout.addWidget(self._create_bulk_card())
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
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 600;")
        frame_layout.addWidget(heading)
        frame_layout.addWidget(placeholder)
        frame_layout.addWidget(table)
        panel_layout.addWidget(frame)
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

    def _create_catalog_card(self) -> QGroupBox:
        group = QGroupBox("Přehled číselníků")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)

        left, right, splitter = self._create_split_panel()
        left_layout = left.layout()
        assert left_layout is not None
        right_layout = right.layout()
        assert right_layout is not None

        description = QLabel(
            "Centrální přehled všech číselníků Manažera BOZP. Vyberte skupinu nebo číselník vlevo "
            "a zobrazí se informace, export a import."
        )
        description.setWordWrap(True)
        left_layout.addWidget(description)

        self.catalog_tree = QTreeWidget()
        self.catalog_tree.setHeaderHidden(True)
        self.catalog_tree.currentItemChanged.connect(self._on_catalog_selection_changed)
        left_layout.addWidget(self.catalog_tree)

        self.detail_title = QLabel("Vyberte skupinu nebo číselník")
        self.detail_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        right_layout.addWidget(self.detail_title)

        self.detail_name = QLabel()
        self.detail_name.setWordWrap(True)
        right_layout.addWidget(self.detail_name)

        self.detail_module = QLabel()
        self.detail_module.setWordWrap(True)
        right_layout.addWidget(self.detail_module)

        self.detail_count = QLabel()
        right_layout.addWidget(self.detail_count)

        self.detail_storage = QLabel()
        right_layout.addWidget(self.detail_storage)

        self.detail_path = QLabel()
        self.detail_path.setWordWrap(True)
        right_layout.addWidget(self.detail_path)

        self.detail_modified = QLabel()
        right_layout.addWidget(self.detail_modified)

        self.detail_list = QLabel()
        self.detail_list.setWordWrap(True)
        right_layout.addWidget(self.detail_list)

        buttons = QHBoxLayout()
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._export_selected)
        self.export_button.setEnabled(False)
        buttons.addWidget(self.export_button)

        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self._import_selected)
        self.import_button.setEnabled(False)
        buttons.addWidget(self.import_button)

        self.export_group_button = QPushButton("Exportovat skupinu")
        self.export_group_button.clicked.connect(self._export_group)
        self.export_group_button.setEnabled(False)
        buttons.addWidget(self.export_group_button)

        self.import_group_button = QPushButton("Importovat skupinu")
        self.import_group_button.clicked.connect(self._import_group)
        self.import_group_button.setEnabled(False)
        buttons.addWidget(self.import_group_button)
        buttons.addStretch()
        right_layout.addLayout(buttons)

        self.single_manifest_placeholder = QLabel(
            "Přehled obsahu exportu bude dostupný po exportu vybrané položky."
        )
        self.single_manifest_placeholder.setWordWrap(True)
        self.single_manifest_table = ManifestTableWidget()
        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Přehled obsahu exportu",
                self.single_manifest_table,
                self.single_manifest_placeholder,
            )
        )

        self.open_single_export_button = QPushButton("Otevřít umístění")
        self.open_single_export_button.clicked.connect(self._open_single_export_location)
        self.open_single_export_button.setEnabled(False)
        right_layout.addWidget(self.open_single_export_button)
        right_layout.addStretch()

        layout.addWidget(splitter)
        return group

    def _create_bulk_card(self) -> QGroupBox:
        group = QGroupBox("Hromadný export a import")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)

        left, right, splitter = self._create_split_panel()
        left_layout = left.layout()
        assert left_layout is not None
        right_layout = right.layout()
        assert right_layout is not None

        self.bulk_export_button = QPushButton("Exportovat všechny číselníky")
        self.bulk_export_button.clicked.connect(self._export_all)
        left_layout.addWidget(self.bulk_export_button)

        self.last_bulk_export_label = QLabel()
        self.last_bulk_export_label.setWordWrap(True)
        left_layout.addWidget(self.last_bulk_export_label)

        self.open_bulk_export_button = QPushButton("Otevřít umístění")
        self.open_bulk_export_button.clicked.connect(self._open_bulk_export_location)
        left_layout.addWidget(self.open_bulk_export_button)

        self.bulk_import_button = QPushButton("Importovat všechny číselníky")
        self.bulk_import_button.clicked.connect(self._import_all)
        left_layout.addWidget(self.bulk_import_button)

        self.last_bulk_import_label = QLabel()
        self.last_bulk_import_label.setWordWrap(True)
        left_layout.addWidget(self.last_bulk_import_label)
        left_layout.addStretch()

        self.bulk_manifest_placeholder = QLabel(
            "Přehled obsahu hromadného exportu bude dostupný po prvním exportu."
        )
        self.bulk_manifest_placeholder.setWordWrap(True)
        self.bulk_manifest_table = ManifestTableWidget()
        right_layout.addWidget(
            self._wrap_manifest_panel(
                "Přehled obsahu hromadného exportu",
                self.bulk_manifest_table,
                self.bulk_manifest_placeholder,
            )
        )
        right_layout.addStretch()

        layout.addWidget(splitter)
        return group

    def refresh(self) -> None:
        self._reload_catalog_tree()
        self._update_bulk_sections()
        if self._selected_group is not None:
            self._show_group_details(self._selected_group)
        elif self._selected_entry is not None:
            self._show_entry_details(self._selected_entry)

    def _reload_catalog_tree(self) -> None:
        current_id = ""
        if self._selected_group is not None:
            current_id = f"{GROUP_PREFIX}{self._selected_group}"
        elif self._selected_entry is not None:
            current_id = self._selected_entry.codebook_id

        self.catalog_tree.clear()
        grouped = codebook_catalog_service.grouped_codebooks()

        first_item: QTreeWidgetItem | None = None
        restore_item: QTreeWidgetItem | None = None

        for module in MODULE_ORDER:
            entries = grouped.get(module) or []
            if not entries:
                continue

            group_item = QTreeWidgetItem([module])
            group_item.setData(0, Qt.ItemDataRole.UserRole, f"{GROUP_PREFIX}{module}")
            self.catalog_tree.addTopLevelItem(group_item)

            if first_item is None:
                first_item = group_item
            if current_id == f"{GROUP_PREFIX}{module}":
                restore_item = group_item

            for entry in sorted(entries, key=lambda item: item.name.lower()):
                child = QTreeWidgetItem([entry.name])
                child.setData(0, Qt.ItemDataRole.UserRole, entry.codebook_id)
                group_item.addChild(child)
                if first_item is None:
                    first_item = child
                if entry.codebook_id == current_id:
                    restore_item = child

            group_item.setExpanded(True)

        if restore_item is not None:
            self.catalog_tree.setCurrentItem(restore_item)
        elif first_item is not None:
            self.catalog_tree.setCurrentItem(first_item)

    def _on_catalog_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            self._selected_entry = None
            self._selected_group = None
            self._clear_entry_details()
            return

        item_id = str(current.data(0, Qt.ItemDataRole.UserRole) or "")
        if item_id.startswith(GROUP_PREFIX):
            self._selected_group = item_id[len(GROUP_PREFIX) :]
            self._selected_entry = None
            self._show_group_details(self._selected_group)
            return

        if not item_id:
            self._selected_entry = None
            self._selected_group = None
            self._clear_entry_details()
            return

        entry = codebook_catalog_service.get_by_id(item_id)
        self._selected_entry = entry
        self._selected_group = None
        if entry is None:
            self._clear_entry_details()
            return
        self._show_entry_details(entry)

    def _clear_entry_details(self) -> None:
        self.detail_title.setText("Vyberte skupinu nebo číselník")
        self.detail_name.setText("")
        self.detail_module.setText("")
        self.detail_count.setText("")
        self.detail_storage.setText("")
        self.detail_path.setText("")
        self.detail_modified.setText("")
        self.detail_list.setText("")
        self.export_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.export_group_button.setEnabled(False)
        self.import_group_button.setEnabled(False)
        self.open_single_export_button.setEnabled(False)

    def _show_group_details(self, module: str) -> None:
        entries = codebook_catalog_service.list_group_entries(module)
        exportable = [entry for entry in entries if entry.exportable]
        importable = [entry for entry in entries if entry.importable]
        total_items = sum(entry.item_count for entry in entries)

        self.detail_title.setText(module)
        self.detail_name.setText(f"Skupina: {module}")
        self.detail_module.setText(f"Počet číselníků ve skupině: {len(entries)}")
        self.detail_count.setText(f"Celkový počet položek: {total_items}")
        self.detail_storage.setText("")
        self.detail_path.setText("")
        self.detail_modified.setText("")
        self.detail_list.setText(
            "Zahrnuté číselníky:\n" + "\n".join(f"• {entry.name}" for entry in entries)
        )

        self.export_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.export_group_button.setEnabled(bool(exportable))
        all_importable = bool(entries) and len(importable) == len(entries)
        self.import_group_button.setEnabled(all_importable and bool(importable))

    def _show_entry_details(self, entry: CodebookEntry) -> None:
        self.detail_title.setText(entry.name)
        self.detail_name.setText(f"Název: {entry.name}")
        self.detail_module.setText(f"Modul: {entry.module}")
        self.detail_count.setText(f"Počet položek: {entry.item_count}")
        self.detail_storage.setText(f"Umístění: {entry.storage_type}")
        self.detail_path.setText(f"Cesta: {entry.path}")
        modified = (
            data_management_settings_service.format_timestamp(entry.last_modified)
            if entry.last_modified
            else "—"
        )
        self.detail_modified.setText(f"Datum poslední změny: {modified}")
        self.detail_list.setText("")
        self.export_button.setEnabled(entry.exportable)
        self.import_button.setEnabled(entry.importable)
        self.export_group_button.setEnabled(False)
        self.import_group_button.setEnabled(False)

    def _export_group(self) -> None:
        if self._selected_group is None:
            return

        module = self._selected_group
        default_path = codebook_export_service.default_group_export_path(module)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export skupiny – {module}",
            str(default_path),
            "ZIP archivy (*.zip)",
        )
        if not file_path:
            return

        try:
            result = codebook_export_service.export_group_codebooks(module, file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export skupiny", str(exc))
            return

        self._last_single_export_path = str(result.path)
        self._populate_manifest_table(
            self.single_manifest_table,
            self.single_manifest_placeholder,
            codebook_manifest_service.rows_from_bulk_manifest(result.manifest),
        )
        self.open_single_export_button.setEnabled(True)
        QMessageBox.information(
            self,
            "Export skupiny",
            f"Skupina „{module}“ byla exportována.\n\nSoubor: {result.path.name}",
        )

    def _import_group(self) -> None:
        if self._selected_group is None:
            return

        module = self._selected_group
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import skupiny – {module}",
            str(storage_service.imports_dir),
            "ZIP archivy (*.zip)",
        )
        if not file_path:
            return

        confirm = QMessageBox.question(
            self,
            "Import skupiny",
            "Před importem bude vytvořena kompletní bezpečnostní záloha.\n\n"
            "Vestavěné a nepodporované číselníky budou přeskočeny.\n\n"
            "Pokračovat?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = codebook_transfer_service.import_group_with_verified_safety(module, file_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Import skupiny", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "Import skupiny", str(exc))
            return

        self._show_import_summary_dict(result["import_result"], title=f"Import skupiny – {module}")
        self.refresh()

    def _export_selected(self) -> None:
        if self._selected_entry is None:
            return

        entry = self._selected_entry
        default_path = codebook_export_service.default_single_export_path(entry)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export číselníku – {entry.name}",
            str(default_path),
            "JSON soubory (*.json)",
        )
        if not file_path:
            return

        try:
            result = codebook_export_service.export_codebook(entry, file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export číselníku", str(exc))
            return

        self._last_single_export_path = str(result.path)
        manifest = result.manifest
        self._populate_manifest_table(
            self.single_manifest_table,
            self.single_manifest_placeholder,
            codebook_manifest_service.rows_from_single_manifest(manifest),
        )
        self.open_single_export_button.setEnabled(True)
        QMessageBox.information(
            self,
            "Export číselníku",
            f"Číselník „{entry.name}“ byl exportován.\n\nSoubor: {result.path.name}",
        )

    def _import_selected(self) -> None:
        if self._selected_entry is None or not self._selected_entry.importable:
            return

        entry = self._selected_entry
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import číselníku – {entry.name}",
            str(storage_service.imports_dir),
            "JSON soubory (*.json)",
        )
        if not file_path:
            return

        summary = codebook_import_service.import_codebook(entry, file_path)
        self._show_import_summary(summary, title="Import číselníku")
        self.refresh()

    def _export_all(self) -> None:
        default_path = codebook_export_service.default_bulk_export_path()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export všech číselníků",
            str(default_path),
            "ZIP archivy (*.zip)",
        )
        if not file_path:
            return

        try:
            result = codebook_export_service.export_all_codebooks(file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Hromadný export", str(exc))
            return

        record = CodebooksExportRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            path=str(result.path),
            manifest=result.manifest,
            export_type="bulk",
        )
        data_management_settings_service.save_last_codebooks_export(record)
        self._update_bulk_sections()
        QMessageBox.information(
            self,
            "Hromadný export",
            f"Exportováno {result.item_count} číselníků.\n\nSoubor: {result.path.name}",
        )

    def _import_all(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import všech číselníků",
            str(storage_service.imports_dir),
            "ZIP archivy (*.zip)",
        )
        if not file_path:
            return

        confirm = QMessageBox.question(
            self,
            "Import všech číselníků",
            "Před importem bude vytvořena kompletní bezpečnostní záloha.\n\n"
            "Pokračovat?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = codebook_transfer_service.import_with_verified_safety(file_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Import číselníků", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "Import číselníků", str(exc))
            return

        data_management_settings_service.save_last_codebooks_pre_import_backup(
            BackupRecord(
                created_at=datetime.now().isoformat(timespec="seconds"),
                path=result["safety_backup_path"],
                manifest=result["safety_backup_manifest"],
                backup_type=BACKUP_TYPE_FULL,
            )
        )
        data_management_settings_service.save_last_codebooks_import(
            CodebooksImportRecord(
                created_at=result["imported_at"],
                source_path=result["source_path"],
                safety_backup_path=result["safety_backup_path"],
                import_result=result["import_result"],
            )
        )
        self._update_bulk_sections()
        self._show_import_summary_dict(result["import_result"], title="Import všech číselníků")
        self.refresh()

    def _update_bulk_sections(self) -> None:
        export_record = data_management_settings_service.get_last_codebooks_export()
        if export_record is None:
            self.last_bulk_export_label.setText("Poslední export: —")
            self.open_bulk_export_button.setEnabled(False)
            self._populate_manifest_table(
                self.bulk_manifest_table,
                self.bulk_manifest_placeholder,
                [],
            )
        else:
            self.last_bulk_export_label.setText(
                "Poslední export: "
                f"{data_management_settings_service.format_timestamp(export_record.created_at)}\n"
                f"Soubor: {Path(export_record.path).name}"
            )
            self.open_bulk_export_button.setEnabled(bool(export_record.path))
            self._populate_manifest_table(
                self.bulk_manifest_table,
                self.bulk_manifest_placeholder,
                codebook_manifest_service.rows_from_bulk_manifest(export_record.manifest),
            )

        import_record = data_management_settings_service.get_last_codebooks_import()
        if import_record is None:
            self.last_bulk_import_label.setText("Poslední import: —")
            return

        import_result = import_record.import_result or {}
        self.last_bulk_import_label.setText(
            "Poslední import: "
            f"{data_management_settings_service.format_timestamp(import_record.created_at)}\n"
            f"Aktualizováno: {import_result.get('updated_count', 0)}, "
            f"přeskočeno: {import_result.get('skipped_count', 0)}, "
            f"chyby: {import_result.get('error_count', 0)}"
        )

    def _open_single_export_location(self) -> None:
        if not self._last_single_export_path:
            return
        open_path_in_file_manager(
            self._last_single_export_path,
            parent=self,
            title="Umístění exportu číselníku",
        )

    def _open_bulk_export_location(self) -> None:
        record = data_management_settings_service.get_last_codebooks_export()
        if record is None or not record.path:
            return
        open_path_in_file_manager(record.path, parent=self, title="Umístění hromadného exportu")

    def _show_import_summary(self, summary, *, title: str) -> None:
        self._show_import_summary_dict(summary.to_dict(), title=title)

    @staticmethod
    def _show_import_summary_dict(import_result: dict, *, title: str) -> None:
        lines = [
            f"Aktualizováno: {import_result.get('updated_count', 0)}",
            f"Přeskočeno: {import_result.get('skipped_count', 0)}",
            f"Chyby: {import_result.get('error_count', 0)}",
        ]
        for item in import_result.get("updated") or []:
            lines.append(f"✔ {item}")
        for item in import_result.get("skipped") or []:
            lines.append(f"○ {item}")
        for item in import_result.get("errors") or []:
            lines.append(f"✖ {item}")
        QMessageBox.information(None, title, "\n".join(lines))
