from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
    HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL,
    HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE,
    HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE,
    HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
    HAZARD_LIBRARY_CATALOG_SOURCES_TITLE,
)
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    IdApplyResult,
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
    HazardLibraryTemplateApplyError,
    HazardLibraryTemplateApplyResult,
    hazard_library_template_apply_service,
)
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    hazard_source_category_service,
)

_ApplyResult = HazardLibraryTemplateApplyResult | IdApplyResult


class HazardLibraryApplyToInventoryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        default_category: str | None = None,
        inventory_items: list[HazardInventoryItem] | None = None,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        # Zachováno kvůli volajícím; výchozí filtr je vždy „Všechny kategorie“.
        self.default_category = default_category
        store = find_identification_working_copy(self)
        if store is not None:
            self._inventory_items = store.get_items(include_inactive=True)
        else:
            self._inventory_items = inventory_items
        self.results: list[_ApplyResult] = []
        self.result: _ApplyResult | None = None
        self._checked_template_ids: list[int] = []
        self._available_templates = []

        self.setWindowTitle(HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE)
        self.resize(720, 520)

        layout = QVBoxLayout(self)

        category_row = QHBoxLayout()
        category_row.addWidget(QLabel(HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL))
        self.category_filter = QComboBox()
        self.category_filter.addItem(HAZARD_LIBRARY_APPLY_ALL_CATEGORIES, None)
        for category in hazard_source_category_service.get_all(include_inactive=True):
            self.category_filter.addItem(category.name, category.code)
        self.category_filter.setCurrentIndex(0)
        self.category_filter.currentIndexChanged.connect(self._reload_sources)
        category_row.addWidget(self.category_filter, stretch=1)
        layout.addLayout(category_row)

        counts_row = QHBoxLayout()
        self.shown_count_label = QLabel(
            HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=0, total=0),
        )
        self.selected_count_label = QLabel(
            HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE.format(selected=0),
        )
        counts_row.addWidget(self.shown_count_label)
        counts_row.addSpacing(16)
        counts_row.addWidget(self.selected_count_label)
        counts_row.addStretch()
        layout.addLayout(counts_row)

        layout.addWidget(QLabel(HAZARD_LIBRARY_CATALOG_SOURCES_TITLE))
        self.sources_list = QListWidget()
        self.sources_list.setMinimumHeight(280)
        self.sources_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.sources_list)

        # Zpětná kompatibilita pro starší testy / volání.
        self.recommended_list = self.sources_list
        self.other_list = QListWidget()
        self.other_list.hide()

        self.include_inactive = QCheckBox("Zahrnout neaktivní záznamy")
        self.include_inactive.setChecked(False)
        self.include_inactive.toggled.connect(self._reload_sources)
        layout.addWidget(self.include_inactive)

        buttons = create_save_cancel_box(self)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.apply_button.setText("Převzít")
        self.apply_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload_sources()

    def _selected_category(self) -> str | None:
        return self.category_filter.currentData()

    def selected_template_ids(self) -> list[int]:
        """Označené zdroje, které jsou stále dostupné k převzetí."""
        available_ids = {template.id for template in self._available_templates}
        return [
            template_id
            for template_id in self._checked_template_ids
            if template_id in available_ids
        ]

    def _reload_sources(self) -> None:
        """Při otevření / změně filtru načte aktuální katalog z DB."""
        store = find_identification_working_copy(self)
        if store is not None:
            self._inventory_items = store.get_items(include_inactive=True)

        groups = hazard_library_template_apply_service.get_template_groups(
            operation_id=None,
            category=None,
            hazard_identification_id=self.hazard_identification_id,
            include_inactive=self.include_inactive.isChecked(),
            inventory_items=self._inventory_items,
        )
        self._available_templates = list(groups.recommended) + list(groups.other)
        total = len(self._available_templates)

        selected_category = self._selected_category()
        if selected_category is None:
            templates = self._available_templates
        else:
            templates = [
                template
                for template in self._available_templates
                if template.category == selected_category
            ]

        self._populate_list(self.sources_list, templates)
        self.shown_count_label.setText(
            HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(
                shown=len(templates),
                total=total,
            ),
        )
        self._update_selection_ui()

    def _populate_list(self, list_widget: QListWidget, templates) -> None:
        checked_ids = set(self._checked_template_ids)
        list_widget.blockSignals(True)
        list_widget.clear()
        for template in templates:
            category_label = hazard_source_category_service.label_for(template.category)
            item = QListWidgetItem(f"{template.name} ({category_label})")
            item.setData(Qt.ItemDataRole.UserRole, template.id)
            item.setToolTip(template.name)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if template.id in checked_ids
                else Qt.CheckState.Unchecked
            )
            list_widget.addItem(item)
        list_widget.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        template_id = item.data(Qt.ItemDataRole.UserRole)
        if template_id is None:
            return
        self._set_template_checked(
            template_id,
            item.checkState() == Qt.CheckState.Checked,
        )
        self._update_selection_ui()

    def _set_template_checked(self, template_id: int, checked: bool) -> None:
        if checked:
            if template_id not in self._checked_template_ids:
                self._checked_template_ids.append(template_id)
            return
        if template_id in self._checked_template_ids:
            self._checked_template_ids.remove(template_id)

    def _update_selection_ui(self) -> None:
        selected = len(self.selected_template_ids())
        self.selected_count_label.setText(
            HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE.format(selected=selected),
        )
        self.apply_button.setEnabled(selected > 0)

    def _apply_one(self, template_id: int) -> _ApplyResult:
        store = find_identification_working_copy(self)
        if store is not None:
            return store.apply_from_template(
                template_id,
                include_inactive=self.include_inactive.isChecked(),
            )
        return hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.hazard_identification_id,
            template_id=template_id,
            include_inactive=self.include_inactive.isChecked(),
        )

    def accept(self) -> None:
        template_ids = self.selected_template_ids()
        if not template_ids:
            return

        results: list[_ApplyResult] = []
        applied_ids: list[int] = []
        try:
            for template_id in template_ids:
                results.append(self._apply_one(template_id))
                applied_ids.append(template_id)
        except HazardLibraryTemplateApplyError as error:
            for template_id in applied_ids:
                self._set_template_checked(template_id, False)
            self._reload_sources()
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
                str(error),
            )
            return

        self.results = results
        self.result = results[-1]
        super().accept()
