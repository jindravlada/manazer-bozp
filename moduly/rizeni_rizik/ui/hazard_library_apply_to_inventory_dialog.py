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
    HAZARD_LIBRARY_CATALOG_SOURCES_TITLE,
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

        self.setWindowTitle(HAZARD_LIBRARY_APPLY_TO_INVENTORY_DIALOG_TITLE)
        self.resize(720, 520)

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
        layout.addWidget(self.include_inactive)

        buttons = create_save_cancel_box(self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Převzít")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        groups = hazard_library_template_apply_service.get_template_groups(
            operation_id=None,
            category=default_category,
        )
        templates = list(groups.recommended) + list(groups.other)
        self._populate_list(self.sources_list, templates)
        self.sources_list.itemDoubleClicked.connect(lambda _: self.accept())

        if not templates:
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
