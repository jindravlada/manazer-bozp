from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import REFERENCE_PHOTO_FILTER
from moduly.proverky.sluzby.proverky_knowledge_service import (
    EDITABLE_SECTION_LIST_FIELDS,
    EDITABLE_SECTION_PROCEDURE_FIELDS,
    EDITABLE_SECTION_REFERENCE_FIELDS,
    proverky_knowledge_service,
)
from moduly.proverky.sluzby.proverky_reference_photo_service import proverky_reference_photo_service
from moduly.proverky.ui.proverky_knowledge_list_item_dialog import ProverkyKnowledgeListItemDialog
from moduly.proverky.ui.proverky_knowledge_reference_photo_dialog import (
    ProverkyKnowledgeReferencePhotoDialog,
)
from moduly.proverky.ui.proverky_knowledge_procedure_step_dialog import (
    ProverkyKnowledgeProcedureStepDialog,
)

_LIST_MIN_HEIGHT = 140
_SECTION_SPACING = 20


class _CollapsibleSection(QWidget):
    def __init__(self, title: str, *, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self._count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._header = QPushButton()
        self._header.setFlat(True)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 4px 0; }"
        )
        self._header.clicked.connect(self._toggle)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 0, 0, 0)
        self._content_layout.setSpacing(8)

        layout.addWidget(self._header)
        layout.addWidget(self._content)

        self._content.setVisible(expanded)
        self._refresh_header()

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def set_count(self, count: int) -> None:
        self._count = max(0, count)
        self._refresh_header()

    def _refresh_header(self) -> None:
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f"{arrow} {self._title} ({self._count})")

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._refresh_header()


class ProverkyKnowledgeSectionEditDialog(QDialog):
    """Editor znalostní karty sekce prověrky."""

    def __init__(
        self,
        parent=None,
        *,
        area_id: str,
        section_id: str,
    ):
        super().__init__(parent)

        self._area_id = area_id
        self._section_id = section_id
        self._lists_by_field: dict[str, QListWidget] = {}
        self._procedure_lists: set[QListWidget] = set()
        self._reference_lists: set[QListWidget] = set()
        self._sections_by_list: dict[QListWidget, _CollapsibleSection] = {}

        section = proverky_knowledge_service.get_section(area_id, section_id)
        if section is None:
            raise ValueError(f"Sekce {section_id} v oblasti {area_id} neexistuje.")

        self._section = section
        area = proverky_knowledge_service.get_area_by_id(area_id)
        area_label = area.nazev if area else area_id
        section_label = str(section.get("nazev") or section_id)

        self.setWindowTitle(f"Editor znalostí – {area_label} → {section_label}")
        self.resize(760, 820)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(_SECTION_SPACING)
        scroll.setWidget(scroll_content)

        header_form = QFormLayout()
        header_form.setSpacing(10)

        self._id_label = QLabel(section_id)
        self._nazev_edit = QLineEdit()
        self._nazev_edit.setText(str(section.get("nazev") or ""))

        self._popis_edit = QTextEdit()
        self._popis_edit.setPlainText(str(section.get("popis") or ""))
        self._popis_edit.setMinimumHeight(100)

        self._aktivni_check = QCheckBox("Sekce je aktivní")
        self._aktivni_check.setChecked(bool(section.get("aktivni", True)))

        header_form.addRow("Identifikátor:", self._id_label)
        header_form.addRow("Název sekce:", self._nazev_edit)
        header_form.addRow("Popis:", self._popis_edit)
        header_form.addRow("", self._aktivni_check)
        scroll_layout.addLayout(header_form)

        for title, field_name in EDITABLE_SECTION_PROCEDURE_FIELDS:
            list_widget = self._create_list_section(scroll_layout, title, field_name)
            self._procedure_lists.add(list_widget)
            self._populate_procedure_list(list_widget, section.get(field_name) or [])

        for title, field_name in EDITABLE_SECTION_REFERENCE_FIELDS:
            list_widget = self._create_reference_section(scroll_layout, title, field_name)
            self._populate_reference_list(list_widget, section.get(field_name) or [])

        for title, field_name in EDITABLE_SECTION_LIST_FIELDS:
            list_widget = self._create_list_section(scroll_layout, title, field_name)
            self._populate_list(list_widget, section.get(field_name) or [])

        scroll_layout.addStretch()
        root_layout.addWidget(scroll, stretch=1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

    def exec(self) -> int:
        self.showMaximized()
        return super().exec()

    def _create_list_section(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        field_name: str,
    ) -> QListWidget:
        section = _CollapsibleSection(title, expanded=True)
        list_widget = QListWidget()
        list_widget.setMinimumHeight(_LIST_MIN_HEIGHT)
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._list_toolbar(list_widget))
        self._lists_by_field[field_name] = list_widget
        self._sections_by_list[list_widget] = section
        parent_layout.addWidget(section)
        return list_widget

    def _create_reference_section(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        field_name: str,
    ) -> QListWidget:
        section = _CollapsibleSection(title, expanded=True)
        list_widget = QListWidget()
        list_widget.setMinimumHeight(_LIST_MIN_HEIGHT)
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._reference_toolbar(list_widget))
        self._lists_by_field[field_name] = list_widget
        self._reference_lists.add(list_widget)
        self._sections_by_list[list_widget] = section
        parent_layout.addWidget(section)
        return list_widget

    def _reference_toolbar(self, list_widget: QListWidget) -> QHBoxLayout:
        toolbar = QHBoxLayout()

        add_btn = QPushButton("Přidat fotografii")
        edit_btn = QPushButton("Upravit")
        remove_btn = QPushButton("Odebrat")
        up_btn = QPushButton("Posun nahoru")
        down_btn = QPushButton("Posun dolů")
        toggle_btn = QPushButton("Aktivní / neaktivní")

        add_btn.clicked.connect(lambda: self._add_reference_photo(list_widget))
        edit_btn.clicked.connect(lambda: self._edit_reference_photo(list_widget))
        remove_btn.clicked.connect(lambda: self._remove_reference_photo(list_widget))
        up_btn.clicked.connect(lambda: self._move_item(list_widget, -1))
        down_btn.clicked.connect(lambda: self._move_item(list_widget, 1))
        toggle_btn.clicked.connect(lambda: self._toggle_active(list_widget))

        for button in (add_btn, edit_btn, remove_btn, up_btn, down_btn, toggle_btn):
            toolbar.addWidget(button)
        toolbar.addStretch()
        return toolbar

    def _list_toolbar(self, list_widget: QListWidget) -> QHBoxLayout:
        toolbar = QHBoxLayout()

        add_btn = QPushButton("Přidat")
        edit_btn = QPushButton("Upravit")
        remove_btn = QPushButton("Odebrat")
        up_btn = QPushButton("Posun nahoru")
        down_btn = QPushButton("Posun dolů")
        toggle_btn = QPushButton("Aktivní / neaktivní")

        add_btn.clicked.connect(lambda: self._add_item(list_widget))
        edit_btn.clicked.connect(lambda: self._edit_item(list_widget))
        remove_btn.clicked.connect(lambda: self._remove_item(list_widget))
        up_btn.clicked.connect(lambda: self._move_item(list_widget, -1))
        down_btn.clicked.connect(lambda: self._move_item(list_widget, 1))
        toggle_btn.clicked.connect(lambda: self._toggle_active(list_widget))

        for button in (add_btn, edit_btn, remove_btn, up_btn, down_btn, toggle_btn):
            toolbar.addWidget(button)
        toolbar.addStretch()
        return toolbar

    def _populate_procedure_list(self, list_widget: QListWidget, items: list) -> None:
        list_widget.clear()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            self._add_procedure_row(list_widget, deepcopy(raw))
        self._refresh_section_count(list_widget)

    @staticmethod
    def _format_procedure_label(item: dict) -> str:
        prefix = "[neaktivní] " if not item.get("aktivni", True) else ""
        text = str(item.get("text") or "—")
        return f"{prefix}{text}"

    def _add_procedure_row(self, list_widget: QListWidget, item: dict) -> None:
        row = QListWidgetItem(self._format_procedure_label(item))
        row.setData(Qt.ItemDataRole.UserRole, item)
        list_widget.addItem(row)

    def _populate_reference_list(self, list_widget: QListWidget, items: list) -> None:
        list_widget.clear()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            self._add_reference_row(list_widget, deepcopy(raw))
        self._refresh_section_count(list_widget)

    @staticmethod
    def _format_reference_label(item: dict) -> str:
        prefix = "[neaktivní] " if not item.get("aktivni", True) else ""
        nazev = str(item.get("nazev") or "—")
        return f"{prefix}{nazev}"

    def _add_reference_row(self, list_widget: QListWidget, item: dict) -> None:
        row = QListWidgetItem(self._format_reference_label(item))
        row.setData(Qt.ItemDataRole.UserRole, item)
        list_widget.addItem(row)

    def _populate_list(self, list_widget: QListWidget, items: list) -> None:
        list_widget.clear()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            self._add_list_row(list_widget, deepcopy(raw))
        self._refresh_section_count(list_widget)

    @staticmethod
    def _format_item_label(item: dict) -> str:
        prefix = "[neaktivní] " if not item.get("aktivni", True) else ""
        nazev = str(item.get("nazev") or "—")
        return f"{prefix}{nazev}"

    def _add_list_row(self, list_widget: QListWidget, item: dict) -> None:
        row = QListWidgetItem(self._format_item_label(item))
        row.setData(Qt.ItemDataRole.UserRole, item)
        list_widget.addItem(row)

    def _refresh_section_count(self, list_widget: QListWidget) -> None:
        section = self._sections_by_list.get(list_widget)
        if section is not None:
            section.set_count(list_widget.count())

    def _existing_ids(self, list_widget: QListWidget, *, exclude_row: int | None = None) -> set[str]:
        ids: set[str] = set()
        for row in range(list_widget.count()):
            if row == exclude_row:
                continue
            item = list_widget.item(row)
            data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if isinstance(data, dict):
                item_id = str(data.get("id") or "").strip()
                if item_id:
                    ids.add(item_id)
        return ids

    def _selected_row(self, list_widget: QListWidget) -> int:
        return list_widget.currentRow()

    def _add_reference_photo(self, list_widget: QListWidget) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte referenční fotografii",
            "",
            REFERENCE_PHOTO_FILTER,
        )
        if not file_path:
            return

        default_name = Path(file_path).stem.strip() or "Fotografie"
        photo_id = proverky_knowledge_service.generate_item_id(
            default_name,
            self._existing_ids(list_widget),
        )

        try:
            relative_path = proverky_reference_photo_service.save_optimized(
                Path(file_path),
                area_id=self._area_id,
                section_id=self._section_id,
                photo_id=photo_id,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Fotografii se nepodařilo uložit.\n\n{exc}",
            )
            return

        item = {
            "id": photo_id,
            "nazev": default_name,
            "popis": "",
            "soubor": relative_path,
            "control_point_id": None,
            "aktivni": True,
        }
        self._add_reference_row(list_widget, item)
        list_widget.setCurrentRow(list_widget.count() - 1)
        self._refresh_section_count(list_widget)

    def _edit_reference_photo(self, list_widget: QListWidget) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            QMessageBox.information(self, self.windowTitle(), "Vyberte fotografii k úpravě.")
            return

        current = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
        if not isinstance(current, dict):
            return

        dialog = ProverkyKnowledgeReferencePhotoDialog(
            self,
            title="Upravit referenční fotografii",
            item=current,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        if data is None:
            return

        updated = deepcopy(current)
        updated.update(data)
        list_widget.item(row).setText(self._format_reference_label(updated))
        list_widget.item(row).setData(Qt.ItemDataRole.UserRole, updated)

    def _remove_reference_photo(self, list_widget: QListWidget) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            QMessageBox.information(self, self.windowTitle(), "Vyberte fotografii k odebrání.")
            return

        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            "Odebrat vybranou referenční fotografii?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        current = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
        if isinstance(current, dict):
            proverky_reference_photo_service.delete_photo(str(current.get("soubor") or ""))

        list_widget.takeItem(row)
        self._refresh_section_count(list_widget)

    def _add_item(self, list_widget: QListWidget) -> None:
        if list_widget in self._procedure_lists:
            dialog = ProverkyKnowledgeProcedureStepDialog(
                self,
                title="Přidat krok postupu",
                existing_ids=self._existing_ids(list_widget),
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            data = dialog.get_data()
            if data is None:
                return

            if not data["id"]:
                data["id"] = proverky_knowledge_service.generate_item_id(
                    data["text"],
                    self._existing_ids(list_widget),
                )

            self._add_procedure_row(list_widget, data)
            list_widget.setCurrentRow(list_widget.count() - 1)
            self._refresh_section_count(list_widget)
            return

        dialog = ProverkyKnowledgeListItemDialog(
            self,
            title="Přidat položku",
            existing_ids=self._existing_ids(list_widget),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        if data is None:
            return

        if not data["id"]:
            data["id"] = proverky_knowledge_service.generate_item_id(
                data["nazev"],
                self._existing_ids(list_widget),
            )

        self._add_list_row(list_widget, data)
        list_widget.setCurrentRow(list_widget.count() - 1)
        self._refresh_section_count(list_widget)

    def _edit_item(self, list_widget: QListWidget) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            QMessageBox.information(self, self.windowTitle(), "Vyberte položku k úpravě.")
            return

        current = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
        if not isinstance(current, dict):
            return

        if list_widget in self._procedure_lists:
            dialog = ProverkyKnowledgeProcedureStepDialog(
                self,
                title="Upravit krok postupu",
                item=current,
                existing_ids=self._existing_ids(list_widget, exclude_row=row),
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            data = dialog.get_data()
            if data is None:
                return

            if not data["id"]:
                data["id"] = proverky_knowledge_service.generate_item_id(
                    data["text"],
                    self._existing_ids(list_widget, exclude_row=row),
                )

            list_widget.item(row).setText(self._format_procedure_label(data))
            list_widget.item(row).setData(Qt.ItemDataRole.UserRole, data)
            return

        dialog = ProverkyKnowledgeListItemDialog(
            self,
            title="Upravit položku",
            item=current,
            existing_ids=self._existing_ids(list_widget, exclude_row=row),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()
        if data is None:
            return

        if not data["id"]:
            data["id"] = proverky_knowledge_service.generate_item_id(
                data["nazev"],
                self._existing_ids(list_widget, exclude_row=row),
            )

        list_widget.item(row).setText(self._format_item_label(data))
        list_widget.item(row).setData(Qt.ItemDataRole.UserRole, data)

    def _remove_item(self, list_widget: QListWidget) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            QMessageBox.information(self, self.windowTitle(), "Vyberte položku k odebrání.")
            return

        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            "Odebrat vybranou položku?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        list_widget.takeItem(row)
        self._refresh_section_count(list_widget)

    def _move_item(self, list_widget: QListWidget, direction: int) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            return

        target = row + direction
        if target < 0 or target >= list_widget.count():
            return

        item = list_widget.takeItem(row)
        list_widget.insertItem(target, item)
        list_widget.setCurrentRow(target)

    def _toggle_active(self, list_widget: QListWidget) -> None:
        row = self._selected_row(list_widget)
        if row < 0:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "Vyberte položku pro přepnutí stavu aktivní / neaktivní.",
            )
            return

        item = list_widget.item(row)
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        updated = deepcopy(data)
        updated["aktivni"] = not bool(updated.get("aktivni", True))
        if list_widget in self._procedure_lists:
            item.setText(self._format_procedure_label(updated))
        elif list_widget in self._reference_lists:
            item.setText(self._format_reference_label(updated))
        else:
            item.setText(self._format_item_label(updated))
        item.setData(Qt.ItemDataRole.UserRole, updated)

    def _collect_reference_photos(self, list_widget: QListWidget) -> list[dict]:
        items: list[dict] = []
        for row in range(list_widget.count()):
            data = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                items.append(deepcopy(data))
        return proverky_knowledge_service.normalize_reference_photos(items)

    def _collect_procedure_steps(self, list_widget: QListWidget) -> list[dict]:
        items: list[dict] = []
        for row in range(list_widget.count()):
            data = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                items.append(deepcopy(data))
        return proverky_knowledge_service.normalize_procedure_steps(items)

    def _collect_list_items(self, list_widget: QListWidget) -> list[dict]:
        items: list[dict] = []
        for row in range(list_widget.count()):
            data = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                items.append(deepcopy(data))
        return proverky_knowledge_service.normalize_list_items(items)

    def _build_section_payload(self) -> dict | None:
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            return None

        payload = deepcopy(self._section)
        payload["nazev"] = nazev
        payload["popis"] = self._popis_edit.toPlainText().strip()
        payload["aktivni"] = self._aktivni_check.isChecked()

        for _title, field_name in EDITABLE_SECTION_PROCEDURE_FIELDS:
            list_widget = self._lists_by_field[field_name]
            payload[field_name] = self._collect_procedure_steps(list_widget)

        for _title, field_name in EDITABLE_SECTION_REFERENCE_FIELDS:
            list_widget = self._lists_by_field[field_name]
            payload[field_name] = self._collect_reference_photos(list_widget)

        for _title, field_name in EDITABLE_SECTION_LIST_FIELDS:
            list_widget = self._lists_by_field[field_name]
            payload[field_name] = self._collect_list_items(list_widget)

        return payload

    def _accept(self) -> None:
        payload = self._build_section_payload()
        if payload is None:
            QMessageBox.warning(self, self.windowTitle(), "Název sekce je povinný.")
            return

        saved = proverky_knowledge_service.save_section(
            self._area_id,
            self._section_id,
            payload,
        )
        if not saved:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Změny se nepodařilo uložit.",
            )
            return

        self.accept()
