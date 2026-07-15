from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_LABELS
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
    HAZARD_LIBRARY_OTHER_SOURCES_TITLE,
    HAZARD_LIBRARY_RECOMMENDED_SOURCES_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
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
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.default_category = default_category
        self.result: HazardLibraryTemplateApplyResult | None = None

        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        operation_id = identification.operation_id if identification is not None else None

        self.setWindowTitle(HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE)
        self.resize(720, 560)

        layout = QVBoxLayout(self)

        if default_category is not None:
            category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(
                default_category,
                default_category,
            )
            intro = QLabel(
                f"Kategorie: {category_label}. Vyberte zdroj rizika z katalogu."
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)

        layout.addWidget(QLabel(HAZARD_LIBRARY_RECOMMENDED_SOURCES_TITLE))
        self.recommended_list = QListWidget()
        self.recommended_list.setMinimumHeight(180)
        layout.addWidget(self.recommended_list)

        layout.addWidget(QLabel(HAZARD_LIBRARY_OTHER_SOURCES_TITLE))
        self.other_list = QListWidget()
        self.other_list.setMinimumHeight(180)
        layout.addWidget(self.other_list)

        self.include_inactive = QCheckBox("Zahrnout neaktivní záznamy")
        self.include_inactive.setChecked(False)
        layout.addWidget(self.include_inactive)

        buttons = create_save_cancel_box(self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Převzít")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        groups = hazard_library_template_apply_service.get_template_groups(
            operation_id=operation_id,
            category=default_category,
        )
        self._populate_list(self.recommended_list, groups.recommended)
        self._populate_list(self.other_list, groups.other)

        self.recommended_list.itemSelectionChanged.connect(self._clear_other_selection)
        self.other_list.itemSelectionChanged.connect(self._clear_recommended_selection)
        self.recommended_list.itemDoubleClicked.connect(lambda _: self.accept())
        self.other_list.itemDoubleClicked.connect(lambda _: self.accept())

        if not groups.recommended and not groups.other:
            QMessageBox.information(
                self,
                HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE,
                "V katalogu nejsou k dispozici žádné zdroje rizika pro tuto kategorii.",
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
            list_widget.addItem(item)

    def _clear_other_selection(self) -> None:
        if self.recommended_list.selectedItems():
            self.other_list.blockSignals(True)
            self.other_list.clearSelection()
            self.other_list.blockSignals(False)

    def _clear_recommended_selection(self) -> None:
        if self.other_list.selectedItems():
            self.recommended_list.blockSignals(True)
            self.recommended_list.clearSelection()
            self.recommended_list.blockSignals(False)

    def _selected_template_id(self) -> int | None:
        for list_widget in (self.recommended_list, self.other_list):
            selected = list_widget.selectedItems()
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
