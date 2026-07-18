"""Správa číselníku kategorií zdrojů rizik – odložené ukládání."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_close_push_button
from core.widgets.filter_bar import FilterBar
from core.widgets.info_tooltip import set_widget_tooltip
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    HazardSourceCategoryError,
    hazard_source_category_service,
    normalize_category_name,
)
from moduly.rizeni_rizik.ui.hazard_source_category_dialog import HazardSourceCategoryDialog

DIALOG_TITLE = "Kategorie zdrojů rizik"
UNSAVED_PROMPT = "Máte neuložené změny. Co chcete udělat?"
UNSAVED_SAVE = "Uložit"
UNSAVED_DISCARD = "Zahodit změny"
UNSAVED_CANCEL_CLOSE = "Zrušit zavření"

COL_NAME = 0
COL_DESCRIPTION = 1
COL_ACTIVE = 2


@dataclass
class CategoryDraft:
    key: int
    code: str | None
    name: str
    description: str
    sort_order: int
    active: bool
    is_new: bool = False


class HazardSourceCategoriesManagementDialog(QDialog):
    """Správa číselníku kategorií zdrojů rizik s odloženým uložením."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.resize(820, 520)

        self._working_items: list[CategoryDraft] = []
        self._dirty = False
        self._closing = False
        self._next_temp_key = -1

        layout = QVBoxLayout(self)
        info = QLabel(
            "Číselník kategorií slouží k třídění zdrojů rizik. "
            "Deaktivace kategorie neskrývá existující zdroje ani jejich vazby.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_category)
        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_category)
        self.activate_button = QPushButton("Aktivovat")
        self.activate_button.clicked.connect(self.activate_selected_category)
        self.deactivate_button = QPushButton("Deaktivovat")
        self.deactivate_button.clicked.connect(self.deactivate_selected_category)
        self.filter = QComboBox()
        self.filter.addItems(["Aktivní", "Všechny"])
        self.filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.activate_button)
        toolbar.addWidget(self.deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.filter)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Název", "Popis", "Aktivní"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.doubleClicked.connect(self.edit_selected_category)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        self.table.setColumnWidth(COL_NAME, 260)
        self.table.setColumnWidth(COL_ACTIVE, 80)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ACTIVE, QHeaderView.ResizeMode.Fixed)

        self.text_filter = FilterBar(self.table)
        self.text_filter.search_edit.textChanged.connect(self._update_counts)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)
        self.close_button = QPushButton()
        configure_close_push_button(self.close_button)
        self.close_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.close_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Uložit")
        self.save_button.setIcon(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
        )
        self.save_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.save_button.clicked.connect(self._save_all)
        footer.addWidget(self.close_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

        self._load_working_copy()
        self.refresh()
        self._update_save_enabled()

    def is_dirty(self) -> bool:
        return self._dirty

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_save_enabled()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_save_enabled()

    def _update_save_enabled(self) -> None:
        self.save_button.setEnabled(self.is_dirty())

    def _load_working_copy(self) -> None:
        categories = hazard_source_category_service.get_all(include_inactive=True)
        self._working_items = [
            CategoryDraft(
                key=category.id,
                code=category.code,
                name=category.name,
                description=category.description or "",
                sort_order=category.sort_order,
                active=bool(category.active),
                is_new=False,
            )
            for category in categories
        ]
        self._mark_clean()

    def _sorted_working_items(self) -> list[CategoryDraft]:
        return sorted(
            self._working_items,
            key=lambda item: (item.sort_order, item.name.casefold(), item.key),
        )

    def refresh(self) -> None:
        include_inactive = self.filter.currentIndex() == 1
        rows = [
            item
            for item in self._sorted_working_items()
            if include_inactive or item.active
        ]
        self.table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            name_item = QTableWidgetItem(item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, item.key)
            set_widget_tooltip(name_item, item.name)
            description_item = QTableWidgetItem(item.description or "")
            if item.description:
                set_widget_tooltip(description_item, item.description)
            active_item = QTableWidgetItem("Ano" if item.active else "Ne")
            self.table.setItem(row_index, COL_NAME, name_item)
            self.table.setItem(row_index, COL_DESCRIPTION, description_item)
            self.table.setItem(row_index, COL_ACTIVE, active_item)
        self._update_counts()
        self._update_action_buttons()

    def _update_counts(self) -> None:
        self.text_filter.apply_filter()
        total = len(self._working_items)
        visible = sum(
            1
            for row in range(self.table.rowCount())
            if not self.table.isRowHidden(row)
        )
        self.text_filter.count_label.setText(f"Zobrazeno: {visible} / {total}")

    def _update_action_buttons(self) -> None:
        item = self._selected_item()
        if item is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        self.activate_button.setEnabled(not item.active)
        self.deactivate_button.setEnabled(item.active)

    def _selected_item(self) -> CategoryDraft | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        table_item = self.table.item(selected[0].row(), COL_NAME)
        if table_item is None:
            return None
        key = table_item.data(Qt.ItemDataRole.UserRole)
        for item in self._working_items:
            if item.key == key:
                return item
        return None

    def _validate_name(self, name: str, *, exclude_key: int | None = None) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized:
            raise HazardSourceCategoryError("Název kategorie je povinný.")
        needle = normalize_category_name(normalized)
        for item in self._working_items:
            if item.key == exclude_key:
                continue
            if normalize_category_name(item.name) == needle:
                raise HazardSourceCategoryError(
                    f"Kategorie „{item.name}“ již existuje.",
                )
        return normalized

    def _ensure_can_deactivate(self, item: CategoryDraft) -> None:
        if not item.code:
            return
        count = hazard_source_category_service.count_active_sources(item.code)
        if count:
            noun = "aktivní zdroj" if count == 1 else "aktivních zdrojů"
            raise HazardSourceCategoryError(
                f"Kategorie obsahuje {count} {noun}. "
                "Před deaktivací přesuňte zdroje do jiné aktivní kategorie.",
            )

    def add_category(self) -> None:
        dialog = HazardSourceCategoryDialog(self)
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            name = self._validate_name(data["name"])
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return
        self._working_items.append(
            CategoryDraft(
                key=self._next_temp_key,
                code=None,
                name=name,
                description=data["description"],
                sort_order=data["sort_order"],
                active=bool(data["active"]),
                is_new=True,
            ),
        )
        self._next_temp_key -= 1
        self._mark_dirty()
        self.refresh()

    def edit_selected_category(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, DIALOG_TITLE, "Vyberte kategorii.")
            return
        dialog = HazardSourceCategoryDialog(self, category=item)
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            name = self._validate_name(data["name"], exclude_key=item.key)
            will_deactivate = item.active and not data["active"]
            if will_deactivate:
                self._ensure_can_deactivate(item)
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return
        item.name = name
        item.description = data["description"]
        item.sort_order = data["sort_order"]
        item.active = bool(data["active"])
        self._mark_dirty()
        self.refresh()

    def activate_selected_category(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        try:
            self._validate_name(item.name, exclude_key=item.key)
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return
        item.active = True
        self._mark_dirty()
        self.refresh()

    def deactivate_selected_category(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        try:
            self._ensure_can_deactivate(item)
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return
        item.active = False
        self._mark_dirty()
        self.refresh()

    def _validate_working_copy_for_save(self) -> None:
        seen: set[str] = set()
        for item in self._working_items:
            name = self._validate_name(item.name, exclude_key=item.key)
            needle = normalize_category_name(name)
            if needle in seen:
                raise HazardSourceCategoryError(f"Kategorie „{item.name}“ již existuje.")
            seen.add(needle)

        original_by_id = {
            category.id: category
            for category in hazard_source_category_service.get_all(include_inactive=True)
        }
        for item in self._working_items:
            if item.is_new or item.active:
                continue
            original = original_by_id.get(item.key)
            if original is not None and original.active and not item.active:
                self._ensure_can_deactivate(item)

    def _save_all(self) -> bool:
        if not self.is_dirty():
            return True
        try:
            self._validate_working_copy_for_save()
            for item in list(self._working_items):
                if item.is_new:
                    created = hazard_source_category_service.create_category(
                        name=item.name,
                        description=item.description,
                        active=item.active,
                        sort_order=item.sort_order,
                    )
                    item.key = created.id
                    item.code = created.code
                    item.is_new = False
                else:
                    hazard_source_category_service.update_category(
                        item.key,
                        name=item.name,
                        description=item.description,
                        active=item.active,
                        sort_order=item.sort_order,
                    )
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return False

        self._load_working_copy()
        self.refresh()
        return True

    def _prompt_unsaved_close(self) -> str:
        message = QMessageBox(self)
        message.setWindowTitle(DIALOG_TITLE)
        message.setText(UNSAVED_PROMPT)
        message.setIcon(QMessageBox.Icon.Question)
        save_btn = message.addButton(UNSAVED_SAVE, QMessageBox.ButtonRole.AcceptRole)
        discard_btn = message.addButton(
            UNSAVED_DISCARD,
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = message.addButton(
            UNSAVED_CANCEL_CLOSE,
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(cancel_btn)
        message.exec()
        clicked = message.clickedButton()
        if clicked is save_btn:
            return "save"
        if clicked is discard_btn:
            return "discard"
        return "cancel"

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing or not self.is_dirty():
            self._closing = True
            super().closeEvent(event)
            return
        decision = self._prompt_unsaved_close()
        if decision == "cancel":
            event.ignore()
            return
        if decision == "save":
            if not self._save_all():
                event.ignore()
                return
        self._closing = True
        super().closeEvent(event)

    def reject(self) -> None:
        if self._closing:
            super().reject()
            return
        if self.is_dirty():
            decision = self._prompt_unsaved_close()
            if decision == "cancel":
                return
            if decision == "save":
                if not self._save_all():
                    return
        self._closing = True
        super().reject()

    def accept(self) -> None:
        if self.is_dirty() and not self._save_all():
            return
        self._closing = True
        super().accept()
