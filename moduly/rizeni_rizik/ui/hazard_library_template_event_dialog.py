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
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_EVENT_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    HazardLibraryTemplateEventError,
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_item_service import (
    hazard_library_template_item_service,
)


class HazardLibraryTemplateEventDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        event=None,
        default_template_item_id: int | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.template_id = template_id
        self.event = event
        self.read_only = read_only

        self.setWindowTitle(HAZARD_LIBRARY_EVENT_DIALOG_TITLE)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.template_item = QComboBox()
        self._populate_template_items(default_template_item_id)

        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(80)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Položka vzoru *:", self.template_item)
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
            index = self.template_item.findData(event.template_item_id)
            if index >= 0:
                self.template_item.setCurrentIndex(index)
            self.name.setText(event.name)
            self.description.setPlainText(event.description or "")
            self.note.setPlainText(event.note or "")
            self.active_checkbox.setChecked(bool(event.active))

        if read_only:
            self.template_item.setEnabled(False)
            self.name.setReadOnly(True)
            self.description.setReadOnly(True)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _populate_template_items(self, default_template_item_id: int | None) -> None:
        self.template_item.clear()
        for item in hazard_library_template_item_service.get_for_template(
            self.template_id,
            include_inactive=False,
        ):
            self.template_item.addItem(item.name, item.id)
        if default_template_item_id is not None:
            index = self.template_item.findData(default_template_item_id)
            if index >= 0:
                self.template_item.setCurrentIndex(index)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        data = self.get_data()
        template_item_id = self.template_item.currentData()
        if template_item_id is None:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
                "Vyberte položku vzoru.",
            )
            return

        try:
            if self.event is None:
                hazard_library_template_event_service.create_event(
                    template_id=self.template_id,
                    template_item_id=template_item_id,
                    **data,
                )
            else:
                hazard_library_template_event_service.update_event(
                    self.event.id,
                    template_id=self.template_id,
                    template_item_id=template_item_id,
                    **data,
                )
        except HazardLibraryTemplateEventError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_EVENT_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
