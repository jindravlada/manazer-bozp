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

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    HAZARD_EVENT_DIALOG_TITLE,
    HAZARD_INVENTORY_CATEGORY_LABELS,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventError,
    hazard_event_service,
)


class HazardEventDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        event=None,
        default_inventory_item_id: int | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.hazard_event = event
        self.read_only = read_only

        self.setWindowTitle(HAZARD_EVENT_DIALOG_TITLE)
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
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Zdroj analýzy *:", self.inventory_item)
        form.addRow("Název události *:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if event is not None:
            index = self.inventory_item.findData(event.inventory_item_id)
            if index >= 0:
                self.inventory_item.setCurrentIndex(index)
            self.name.setText(event.name)
            self.description.setPlainText(event.description or "")
            self.note.setPlainText(event.note or "")
            self.active_checkbox.setChecked(bool(event.active))

        if read_only:
            self.inventory_item.setEnabled(False)
            self.name.setReadOnly(True)
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _populate_inventory_items(self, default_inventory_item_id: int | None) -> None:
        items = hazard_event_service.get_inventory_item_candidates(
            self.hazard_identification_id
        )
        self.inventory_item.clear()
        for item in items:
            category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(
                item.category,
                item.category,
            )
            label = f"{item.name} ({category_label})"
            self.inventory_item.addItem(label, item.id)

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
            if self.hazard_event is None:
                hazard_event_service.create_event(
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
            else:
                hazard_event_service.update_event(
                    self.hazard_event.id,
                    hazard_identification_id=self.hazard_identification_id,
                    **data,
                )
        except HazardEventError as error:
            QMessageBox.warning(self, HAZARD_EVENT_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "inventory_item_id": self.inventory_item.currentData(),
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
