from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    INVENTORY_ITEM_DIALOG_TITLE,
    format_inventory_item_source_label,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    HazardInventoryItemError,
    hazard_inventory_item_service,
)


class HazardInventoryItemDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        item=None,
        default_category: str | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.item = item
        self.read_only = read_only

        self.setWindowTitle(INVENTORY_ITEM_DIALOG_TITLE)
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category = QComboBox()
        for category in HAZARD_INVENTORY_CATEGORIES:
            self.category.addItem(HAZARD_INVENTORY_CATEGORY_LABELS[category], category)

        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(100)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)
        self.source_label = QLabel()
        self.source_label.setWordWrap(True)

        form.addRow("Kategorie *:", self.category)
        form.addRow("Název *:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)
        layout.addWidget(self.source_label)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if item is not None:
            index = self.category.findData(item.category)
            if index >= 0:
                self.category.setCurrentIndex(index)
            self.name.setText(item.name)
            self.description.setPlainText(item.description or "")
            self.active_checkbox.setChecked(bool(item.active))
            source_text = format_inventory_item_source_label(
                source_template_id=item.source_template_id,
                source_template_version=item.source_template_version,
            )
            if source_text:
                self.source_label.setText(f"Původ: {source_text}")
        elif default_category is not None:
            index = self.category.findData(default_category)
            if index >= 0:
                self.category.setCurrentIndex(index)

        if read_only:
            self.category.setEnabled(False)
            self.name.setReadOnly(True)
            self.description.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        try:
            if self.item is None:
                hazard_inventory_item_service.create_item(
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
            else:
                hazard_inventory_item_service.update_item(self.item.id, **data)
        except HazardInventoryItemError as error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, INVENTORY_ITEM_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "category": self.category.currentData(),
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
