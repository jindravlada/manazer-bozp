from PySide6.QtCore import Qt
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
    HAZARD_EVENT_DIALOG_TITLE,
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    INVENTORY_ADD_NEW_BUTTON,
    INVENTORY_COL_ACTIVE,
    INVENTORY_COL_DESCRIPTION,
    INVENTORY_COL_ID,
    INVENTORY_COL_NAME,
    INVENTORY_COLUMN_COUNT,
    INVENTORY_INTRO_TEXT,
    INVENTORY_ITEM_DIALOG_TITLE,
    INVENTORY_TABLE_HEADERS,
    ITEM_EVENT_COL_ACTIVE,
    ITEM_EVENT_COL_ID,
    ITEM_EVENT_COL_NAME,
    ITEM_EVENT_COLUMN_COUNT,
    ITEM_EVENT_TABLE_HEADERS,
    ITEM_EVENTS_SECTION_TITLE,
    ITEM_EVENTS_SELECT_EVENT,
    ITEM_EVENTS_SELECT_ITEM,
    WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
    WORKPLACE_ANALYSIS_SELECT_ITEM,
    can_save_inventory_item_to_library,
    format_event_display_name,
    format_inventory_item_display_name,
)
from moduly.rizeni_rizik.constants_library import (
    CATALOG_COMPARE_WITH_MASTER_BUTTON,
    CATALOG_COMPARE_WITH_MASTER_NOT_CATALOG_ITEM,
    CATALOG_COMPARE_WITH_MASTER_SELECT_ITEM,
    CATALOG_UPDATE_SUCCESS_TEXT,
    CATALOG_UPDATE_SUCCESS_TITLE,
    HAZARD_LIBRARY_APPLY_ARCHIVED_MESSAGE,
    HAZARD_LIBRARY_APPLY_TO_INVENTORY_BUTTON,
    HAZARD_LIBRARY_APPLY_TO_INVENTORY_SUCCESS_TITLE,
    HAZARD_LIBRARY_OPEN_IN_LIBRARY_BUTTON,
    HAZARD_LIBRARY_SAVE_ARCHIVED_MESSAGE,
    HAZARD_LIBRARY_SAVE_FROM_INVENTORY_SUCCESS_TITLE,
    HAZARD_LIBRARY_SAVE_INACTIVE_ITEM_MESSAGE,
    HAZARD_LIBRARY_SAVE_TO_LIBRARY_BUTTON,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
    HazardCatalogInstanceUpdateError,
    hazard_catalog_instance_update_service,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_compare_service import (
    HazardCatalogInstanceCompareError,
    hazard_catalog_instance_compare_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
    hazard_library_template_apply_service,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventError,
    hazard_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import hazard_inventory_item_service
from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
    hazard_library_template_import_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import hazard_risk_assessment_service
from moduly.rizeni_rizik.ui.hazard_catalog_instance_update_offer_dialog import (
    CATALOG_UPDATE_CHOICE_KEEP,
    CATALOG_UPDATE_CHOICE_SHOW_DIFF,
    CATALOG_UPDATE_CHOICE_UPDATE,
    HazardCatalogInstanceUpdateOfferDialog,
)
from moduly.rizeni_rizik.ui.hazard_catalog_instance_compare_dialog import (
    HazardCatalogInstanceCompareDialog,
)
from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog
from moduly.rizeni_rizik.ui.hazard_inventory_item_dialog import HazardInventoryItemDialog
from moduly.rizeni_rizik.ui.hazard_library_apply_to_inventory_dialog import (
    HazardLibraryApplyToInventoryDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_save_from_inventory_dialog import (
    HazardLibrarySaveFromInventoryDialog,
)


class HazardInventoryWidget(QWidget):
    def __init__(self, parent=None, on_event_saved=None, on_open_library_template=None):
        super().__init__(parent)

        self._on_event_saved = on_event_saved
        self._on_open_library_template = on_open_library_template

        self._identification_id: int | None = None
        self._identification_status = ""
        self._read_only = False
        self._current_category = HAZARD_INVENTORY_CATEGORIES[0]
        self._selected_item_id: int | None = None
        self._selected_event_id: int | None = None
        self._dismissed_master_update_offers: set[int] = set()

        layout = QVBoxLayout(self)

        intro = QLabel(INVENTORY_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.toolbar = QHBoxLayout()
        self.add_btn = QPushButton(INVENTORY_ADD_NEW_BUTTON)
        self.apply_from_library_btn = QPushButton(HAZARD_LIBRARY_APPLY_TO_INVENTORY_BUTTON)
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.save_to_library_btn = QPushButton(HAZARD_LIBRARY_SAVE_TO_LIBRARY_BUTTON)
        self.compare_with_master_btn = QPushButton(CATALOG_COMPARE_WITH_MASTER_BUTTON)
        self.toolbar.addWidget(self.add_btn)
        self.toolbar.addWidget(self.apply_from_library_btn)
        self.toolbar.addWidget(self.edit_btn)
        self.toolbar.addWidget(self.activate_btn)
        self.toolbar.addWidget(self.deactivate_btn)
        self.toolbar.addWidget(self.save_to_library_btn)
        self.toolbar.addWidget(self.compare_with_master_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setMinimumWidth(240)
        main_splitter.addWidget(self.category_list)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(INVENTORY_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(INVENTORY_TABLE_HEADERS)
        self.table.setColumnHidden(INVENTORY_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_inventory_items")
        right_splitter.addWidget(self.table)

        events_panel = QWidget()
        events_layout = QVBoxLayout(events_panel)
        events_layout.setContentsMargins(0, 0, 0, 0)
        events_layout.addWidget(QLabel(ITEM_EVENTS_SECTION_TITLE))

        self.events_toolbar = QHBoxLayout()
        self.add_event_btn = QPushButton("Přidat událost")
        self.edit_event_btn = QPushButton("Upravit")
        self.activate_event_btn = QPushButton("Aktivovat")
        self.deactivate_event_btn = QPushButton("Deaktivovat")
        self.events_toolbar.addWidget(self.add_event_btn)
        self.events_toolbar.addWidget(self.edit_event_btn)
        self.events_toolbar.addWidget(self.activate_event_btn)
        self.events_toolbar.addWidget(self.deactivate_event_btn)
        self.events_toolbar.addStretch()
        events_layout.addLayout(self.events_toolbar)

        self.events_table = QTableWidget()
        self.events_table.setColumnCount(ITEM_EVENT_COLUMN_COUNT)
        self.events_table.setHorizontalHeaderLabels(ITEM_EVENT_TABLE_HEADERS)
        self.events_table.setColumnHidden(ITEM_EVENT_COL_ID, True)
        self.events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.events_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        configure_table_columns(self.events_table, "hazard_inventory_item_events")
        events_layout.addWidget(self.events_table, 1)

        right_splitter.addWidget(events_panel)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(1, 1)
        layout.addWidget(main_splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.apply_from_library_btn.clicked.connect(self.apply_from_library)
        self.edit_btn.clicked.connect(self.edit_selected_item)
        self.activate_btn.clicked.connect(self.activate_selected_item)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_item)
        self.save_to_library_btn.clicked.connect(self.save_selected_item_to_library)
        self.compare_with_master_btn.clicked.connect(self.compare_selected_item_with_master)
        self.add_event_btn.clicked.connect(self.add_event_for_selected_item)
        self.edit_event_btn.clicked.connect(self.edit_selected_event)
        self.activate_event_btn.clicked.connect(self.activate_selected_event)
        self.deactivate_event_btn.clicked.connect(self.deactivate_selected_event)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.table.itemSelectionChanged.connect(self._on_item_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_item)
        self.events_table.itemSelectionChanged.connect(self._on_event_selection_changed)
        self.events_table.doubleClicked.connect(self.edit_selected_event)

        self._populate_categories()
        self.set_identification(None, read_only=False, identification_status="")

    def _store(self):
        return find_identification_working_copy(self)

    def _notify_editor_dirty(self) -> None:
        window = self.window()
        update = getattr(window, "_update_save_enabled", None)
        if callable(update):
            update()

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
        identification_status: str = "",
    ) -> None:
        self._identification_id = identification_id
        self._identification_status = identification_status
        self._read_only = read_only
        self._selected_item_id = None
        self._selected_event_id = None
        self._dismissed_master_update_offers.clear()
        editable = not read_only and identification_id is not None
        self._set_item_actions_enabled(editable)
        self._set_event_actions_enabled(False)
        self._update_save_to_library_enabled()
        self._update_apply_from_library_enabled()
        self.compare_with_master_btn.setEnabled(False)
        self._update_compare_with_master_enabled()
        self.refresh()

    def refresh(self) -> None:
        self._populate_categories()
        self._load_table()
        self._load_events_table()

    def add_item(self) -> None:
        if not self._ensure_editable():
            return

        dialog = HazardInventoryItemDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_category=self._current_category,
        )
        if dialog.exec():
            self.refresh()
            self._notify_editor_dirty()

    def apply_from_library(self) -> None:
        if not self._ensure_editable():
            return
        if self._identification_id is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return
        if not hazard_library_template_apply_service.can_apply_template(
            hazard_identification_id=self._identification_id,
            identification_status=self._identification_status,
        ):
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_APPLY_TO_INVENTORY_SUCCESS_TITLE,
                HAZARD_LIBRARY_APPLY_ARCHIVED_MESSAGE,
            )
            return

        dialog = HazardLibraryApplyToInventoryDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_category=self._current_category,
            inventory_items=(
                store.get_items(include_inactive=True)
                if (store := self._store()) is not None
                else None
            ),
        )
        if not dialog.exec() or dialog.result is None:
            return

        result = dialog.result
        self._current_category = result.item.category
        category_index = HAZARD_INVENTORY_CATEGORIES.index(self._current_category)
        self.category_list.setCurrentRow(category_index)
        self._selected_item_id = result.item.id
        self._selected_event_id = None

        summary = (
            f"Název zdroje: {result.item.name}\n"
            f"Nežádoucí události: {result.event_count}\n"
            f"Posouzení: {result.assessment_count}\n"
            f"Existující opatření: {result.existing_measure_count}\n"
            f"Potřebná opatření: {result.required_measure_count}"
        )
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Information)
        message.setWindowTitle(HAZARD_LIBRARY_APPLY_TO_INVENTORY_SUCCESS_TITLE)
        message.setText("Zdroj rizika byl převzat z katalogu a vložen do analýzy pracoviště.")
        message.setInformativeText(summary)
        message.exec()
        self._notify_event_saved()
        self.refresh()
        self._notify_editor_dirty()

    def edit_selected_item(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return

        dialog = HazardInventoryItemDialog(
            self,
            hazard_identification_id=self._identification_id,
            item=item,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()
            self._notify_editor_dirty()

    def activate_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return
        if item.active:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Položka je již aktivní.")
            return

        from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import HazardInventoryItemError

        store = self._store()
        try:
            if store is not None:
                store.activate_item(item.id)
            else:
                hazard_inventory_item_service.activate_item(item.id)
        except HazardInventoryItemError as error:
            QMessageBox.warning(self, INVENTORY_ITEM_DIALOG_TITLE, str(error))
            return
        self.refresh()
        self._notify_editor_dirty()

    def deactivate_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return
        if not item.active:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Položka je již neaktivní.")
            return

        store = self._store()
        if store is not None:
            store.deactivate_item(item.id)
        else:
            hazard_inventory_item_service.deactivate_item(item.id)
        self.refresh()
        self._notify_editor_dirty()

    def save_selected_item_to_library(self) -> None:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return
        if not can_save_inventory_item_to_library(self._identification_status):
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_SAVE_FROM_INVENTORY_SUCCESS_TITLE,
                HAZARD_LIBRARY_SAVE_ARCHIVED_MESSAGE,
            )
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                WORKPLACE_ANALYSIS_SELECT_ITEM,
            )
            return
        if not item.active:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_SAVE_FROM_INVENTORY_SUCCESS_TITLE,
                HAZARD_LIBRARY_SAVE_INACTIVE_ITEM_MESSAGE,
            )
            return

        dialog = HazardLibrarySaveFromInventoryDialog(
            self,
            hazard_identification_id=self._identification_id,
            inventory_item_id=item.id,
            default_name=item.name,
        )
        if not dialog.exec() or dialog.result is None:
            return

        result = dialog.result
        summary = (
            f"Název zdroje: {result.template.name}\n"
            f"Nežádoucí události: {result.event_count}\n"
            f"Posouzení: {result.assessment_count}\n"
            f"Existující opatření: {result.existing_measure_count}\n"
            f"Potřebná opatření: {result.required_measure_count}"
        )
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Information)
        message.setWindowTitle(HAZARD_LIBRARY_SAVE_FROM_INVENTORY_SUCCESS_TITLE)
        message.setText("Zdroj rizika byl úspěšně uložen do katalogu zdrojů rizik.")
        message.setInformativeText(summary)
        open_button = message.addButton(
            HAZARD_LIBRARY_OPEN_IN_LIBRARY_BUTTON,
            QMessageBox.ButtonRole.ActionRole,
        )
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() == open_button and self._on_open_library_template is not None:
            self._on_open_library_template(result.template.id)

    def compare_selected_item_with_master(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                CATALOG_COMPARE_WITH_MASTER_BUTTON,
                CATALOG_COMPARE_WITH_MASTER_SELECT_ITEM,
            )
            return
        if item.source_template_id is None:
            QMessageBox.information(
                self,
                CATALOG_COMPARE_WITH_MASTER_BUTTON,
                CATALOG_COMPARE_WITH_MASTER_NOT_CATALOG_ITEM,
            )
            return

        try:
            result = hazard_catalog_instance_compare_service.compare(item.id)
        except HazardCatalogInstanceCompareError as error:
            QMessageBox.warning(self, CATALOG_COMPARE_WITH_MASTER_BUTTON, str(error))
            return

        dialog = HazardCatalogInstanceCompareDialog(self, result=result)
        dialog.exec()

    def _maybe_offer_master_update(self, item) -> None:
        if item is None:
            return
        if item.source_template_id is None or item.source_template_version is None:
            return
        if not hazard_catalog_instance_update_service.can_offer_update(
            hazard_identification_id=self._identification_id,
            identification_status=self._identification_status,
            read_only=self._read_only,
        ):
            return
        if item.id in self._dismissed_master_update_offers:
            return

        try:
            offer = hazard_catalog_instance_update_service.get_update_offer(item.id)
        except HazardCatalogInstanceUpdateError:
            return
        if offer is None:
            return

        dialog = HazardCatalogInstanceUpdateOfferDialog(self, offer=offer)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.selected_choice == CATALOG_UPDATE_CHOICE_KEEP:
            self._dismissed_master_update_offers.add(item.id)
            return
        if dialog.selected_choice == CATALOG_UPDATE_CHOICE_SHOW_DIFF:
            self.compare_selected_item_with_master()
            return
        if dialog.selected_choice == CATALOG_UPDATE_CHOICE_UPDATE:
            try:
                result = hazard_catalog_instance_update_service.update_from_master(item.id)
            except HazardCatalogInstanceUpdateError as error:
                QMessageBox.warning(self, CATALOG_UPDATE_SUCCESS_TITLE, str(error))
                return

            self._dismissed_master_update_offers.discard(item.id)
            QMessageBox.information(
                self,
                CATALOG_UPDATE_SUCCESS_TITLE,
                CATALOG_UPDATE_SUCCESS_TEXT.format(
                    previous_version=result.previous_version,
                    new_version=result.new_version,
                ),
            )
            self._notify_event_saved()
            self.refresh()

    def add_event_for_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                ITEM_EVENTS_SELECT_ITEM,
            )
            return

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_inventory_item_id=item.id,
        )
        if dialog.exec():
            self._notify_event_saved()
            self.refresh()
            self._notify_editor_dirty()

    def edit_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                ITEM_EVENTS_SELECT_EVENT,
            )
            return

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            event=event,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_event_saved()
            self.refresh()
            self._notify_editor_dirty()

    def activate_selected_event(self) -> None:
        if not self._ensure_editable():
            return

        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                ITEM_EVENTS_SELECT_EVENT,
            )
            return
        if event.active:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již aktivní.",
            )
            return

        store = self._store()
        try:
            if store is not None:
                store.activate_event(event.id)
            else:
                hazard_event_service.activate_event(event.id)
        except HazardEventError as error:
            QMessageBox.warning(self, HAZARD_EVENT_DIALOG_TITLE, str(error))
            return
        self._notify_event_saved()
        self.refresh()
        self._notify_editor_dirty()

    def deactivate_selected_event(self) -> None:
        if not self._ensure_editable():
            return

        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                ITEM_EVENTS_SELECT_EVENT,
            )
            return
        if not event.active:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již neaktivní.",
            )
            return

        store = self._store()
        if store is not None:
            store.deactivate_event(event.id)
        else:
            hazard_event_service.deactivate_event(event.id)
        self._notify_event_saved()
        self.refresh()
        self._notify_editor_dirty()

    def _notify_event_saved(self) -> None:
        if self._on_event_saved is not None:
            self._on_event_saved()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
            )
            return False
        return True

    def _set_item_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_btn,
            self.apply_from_library_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
        ):
            button.setEnabled(enabled)

    def _set_event_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_event_btn,
            self.edit_event_btn,
            self.activate_event_btn,
            self.deactivate_event_btn,
        ):
            button.setEnabled(enabled)

    def _update_save_to_library_enabled(self) -> None:
        item = self._selected_item()
        enabled = hazard_library_template_import_service.can_save_inventory_item(
            hazard_identification_id=self._identification_id,
            identification_status=self._identification_status,
            inventory_item_id=item.id if item is not None else None,
        )
        self.save_to_library_btn.setEnabled(enabled)

    def _update_apply_from_library_enabled(self) -> None:
        enabled = hazard_library_template_apply_service.can_apply_template(
            hazard_identification_id=self._identification_id,
            identification_status=self._identification_status,
        )
        self.apply_from_library_btn.setEnabled(
            enabled and not self._read_only and self._identification_id is not None
        )

    def _update_compare_with_master_enabled(self) -> None:
        item = self._selected_item()
        enabled = (
            self._identification_id is not None
            and item is not None
            and item.source_template_id is not None
            and item.source_template_version is not None
        )
        self.compare_with_master_btn.setEnabled(enabled)

    def _populate_categories(self) -> None:
        store = self._store()
        if store is not None:
            counts = store.count_active_by_category()
        elif self._identification_id is not None:
            counts = hazard_inventory_item_service.count_active_by_category(
                self._identification_id,
            )
        else:
            counts = {category: 0 for category in HAZARD_INVENTORY_CATEGORIES}

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
        if self._identification_id is None:
            self.table.blockSignals(False)
            self._update_event_actions_for_selection()
            return

        store = self._store()
        if store is not None:
            event_counts = store.count_active_by_inventory_items()
            items = store.get_items(
                category=self._current_category,
                include_inactive=True,
            )
        else:
            event_counts = hazard_event_service.count_active_by_inventory_items(
                self._identification_id,
            )
            items = hazard_inventory_item_service.get_by_category(
                self._identification_id,
                self._current_category,
                include_inactive=True,
            )
        self.table.setRowCount(len(items))
        selected_row = -1
        for row, item in enumerate(items):
            self.table.setItem(row, INVENTORY_COL_ID, QTableWidgetItem(str(item.id)))
            display_name = format_inventory_item_display_name(
                item.name,
                event_count=event_counts.get(item.id, 0),
            )
            self.table.setItem(row, INVENTORY_COL_NAME, QTableWidgetItem(display_name))
            self.table.setItem(
                row,
                INVENTORY_COL_DESCRIPTION,
                create_preview_table_item(item.description),
            )
            self.table.setItem(
                row,
                INVENTORY_COL_ACTIVE,
                QTableWidgetItem("Ano" if item.active else "Ne"),
            )
            if self._selected_item_id == item.id:
                selected_row = row

        configure_table_columns(self.table, "hazard_inventory_items")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        else:
            self._selected_item_id = None
            self._selected_event_id = None
        self.table.blockSignals(False)
        self._update_event_actions_for_selection()
        self._update_save_to_library_enabled()
        self._update_compare_with_master_enabled()

    def _load_events_table(self) -> None:
        self.events_table.blockSignals(True)
        self.events_table.setRowCount(0)

        if self._identification_id is None or self._selected_item_id is None:
            self.events_table.blockSignals(False)
            self._update_event_actions_for_selection()
            return

        store = self._store()
        if store is not None:
            assessment_counts = store.count_active_by_events()
            events = store.get_events_for_item(
                self._selected_item_id,
                include_inactive=True,
            )
        else:
            assessment_counts = hazard_risk_assessment_service.count_active_by_events(
                self._identification_id,
            )
            events = hazard_event_service.get_for_inventory_item(
                self._selected_item_id,
                include_inactive=True,
            )
        self.events_table.setRowCount(len(events))
        selected_row = -1
        for row_index, event in enumerate(events):
            self.events_table.setItem(
                row_index,
                ITEM_EVENT_COL_ID,
                QTableWidgetItem(str(event.id)),
            )
            display_name = format_event_display_name(
                event.name,
                assessment_count=assessment_counts.get(event.id, 0),
            )
            self.events_table.setItem(
                row_index,
                ITEM_EVENT_COL_NAME,
                QTableWidgetItem(display_name),
            )
            self.events_table.setItem(
                row_index,
                ITEM_EVENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if event.active else "Ne"),
            )
            if self._selected_event_id == event.id:
                selected_row = row_index

        configure_table_columns(self.events_table, "hazard_inventory_item_events")
        if selected_row >= 0:
            self.events_table.selectRow(selected_row)
        else:
            self._selected_event_id = None
        self.events_table.blockSignals(False)

    def _update_event_actions_for_selection(self) -> None:
        editable = (
            not self._read_only
            and self._identification_id is not None
            and self._selected_item_id is not None
        )
        self._set_event_actions_enabled(editable)

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
        self._update_save_to_library_enabled()
        self._update_compare_with_master_enabled()
        self._maybe_offer_master_update(item)

    def _on_event_selection_changed(self) -> None:
        event = self._selected_event()
        self._selected_event_id = event.id if event is not None else None

    def _selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), INVENTORY_COL_ID)
        if id_item is None:
            return None
        item_id = int(id_item.text())
        store = self._store()
        if store is not None:
            return store.get_item(item_id)
        return hazard_inventory_item_service.get_by_id(item_id)

    def _selected_event(self):
        selected = self.events_table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.events_table.item(selected[0].row(), ITEM_EVENT_COL_ID)
        if id_item is None:
            return None
        event_id = int(id_item.text())
        store = self._store()
        if store is not None:
            return store.get_event(event_id)
        return hazard_event_service.get_by_id(event_id)
