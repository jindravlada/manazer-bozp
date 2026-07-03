from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from core.widgets.knowledge_editor_actions import (
    clear_save_status,
    confirm_close_with_unsaved_changes,
    create_knowledge_editor_footer,
    show_save_status,
    show_unsaved_status,
)
from moduly.proverky.constants import CONTROL_POINT_SEVERITY_OPTIONS, REFERENCE_PHOTO_FILTER
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
_CONTROL_POINTS_LIST_MIN_HEIGHT = 220
_SECTION_SPACING = 20


class _ControlPointListRow(QWidget):
    """Řádek kontrolního bodu v editoru se jmenovkou a editovatelnou závažností."""

    def __init__(self, item: dict, *, on_severity_changed, parent=None):
        super().__init__(parent)
        self._on_severity_changed = on_severity_changed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        self._label = QLabel()
        self._label.setWordWrap(True)

        self._severity_combo = QComboBox()
        self._severity_combo.setFixedWidth(128)
        for value, label in CONTROL_POINT_SEVERITY_OPTIONS:
            self._severity_combo.addItem(label, value)

        self._severity_combo.currentIndexChanged.connect(self._emit_severity_changed)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._severity_combo, 0, Qt.AlignmentFlag.AlignTop)

        self.set_item(item, block_signals=True)

    def set_item(self, item: dict, *, block_signals: bool = False) -> None:
        if block_signals:
            self._severity_combo.blockSignals(True)

        self._label.setText(_format_control_point_label(item))
        severity = proverky_knowledge_service.normalize_control_point_severity(item.get("zavaznost"))
        index = self._severity_combo.findData(severity)
        if index >= 0:
            self._severity_combo.setCurrentIndex(index)

        if block_signals:
            self._severity_combo.blockSignals(False)

    def current_severity(self) -> str:
        return proverky_knowledge_service.normalize_control_point_severity(
            self._severity_combo.currentData()
        )

    def _emit_severity_changed(self) -> None:
        self._on_severity_changed(self.current_severity())


def _format_control_point_label(item: dict) -> str:
    prefix = "[neaktivní] " if not item.get("aktivni", True) else ""
    nazev = str(item.get("nazev") or "—")
    return f"{prefix}{nazev}"


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
        self._field_by_list: dict[QListWidget, str] = {}
        self._procedure_lists: set[QListWidget] = set()
        self._reference_lists: set[QListWidget] = set()
        self._sections_by_list: dict[QListWidget, _CollapsibleSection] = {}

        section = proverky_knowledge_service.get_section(area_id, section_id)
        if section is None:
            raise ValueError(f"Sekce {section_id} v oblasti {area_id} neexistuje.")

        self._section = section
        self._modified = False
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

        footer, self._apply_btn, self._save_close_btn, self._close_btn, self._status_label = (
            create_knowledge_editor_footer(
                on_apply=self._apply_changes,
                on_save_close=self._save_and_close,
                on_close=self._request_close,
            )
        )
        root_layout.addLayout(footer)

        self._nazev_edit.textChanged.connect(lambda *_args: self._mark_modified())
        self._popis_edit.textChanged.connect(lambda *_args: self._mark_modified())
        self._aktivni_check.toggled.connect(lambda *_args: self._mark_modified())

    def _mark_modified(self) -> None:
        self._modified = True
        show_unsaved_status(self._status_label)

    def _mark_saved(self) -> None:
        self._modified = False

    def _apply_changes(self) -> None:
        if self._persist_section_changes():
            self._mark_saved()
            show_save_status(self._status_label)
        else:
            self._show_persist_error()

    def _save_and_close(self) -> None:
        if self._persist_section_changes():
            self._mark_saved()
            self.accept()
        else:
            self._show_persist_error()

    def _request_close(self) -> None:
        if self._confirm_close():
            super().reject()

    def _confirm_close(self) -> bool:
        if not self._modified:
            return True

        decision = confirm_close_with_unsaved_changes(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._persist_section_changes():
                return False
            self._mark_saved()
        else:
            self._mark_saved()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_close():
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._confirm_close():
            super().reject()

    def _create_list_section(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        field_name: str,
    ) -> QListWidget:
        section = _CollapsibleSection(title, expanded=True)
        list_widget = QListWidget()
        min_height = (
            _CONTROL_POINTS_LIST_MIN_HEIGHT
            if field_name == "kontrolni_body"
            else _LIST_MIN_HEIGHT
        )
        list_widget.setMinimumHeight(min_height)
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._list_toolbar(list_widget))
        self._lists_by_field[field_name] = list_widget
        self._field_by_list[list_widget] = field_name
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
            if self._field_by_list.get(list_widget) == "kontrolni_body":
                self._add_control_point_row(list_widget, deepcopy(raw))
            else:
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

    def _add_control_point_row(self, list_widget: QListWidget, item: dict) -> None:
        normalized = deepcopy(item)
        normalized["zavaznost"] = proverky_knowledge_service.normalize_control_point_severity(
            normalized.get("zavaznost")
        )

        row = QListWidgetItem()
        row.setData(Qt.ItemDataRole.UserRole, normalized)
        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

        row_widget = _ControlPointListRow(
            normalized,
            on_severity_changed=lambda severity, r=row, lw=list_widget: self._on_control_point_severity_changed(
                lw,
                r,
                severity,
            ),
        )
        row.setSizeHint(row_widget.sizeHint())
        list_widget.addItem(row)
        list_widget.setItemWidget(row, row_widget)

    def _on_control_point_severity_changed(
        self,
        list_widget: QListWidget,
        row_item: QListWidgetItem,
        severity: str,
    ) -> None:
        data = row_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        updated = deepcopy(data)
        updated["zavaznost"] = proverky_knowledge_service.normalize_control_point_severity(severity)
        row_item.setData(Qt.ItemDataRole.UserRole, updated)
        if not self._persist_section_changes():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Závažnost se nepodařilo uložit.",
            )
            self._mark_modified()
            return
        self._mark_saved()

    def _refresh_control_point_row(self, list_widget: QListWidget, row: int) -> None:
        row_item = list_widget.item(row)
        if row_item is None:
            return

        data = row_item.data(Qt.ItemDataRole.UserRole)
        row_widget = list_widget.itemWidget(row_item)
        if isinstance(data, dict) and isinstance(row_widget, _ControlPointListRow):
            row_widget.set_item(data, block_signals=True)

    def _persist_section_changes(self) -> bool:
        payload = self._build_section_payload()
        if payload is None:
            return False

        saved = proverky_knowledge_service.save_section(
            self._area_id,
            self._section_id,
            payload,
        )
        if saved:
            self._section = payload
        return saved

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
        self._mark_modified()

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
        self._mark_modified()

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
        self._mark_modified()

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
            self._mark_modified()
            return

        dialog = ProverkyKnowledgeListItemDialog(
            self,
            title="Přidat položku",
            existing_ids=self._existing_ids(list_widget),
            include_zavaznost=self._field_by_list.get(list_widget) == "kontrolni_body",
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

        if self._field_by_list.get(list_widget) == "kontrolni_body":
            self._add_control_point_row(list_widget, data)
        else:
            self._add_list_row(list_widget, data)
        list_widget.setCurrentRow(list_widget.count() - 1)
        self._refresh_section_count(list_widget)
        self._mark_modified()

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
            self._mark_modified()
            return

        dialog = ProverkyKnowledgeListItemDialog(
            self,
            title="Upravit položku",
            item=current,
            existing_ids=self._existing_ids(list_widget, exclude_row=row),
            include_zavaznost=self._field_by_list.get(list_widget) == "kontrolni_body",
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

        list_widget.item(row).setData(Qt.ItemDataRole.UserRole, data)
        if self._field_by_list.get(list_widget) == "kontrolni_body":
            self._refresh_control_point_row(list_widget, row)
        else:
            list_widget.item(row).setText(self._format_item_label(data))
        self._mark_modified()

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
        self._mark_modified()

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
        self._mark_modified()

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
        item.setData(Qt.ItemDataRole.UserRole, updated)
        if list_widget in self._procedure_lists:
            item.setText(self._format_procedure_label(updated))
        elif list_widget in self._reference_lists:
            item.setText(self._format_reference_label(updated))
        elif self._field_by_list.get(list_widget) == "kontrolni_body":
            self._refresh_control_point_row(list_widget, row)
        else:
            item.setText(self._format_item_label(updated))
        self._mark_modified()

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

    def _collect_list_items(self, list_widget: QListWidget, field_name: str) -> list[dict]:
        items: list[dict] = []
        for row in range(list_widget.count()):
            data = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                items.append(deepcopy(data))
        if field_name == "kontrolni_body":
            return proverky_knowledge_service.normalize_kontrolni_body(items)
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
            payload[field_name] = self._collect_list_items(list_widget, field_name)

        return payload

    def _show_persist_error(self) -> None:
        clear_save_status(self._status_label)
        payload = self._build_section_payload()
        if payload is None:
            QMessageBox.warning(self, self.windowTitle(), "Název sekce je povinný.")
        else:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Změny se nepodařilo uložit.",
            )
