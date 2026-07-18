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
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
    HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL,
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
        self.result: HazardLibraryTemplateApplyResult | IdApplyResult | None = None

        self.setWindowTitle(HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE)
        self.resize(720, 520)

        layout = QVBoxLayout(self)

        category_row = QHBoxLayout()
        category_row.addWidget(QLabel(HAZARD_LIBRARY_APPLY_CATEGORY_FILTER_LABEL))
        self.category_filter = QComboBox()
        self.category_filter.addItem(HAZARD_LIBRARY_APPLY_ALL_CATEGORIES, None)
        for category in HAZARD_INVENTORY_CATEGORIES:
            self.category_filter.addItem(
                HAZARD_INVENTORY_CATEGORY_LABELS.get(category, category),
                category,
            )
        self.category_filter.setCurrentIndex(0)
        self.category_filter.currentIndexChanged.connect(self._reload_sources)
        category_row.addWidget(self.category_filter, stretch=1)
        layout.addLayout(category_row)

        self.shown_count_label = QLabel(
            HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=0, total=0),
        )
        layout.addWidget(self.shown_count_label)

        layout.addWidget(QLabel(HAZARD_LIBRARY_CATALOG_SOURCES_TITLE))
        self.sources_list = QListWidget()
        self.sources_list.setMinimumHeight(280)
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
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Převzít")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.sources_list.itemDoubleClicked.connect(lambda _: self.accept())
        self._reload_sources()

    def _selected_category(self) -> str | None:
        return self.category_filter.currentData()

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
        available = list(groups.recommended) + list(groups.other)
        total = len(available)

        selected_category = self._selected_category()
        if selected_category is None:
            templates = available
        else:
            templates = [
                template
                for template in available
                if template.category == selected_category
            ]

        self._populate_list(self.sources_list, templates)
        self.shown_count_label.setText(
            HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(
                shown=len(templates),
                total=total,
            ),
        )

    def _populate_list(self, list_widget: QListWidget, templates) -> None:
        list_widget.clear()
        for template in templates:
            category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(
                template.category,
                template.category,
            )
            item = QListWidgetItem(f"{template.name} ({category_label})")
            item.setData(Qt.ItemDataRole.UserRole, template.id)
            item.setToolTip(template.name)
            list_widget.addItem(item)

    def _selected_template_id(self) -> int | None:
        selected = self.sources_list.selectedItems()
        if selected:
            return selected[0].data(Qt.ItemDataRole.UserRole)
        return None

    def accept(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
                "Vyberte zdroj rizika z katalogu.",
            )
            return

        try:
            store = find_identification_working_copy(self)
            if store is not None:
                self.result = store.apply_from_template(
                    template_id,
                    include_inactive=self.include_inactive.isChecked(),
                )
            else:
                self.result = hazard_library_template_apply_service.apply_template(
                    hazard_identification_id=self.hazard_identification_id,
                    template_id=template_id,
                    include_inactive=self.include_inactive.isChecked(),
                )
        except HazardLibraryTemplateApplyError as error:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
                str(error),
            )
            return
        super().accept()
