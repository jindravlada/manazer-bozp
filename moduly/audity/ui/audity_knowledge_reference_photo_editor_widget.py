"""Editor referenčních fotografií oblasti ověření."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_reference_photo_dialog import (
    AudityKnowledgeReferencePhotoDialog,
)
from core.ui.photo_picker_dialog import PhotoPickerDialog

_FIELD_NAME = KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB[1]

_COL_ID = 0
_COL_NAZEV = 1
_COL_POPIS = 2
_COL_SOUBOR = 3
_COL_PORADI = 4
_COL_AKTIVNI = 5


class AudityKnowledgeReferencePhotoEditorWidget(QWidget):
    """Seznam referenčních fotografií s CRUD toolbar."""

    content_modified = Signal()
    content_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process_id = ""
        self._section_id = ""
        self._items: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._add_btn = QPushButton("Přidat")
        self._edit_btn = QPushButton("Upravit")
        self._deactivate_btn = QPushButton("Deaktivovat")
        self._restore_btn = QPushButton("Obnovit")

        self._add_btn.clicked.connect(self._add_item)
        self._edit_btn.clicked.connect(self._edit_selected_item)
        self._deactivate_btn.clicked.connect(self._deactivate_selected_item)
        self._restore_btn.clicked.connect(self._restore_selected_item)

        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._edit_btn)
        toolbar.addWidget(self._deactivate_btn)
        toolbar.addWidget(self._restore_btn)
        toolbar.addStretch()

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Název", "Popis", "Soubor", "Pořadí", "Aktivní"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._edit_selected_item)
        self._table.itemSelectionChanged.connect(self._update_buttons)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_COL_NAZEV, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_POPIS, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_SOUBOR, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnHidden(_COL_ID, True)
        self._table.setColumnWidth(_COL_PORADI, 70)
        self._table.setColumnWidth(_COL_AKTIVNI, 70)

        root.addLayout(toolbar)
        root.addWidget(self._table, stretch=1)

        self._update_buttons()

    def load_section(
        self,
        *,
        process_id: str,
        section_id: str,
        section: dict,
    ) -> None:
        self._process_id = process_id
        self._section_id = section_id
        self._reload_from_section(section)

    def clear_section(self) -> None:
        self._process_id = ""
        self._section_id = ""
        self._items = []
        self._table.setRowCount(0)
        self._update_buttons()

    def reload_items(self) -> None:
        if not self._process_id or not self._section_id:
            return
        section = audit_knowledge_service.get_criterion(
            self._process_id,
            self._section_id,
            ensure=False,
        )
        if section is None:
            self.clear_section()
            return
        self._reload_from_section(section)
        self.content_saved.emit()

    def _reload_from_section(self, section: dict) -> None:
        raw_items = section.get(_FIELD_NAME) or []
        self._items = audit_knowledge_service.normalize_reference_photos_for_editor(
            raw_items
        )
        self._items.sort(key=lambda item: (item.get("poradi", 0), item.get("id", "")))
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = [
                item.get("id", ""),
                item.get("nazev", ""),
                item.get("popis", ""),
                item.get("soubor", ""),
                str(item.get("poradi", "")),
                "Ano" if item.get("aktivni", True) else "Ne",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if not item.get("aktivni", True):
                    cell.setForeground(Qt.GlobalColor.gray)
                self._table.setItem(row, column, cell)
        self._update_buttons()

    def _selected_item(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _existing_ids(self) -> set[str]:
        return {
            str(item.get("id") or "").strip()
            for item in self._items
            if str(item.get("id") or "").strip()
        }

    def _show_errors(self, errors: list[str]) -> None:
        if errors:
            QMessageBox.warning(self, "Editor metodiky auditora", "\n".join(errors))

    def _add_item(self) -> None:
        if not self._process_id or not self._section_id:
            return

        paths = PhotoPickerDialog.get_photos(parent=self)
        if not paths:
            return

        self.content_modified.emit()
        existing_ids = self._existing_ids()
        next_poradi = 10
        if self._items:
            next_poradi = max(int(item.get("poradi") or 0) for item in self._items) + 10

        for path in paths:
            if not path.is_file():
                continue
            nazev = path.stem.strip() or "Fotografie"
            photo_id = audit_knowledge_service.generate_item_id(nazev, existing_ids)
            existing_ids.add(photo_id)
            payload = {
                "id": photo_id,
                "nazev": nazev,
                "popis": "",
                "soubor": str(path.resolve()),
                "poradi": next_poradi,
                "aktivni": True,
                "control_point_id": None,
            }
            next_poradi += 10
            errors = audit_knowledge_editor_service.save_section_list_item(
                self._process_id,
                self._section_id,
                _FIELD_NAME,
                payload,
            )
            if errors:
                self._show_errors(errors)
                break

        self.reload_items()

    def _edit_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or not self._process_id or not self._section_id:
            return

        dialog = AudityKnowledgeReferencePhotoDialog(
            existing_ids=self._existing_ids(),
            item=selected,
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeReferencePhotoDialog.DialogCode.Accepted:
            return

        self.content_modified.emit()
        errors = audit_knowledge_editor_service.save_section_list_item(
            self._process_id,
            self._section_id,
            _FIELD_NAME,
            dialog.item_payload(),
            item_id=dialog.editing_item_id,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _deactivate_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or not selected.get("aktivni", True):
            return
        self.content_modified.emit()
        errors = audit_knowledge_editor_service.set_section_list_item_active(
            self._process_id,
            self._section_id,
            _FIELD_NAME,
            str(selected.get("id") or ""),
            aktivni=False,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _restore_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or selected.get("aktivni", True):
            return
        self.content_modified.emit()
        errors = audit_knowledge_editor_service.set_section_list_item_active(
            self._process_id,
            self._section_id,
            _FIELD_NAME,
            str(selected.get("id") or ""),
            aktivni=True,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _update_buttons(self) -> None:
        has_section = bool(self._process_id and self._section_id)
        selected = self._selected_item()
        is_active = bool(selected.get("aktivni", True)) if selected else False

        self._add_btn.setEnabled(has_section)
        self._edit_btn.setEnabled(has_section and selected is not None)
        self._deactivate_btn.setEnabled(has_section and selected is not None and is_active)
        self._restore_btn.setEnabled(has_section and selected is not None and not is_active)
