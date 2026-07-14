from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.utils.czech_sort import czech_sorted
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORY_LABELS,
    IDENTIFIED_HAZARD_DIALOG_TITLE,
    IDENTIFIED_HAZARD_SOURCE_TYPES,
    IDENTIFIED_HAZARD_SOURCE_LABELS,
    DEFAULT_IDENTIFIED_HAZARD_SOURCE,
)
from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
    IdentifiedHazardError,
    identified_hazard_service,
)


class IdentifiedHazardDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        hazard=None,
        default_inventory_item_id: int | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.hazard = hazard
        self.read_only = read_only

        self.setWindowTitle(IDENTIFIED_HAZARD_DIALOG_TITLE)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.inventory_item = QComboBox()
        self._populate_inventory_items(default_inventory_item_id)

        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(80)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)

        self.source_type = QComboBox()
        for source in IDENTIFIED_HAZARD_SOURCE_TYPES:
            self.source_type.addItem(IDENTIFIED_HAZARD_SOURCE_LABELS[source], source)

        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Položka inventury *:", self.inventory_item)
        form.addRow("Název nebezpečí *:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("Poznámka:", self.note)
        form.addRow("Původ:", self.source_type)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if hazard is not None:
            index = self.inventory_item.findData(hazard.inventory_item_id)
            if index >= 0:
                self.inventory_item.setCurrentIndex(index)
            self.name.setText(hazard.name)
            self.description.setPlainText(hazard.description or "")
            self.note.setPlainText(hazard.note or "")
            source_index = self.source_type.findData(hazard.source_type)
            if source_index >= 0:
                self.source_type.setCurrentIndex(source_index)
            self.active_checkbox.setChecked(bool(hazard.active))

        if read_only:
            self.inventory_item.setEnabled(False)
            self.name.setReadOnly(True)
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.source_type.setEnabled(False)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _populate_inventory_items(self, default_inventory_item_id: int | None) -> None:
        items = identified_hazard_service.get_inventory_item_candidates(
            self.hazard_identification_id
        )
        items = czech_sorted(items, key=lambda item: (item.category, item.name))
        self.inventory_item.clear()
        for item in items:
            category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(item.category, item.category)
            self.inventory_item.addItem(f"{category_label} — {item.name}", item.id)

        if default_inventory_item_id is not None:
            index = self.inventory_item.findData(default_inventory_item_id)
            if index >= 0:
                self.inventory_item.setCurrentIndex(index)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        try:
            if self.hazard is None:
                identified_hazard_service.create_hazard(
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
            else:
                identified_hazard_service.update_hazard(self.hazard.id, **data)
        except IdentifiedHazardError as error:
            QMessageBox.warning(self, IDENTIFIED_HAZARD_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "inventory_item_id": self.inventory_item.currentData(),
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "source_type": self.source_type.currentData() or DEFAULT_IDENTIFIED_HAZARD_SOURCE,
            "active": self.active_checkbox.isChecked(),
        }
