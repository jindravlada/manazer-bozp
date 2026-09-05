from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.rizeni_rizik.constants import (
    RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER,
    RISK_LIST_FILTER_ACTIVE,
    RISK_LIST_FILTER_ALL,
    RISK_LIST_FILTER_INACTIVE,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
    HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL,
    HAZARD_LIBRARY_COL_ACTIVE,
    HAZARD_LIBRARY_COL_CATEGORY,
    HAZARD_LIBRARY_COL_ID,
    HAZARD_LIBRARY_COL_NAME,
    HAZARD_LIBRARY_COL_VERSION,
    HAZARD_LIBRARY_COLUMN_COUNT,
    HAZARD_LIBRARY_DIALOG_TITLE,
    HAZARD_LIBRARY_NEW_BUTTON,
    HAZARD_LIBRARY_PAGE_TITLE,
    HAZARD_LIBRARY_TABLE_HEADERS,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    HazardLibraryTemplateError,
    hazard_library_template_service,
)
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    hazard_source_category_service,
)
from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
from moduly.rizeni_rizik.ui.hazard_source_categories_management_dialog import (
    HazardSourceCategoriesManagementDialog,
)


class HazardLibraryPage(QWidget):
    """Stránka Katalog zdrojů rizik – evidence Master zdrojů rizika."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(HAZARD_LIBRARY_NEW_BUTTON)
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.manage_categories_btn = QPushButton("Spravovat kategorie…")
        self.edit_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)
        self.deactivate_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addWidget(self.manage_categories_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Aktivní:"))
        self.active_filter = QComboBox()
        self.active_filter.addItem(RISK_LIST_FILTER_ACTIVE, RISK_LIST_FILTER_ACTIVE)
        self.active_filter.addItem(RISK_LIST_FILTER_INACTIVE, RISK_LIST_FILTER_INACTIVE)
        self.active_filter.addItem(RISK_LIST_FILTER_ALL, RISK_LIST_FILTER_ALL)
        default_index = self.active_filter.findData(RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER)
        if default_index >= 0:
            self.active_filter.setCurrentIndex(default_index)
        self.active_filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.active_filter)

        self.table = QTableWidget()
        self.table.setColumnCount(HAZARD_LIBRARY_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TABLE_HEADERS)
        self.table.setColumnHidden(HAZARD_LIBRARY_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_library_templates")
        enable_typed_sorting(self.table)
        self.category_filter = QComboBox()
        self.category_filter.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._populate_category_filter()
        self.text_filter = FilterBar(
            self.table,
            placeholder="🔍 Hledat zdroj rizika...",
            apply_fn=self._apply_list_filters,
        )
        self.category_filter.currentIndexChanged.connect(self.text_filter.apply_filter)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel(HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL))
        filter_row.addWidget(self.category_filter)
        filter_row.addWidget(self.text_filter, 1)

        layout.addLayout(toolbar)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_template)
        self.edit_btn.clicked.connect(self.edit_selected_template)
        self.activate_btn.clicked.connect(self.activate_selected_template)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_template)
        self.manage_categories_btn.clicked.connect(self.manage_categories)
        self.table.doubleClicked.connect(self.edit_selected_template)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def _populate_category_filter(self, selected_code: str | None = None) -> None:
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(HAZARD_LIBRARY_APPLY_ALL_CATEGORIES, None)
        for category in hazard_source_category_service.get_active_all():
            self.category_filter.addItem(category.name, category.code)
        if selected_code:
            index = self.category_filter.findData(selected_code)
            self.category_filter.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.category_filter.setCurrentIndex(0)
        self.category_filter.blockSignals(False)

    def _row_matches_category(self, row: int, category_code: str | None) -> bool:
        if not category_code:
            return True
        item = self.table.item(row, HAZARD_LIBRARY_COL_CATEGORY)
        if item is None:
            return False
        return item.data(Qt.ItemDataRole.UserRole) == category_code

    def _apply_list_filters(self, text: str) -> tuple[int, int]:
        category_code = self.category_filter.currentData()
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            match_text = True
            if text:
                row_text_parts = []
                for column in range(self.table.columnCount()):
                    if self.table.isColumnHidden(column):
                        continue
                    item = self.table.item(row, column)
                    if item is not None:
                        row_text_parts.append(item.text())
                match_text = text in " ".join(row_text_parts).lower()
            match = match_text and self._row_matches_category(row, category_code)
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        template = self._selected_template()
        single = template is not None
        self.edit_btn.setEnabled(single)
        self.activate_btn.setEnabled(single and not template.active)
        self.deactivate_btn.setEnabled(single and template.active)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        template = self._selected_template()
        single = template is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_template)
        edit_action.setEnabled(single)
        activate_action = menu.addAction("Aktivovat", self.activate_selected_template)
        activate_action.setEnabled(single and template is not None and not template.active)
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_template)
        deactivate_action.setEnabled(single and template is not None and template.active)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def refresh(self) -> None:
        rows = hazard_library_template_service.get_all_rows(include_inactive=True)
        mode = self.active_filter.currentData()
        if mode == RISK_LIST_FILTER_ACTIVE:
            rows = [row for row in rows if row.template.active]
        elif mode == RISK_LIST_FILTER_INACTIVE:
            rows = [row for row in rows if not row.template.active]
        with sorting_paused(self.table):
            self.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                template = row.template
                record_id = int(template.id)
                name_item = create_typed_item(
                    template.name,
                    typed_text(template.name),
                    stable_id=record_id,
                )
                name_item.setToolTip(template.name)
                self.table.setItem(
                    row_index,
                    HAZARD_LIBRARY_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(row_index, HAZARD_LIBRARY_COL_NAME, name_item)
                category_label = hazard_source_category_service.label_for(template.category)
                category_item = create_typed_item(
                    category_label,
                    typed_text(category_label),
                    stable_id=record_id,
                )
                category_item.setData(Qt.ItemDataRole.UserRole, template.category)
                self.table.setItem(
                    row_index,
                    HAZARD_LIBRARY_COL_CATEGORY,
                    category_item,
                )
                self.table.setItem(
                    row_index,
                    HAZARD_LIBRARY_COL_VERSION,
                    create_typed_item(
                        str(template.version_number),
                        typed_int(template.version_number),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    HAZARD_LIBRARY_COL_ACTIVE,
                    create_typed_item(
                        "Ano" if template.active else "Ne",
                        typed_bool(template.active),
                        stable_id=record_id,
                    ),
                )
        configure_table_columns(self.table, "hazard_library_templates")
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.text_filter.update_count()
        self._refresh_action_buttons()

    def new_template(self) -> None:
        dialog = HazardLibraryTemplateDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def edit_selected_template(self) -> None:
        template = self._selected_template()
        if template is None:
            return
        dialog = HazardLibraryTemplateDialog(self, template=template)
        exec_maximized(dialog)
        self.refresh()

    def activate_selected_template(self) -> None:
        template = self._selected_template()
        if template is None:
            return
        if template.active:
            QMessageBox.information(self, HAZARD_LIBRARY_PAGE_TITLE, "Zdroj rizika je již aktivní.")
            return
        try:
            hazard_library_template_service.activate(template.id)
        except HazardLibraryTemplateError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_DIALOG_TITLE, str(error))
            return
        self.refresh()

    def deactivate_selected_template(self) -> None:
        template = self._selected_template()
        if template is None:
            return
        if not template.active:
            QMessageBox.information(self, HAZARD_LIBRARY_PAGE_TITLE, "Zdroj rizika je již neaktivní.")
            return
        hazard_library_template_service.deactivate(template.id)
        self.refresh()

    def manage_categories(self) -> None:
        selected_code = self.category_filter.currentData()
        dialog = HazardSourceCategoriesManagementDialog(self)
        dialog.exec()
        self._populate_category_filter(selected_code=selected_code)
        self.refresh()

    def open_template(self, template_id: int) -> None:
        self.refresh()
        for row_index in range(self.table.rowCount()):
            id_item = self.table.item(row_index, HAZARD_LIBRARY_COL_ID)
            if id_item is not None and int(id_item.text()) == template_id:
                self.table.selectRow(row_index)
                self.table.scrollToItem(id_item)
                self._refresh_action_buttons()
                break

    def open_template_editor(self, template_id: int) -> None:
        self.open_template(template_id)
        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_PAGE_TITLE,
                "Zdroj rizika nebyl nalezen.",
            )
            self.refresh()
            return
        dialog = HazardLibraryTemplateDialog(self, template=template)
        exec_maximized(dialog)
        self.refresh()

    def _selected_template_id(self) -> int | None:
        if self._selected_row_count() != 1:
            return None
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), HAZARD_LIBRARY_COL_ID)
        if id_item is None:
            return None
        return int(id_item.text())

    def _selected_template(self):
        template_id = self._selected_template_id()
        if template_id is None:
            return None
        return hazard_library_template_service.get_by_id(template_id)
