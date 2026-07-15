from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    format_event_display_name,
    format_inventory_item_display_name,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_CONTENT_INTRO_TEXT,
    HAZARD_LIBRARY_CONTENT_READ_ONLY_MESSAGE,
    HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
    HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
    HAZARD_LIBRARY_TEMPLATE_EVENT_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_EVENT_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_EVENTS_SECTION_TITLE,
    HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_ITEM_COL_DESCRIPTION,
    HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_ITEM_COL_NAME,
    HAZARD_LIBRARY_TEMPLATE_ITEM_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_ITEM_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
    HAZARD_LIBRARY_TEMPLATE_SELECT_ITEM,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    HazardLibraryTemplateEventError,
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_item_service import (
    HazardLibraryTemplateItemError,
    hazard_library_template_item_service,
)
from moduly.rizeni_rizik.ui.hazard_library_template_assessments_dialog import (
    HazardLibraryTemplateAssessmentsDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_template_event_dialog import (
    HazardLibraryTemplateEventDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_template_item_dialog import (
    HazardLibraryTemplateItemDialog,
)


class HazardLibraryTemplateContentWidget(QWidget):
    content_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._template_id: int | None = None
        self._read_only = False
        self._current_category = HAZARD_INVENTORY_CATEGORIES[0]
        self._selected_item_id: int | None = None
        self._selected_event_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(HAZARD_LIBRARY_CONTENT_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.toolbar.addWidget(self.add_btn)
        self.toolbar.addWidget(self.edit_btn)
        self.toolbar.addWidget(self.activate_btn)
        self.toolbar.addWidget(self.deactivate_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setMinimumWidth(240)
        main_splitter.addWidget(self.category_list)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_ITEM_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TEMPLATE_ITEM_TABLE_HEADERS)
        self.table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_library_template_items")
        right_splitter.addWidget(self.table)

        events_panel = QWidget()
        events_layout = QVBoxLayout(events_panel)
        events_layout.setContentsMargins(0, 0, 0, 0)
        events_layout.addWidget(QLabel(HAZARD_LIBRARY_TEMPLATE_EVENTS_SECTION_TITLE))

        self.events_toolbar = QHBoxLayout()
        self.add_event_btn = QPushButton("Přidat událost")
        self.edit_event_btn = QPushButton("Upravit")
        self.assessments_btn = QPushButton("Posouzení a opatření")
        self.activate_event_btn = QPushButton("Aktivovat")
        self.deactivate_event_btn = QPushButton("Deaktivovat")
        self.events_toolbar.addWidget(self.add_event_btn)
        self.events_toolbar.addWidget(self.edit_event_btn)
        self.events_toolbar.addWidget(self.assessments_btn)
        self.events_toolbar.addWidget(self.activate_event_btn)
        self.events_toolbar.addWidget(self.deactivate_event_btn)
        self.events_toolbar.addStretch()
        events_layout.addLayout(self.events_toolbar)

        self.events_table = QTableWidget()
        self.events_table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_EVENT_COLUMN_COUNT)
        self.events_table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TEMPLATE_EVENT_TABLE_HEADERS)
        self.events_table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID, True)
        self.events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.events_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        configure_table_columns(self.events_table, "hazard_library_template_events")
        events_layout.addWidget(self.events_table, 1)

        right_splitter.addWidget(events_panel)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(1, 1)
        layout.addWidget(main_splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.edit_btn.clicked.connect(self.edit_selected_item)
        self.activate_btn.clicked.connect(self.activate_selected_item)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_item)
        self.add_event_btn.clicked.connect(self.add_event_for_selected_item)
        self.edit_event_btn.clicked.connect(self.edit_selected_event)
        self.assessments_btn.clicked.connect(self.open_assessments_for_selected_event)
        self.activate_event_btn.clicked.connect(self.activate_selected_event)
        self.deactivate_event_btn.clicked.connect(self.deactivate_selected_event)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.table.itemSelectionChanged.connect(self._on_item_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_item)
        self.events_table.itemSelectionChanged.connect(self._on_event_selection_changed)
        self.events_table.doubleClicked.connect(self.edit_selected_event)

        self._populate_categories()
        self.set_template(None, read_only=False)

    def set_template(
        self,
        template_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._template_id = template_id
        self._read_only = read_only
        self._selected_item_id = None
        self._selected_event_id = None
        editable = not read_only and template_id is not None
        self._set_item_actions_enabled(editable)
        self._set_event_actions_enabled(False)
        self.refresh()

    def refresh(self) -> None:
        self._populate_categories()
        self._load_table()
        self._load_events_table()

    def add_item(self) -> None:
        if not self._ensure_editable():
            return
        dialog = HazardLibraryTemplateItemDialog(
            self,
            template_id=self._template_id,
            default_category=self._current_category,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def edit_selected_item(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_ITEM,
            )
            return
        dialog = HazardLibraryTemplateItemDialog(
            self,
            template_id=self._template_id,
            item=item,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def activate_selected_item(self) -> None:
        if not self._ensure_editable():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_ITEM,
            )
            return
        if item.active:
            QMessageBox.information(self, HAZARD_LIBRARY_ITEM_DIALOG_TITLE, "Položka je již aktivní.")
            return
        try:
            hazard_library_template_item_service.activate_item(item.id)
        except HazardLibraryTemplateItemError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_ITEM_DIALOG_TITLE, str(error))
            return
        self._notify_content_changed()
        self.refresh()

    def deactivate_selected_item(self) -> None:
        if not self._ensure_editable():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_ITEM,
            )
            return
        if not item.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                "Položka je již neaktivní.",
            )
            return
        hazard_library_template_item_service.deactivate_item(item.id)
        self._notify_content_changed()
        self.refresh()

    def add_event_for_selected_item(self) -> None:
        if not self._ensure_editable():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_ITEM,
            )
            return
        dialog = HazardLibraryTemplateEventDialog(
            self,
            template_id=self._template_id,
            default_template_item_id=item.id,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def edit_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        dialog = HazardLibraryTemplateEventDialog(
            self,
            template_id=self._template_id,
            event=event,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_content_changed()
            self.refresh()

    def open_assessments_for_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        dialog = HazardLibraryTemplateAssessmentsDialog(
            self,
            template_id=self._template_id,
            template_event_id=event.id,
            event_name=event.name,
            read_only=self._read_only,
            on_content_changed=self._notify_content_changed,
        )
        dialog.exec()
        self.refresh()

    def activate_selected_event(self) -> None:
        if not self._ensure_editable():
            return
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        if event.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již aktivní.",
            )
            return
        try:
            hazard_library_template_event_service.activate_event(event.id)
        except HazardLibraryTemplateEventError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_EVENT_DIALOG_TITLE, str(error))
            return
        self._notify_content_changed()
        self.refresh()

    def deactivate_selected_event(self) -> None:
        if not self._ensure_editable():
            return
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                HAZARD_LIBRARY_TEMPLATE_SELECT_EVENT,
            )
            return
        if not event.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již neaktivní.",
            )
            return
        hazard_library_template_event_service.deactivate_event(event.id)
        self._notify_content_changed()
        self.refresh()

    def _notify_content_changed(self) -> None:
        self.content_changed.emit()

    def _ensure_editable(self) -> bool:
        if self._template_id is None:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                "Nejprve uložte základní údaje vzoru.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_ITEM_DIALOG_TITLE,
                HAZARD_LIBRARY_CONTENT_READ_ONLY_MESSAGE,
            )
            return False
        return True

    def _set_item_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
        ):
            button.setEnabled(enabled)

    def _set_event_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_event_btn,
            self.edit_event_btn,
            self.assessments_btn,
            self.activate_event_btn,
            self.deactivate_event_btn,
        ):
            button.setEnabled(enabled)

    def _populate_categories(self) -> None:
        counts = (
            hazard_library_template_item_service.count_active_by_category(self._template_id)
            if self._template_id is not None
            else {category: 0 for category in HAZARD_INVENTORY_CATEGORIES}
        )
        selected_category = self._current_category
        self.category_list.blockSignals(True)
        self.category_list.clear()
        for category in HAZARD_INVENTORY_CATEGORIES:
            label = HAZARD_INVENTORY_CATEGORY_LABELS[category]
            count = counts.get(category, 0)
            item = QListWidgetItem(f"{label} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        index = HAZARD_INVENTORY_CATEGORIES.index(selected_category)
        self.category_list.setCurrentRow(index)
        self.category_list.blockSignals(False)

    def _load_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._template_id is None:
            self.table.blockSignals(False)
            self._update_event_actions_for_selection()
            return

        event_counts = hazard_library_template_event_service.count_active_by_template_items(
            self._template_id
        )
        assessment_counts = hazard_library_template_assessment_service.count_active_by_events(
            self._template_id
        )
        items = hazard_library_template_item_service.get_by_category(
            self._template_id,
            self._current_category,
            include_inactive=True,
        )
        self.table.setRowCount(len(items))
        selected_row = -1
        for row, item in enumerate(items):
            self.table.setItem(
                row,
                HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ID,
                QTableWidgetItem(str(item.id)),
            )
            display_name = format_inventory_item_display_name(
                item.name,
                event_count=event_counts.get(item.id, 0),
            )
            self.table.setItem(
                row,
                HAZARD_LIBRARY_TEMPLATE_ITEM_COL_NAME,
                QTableWidgetItem(display_name),
            )
            self.table.setItem(
                row,
                HAZARD_LIBRARY_TEMPLATE_ITEM_COL_DESCRIPTION,
                create_preview_table_item(item.description),
            )
            self.table.setItem(
                row,
                HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ACTIVE,
                QTableWidgetItem("Ano" if item.active else "Ne"),
            )
            if self._selected_item_id == item.id:
                selected_row = row

        configure_table_columns(self.table, "hazard_library_template_items")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        else:
            self._selected_item_id = None
            self._selected_event_id = None
        self.table.blockSignals(False)
        self._update_event_actions_for_selection()
        self._assessment_counts = assessment_counts

    def _load_events_table(self) -> None:
        self.events_table.blockSignals(True)
        self.events_table.setRowCount(0)

        if self._template_id is None or self._selected_item_id is None:
            self.events_table.blockSignals(False)
            self._update_event_actions_for_selection()
            return

        assessment_counts = getattr(self, "_assessment_counts", {})
        events = hazard_library_template_event_service.get_for_template_item(
            self._selected_item_id,
            include_inactive=True,
        )
        self.events_table.setRowCount(len(events))
        selected_row = -1
        for row_index, event in enumerate(events):
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID,
                QTableWidgetItem(str(event.id)),
            )
            display_name = format_event_display_name(
                event.name,
                assessment_count=assessment_counts.get(event.id, 0),
            )
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
                QTableWidgetItem(display_name),
            )
            self.events_table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if event.active else "Ne"),
            )
            if self._selected_event_id == event.id:
                selected_row = row_index

        configure_table_columns(self.events_table, "hazard_library_template_events")
        if selected_row >= 0:
            self.events_table.selectRow(selected_row)
        else:
            self._selected_event_id = None
        self.events_table.blockSignals(False)

    def _update_event_actions_for_selection(self) -> None:
        has_template = self._template_id is not None
        has_item = self._selected_item_id is not None
        editable = not self._read_only and has_template and has_item
        self._set_event_actions_enabled(has_template and has_item)
        self.assessments_btn.setEnabled(has_template and self._selected_event_id is not None)
        if self._read_only:
            self.add_event_btn.setEnabled(False)
            self.edit_event_btn.setEnabled(has_template and has_item)
            self.activate_event_btn.setEnabled(False)
            self.deactivate_event_btn.setEnabled(False)
            self.assessments_btn.setEnabled(has_template and self._selected_event_id is not None)
        else:
            self.add_event_btn.setEnabled(editable)
            self.edit_event_btn.setEnabled(has_template and has_item)
            self.activate_event_btn.setEnabled(editable)
            self.deactivate_event_btn.setEnabled(editable)

    def _on_category_changed(self, row: int) -> None:
        item = self.category_list.item(row)
        if item is None:
            return
        category = item.data(Qt.ItemDataRole.UserRole)
        if category:
            self._current_category = category
            self._selected_item_id = None
            self._selected_event_id = None
            self._load_table()
            self._load_events_table()

    def _on_item_selection_changed(self) -> None:
        item = self._selected_item()
        new_id = item.id if item is not None else None
        if new_id == self._selected_item_id:
            return
        self._selected_item_id = new_id
        self._selected_event_id = None
        self._load_events_table()
        self._update_event_actions_for_selection()

    def _on_event_selection_changed(self) -> None:
        event = self._selected_event()
        self._selected_event_id = event.id if event is not None else None
        self._update_event_actions_for_selection()

    def _selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), HAZARD_LIBRARY_TEMPLATE_ITEM_COL_ID)
        if id_item is None:
            return None
        return hazard_library_template_item_service.get_by_id(int(id_item.text()))

    def _selected_event(self):
        selected = self.events_table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.events_table.item(selected[0].row(), HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ID)
        if id_item is None:
            return None
        return hazard_library_template_event_service.get_by_id(int(id_item.text()))
