from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.workplace_selector import WorkplaceSelector


class ControlDialog(QDialog):
    DEFECT_OPTIONS = ["NE", "ANO"]
    LEGACY_DEFECT_MAP = {
        "Bez závad": "NE",
        "Se závadami": "ANO",
        "Neprovedena": "NE",
    }

    def __init__(self, parent=None, control=None):
        super().__init__(parent)

        self.control = control

        self.setWindowTitle("Evidence kontroly ze SD portálu")
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.inspection_date_edit = DateEdit()

        self.inspector_selector = ThpWorkerSelector()
        self.workplace_selector = WorkplaceSelector()

        self.checklist_edit = QLineEdit()
        self.checklist_edit.setPlaceholderText("Název kontrolního listu")

        self.defect_combo = QComboBox()
        self.defect_combo.addItems(self.DEFECT_OPTIONS)
        self.defect_combo.setCurrentText("NE")

        self.sd_reference_edit = QLineEdit()
        self.sd_reference_edit.setPlaceholderText("Volitelné číslo nebo odkaz na záznam v SD portálu")

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Stručná poznámka ke kontrole.")
        self.note_edit.setMinimumHeight(100)

        form.addRow("Datum kontroly:", self.inspection_date_edit)
        form.addRow("THP pracovník:", self.inspector_selector)
        form.addRow("Pracoviště:", self.workplace_selector)
        form.addRow("Kontrolní list:", self.checklist_edit)
        form.addRow("Závada:", self.defect_combo)
        form.addRow("Odkaz / číslo SD:", self.sd_reference_edit)
        form.addRow("Stručná poznámka:", self.note_edit)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if control is not None:
            if control.inspection_date:
                self.inspection_date_edit.set_date_iso(control.inspection_date.isoformat())
            self.inspector_selector.set_person_id(control.inspector_id)
            self.workplace_selector.set_workplace_id(control.workplace_id)
            self.checklist_edit.setText(control.title or "")
            self.defect_combo.setCurrentText(self._defect_display(control.result))
            self.sd_reference_edit.setText(control.sd_reference or "")
            self.note_edit.setPlainText(control.note or "")

    def _defect_display(self, result: str) -> str:
        if result in self.DEFECT_OPTIONS:
            return result
        return self.LEGACY_DEFECT_MAP.get(result or "", "NE")

    def get_data(self) -> dict:
        qdate = self.inspection_date_edit.date()
        inspection_date = date(qdate.year(), qdate.month(), qdate.day())

        return {
            "title": self.checklist_edit.text().strip(),
            "inspection_date": inspection_date,
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "inspector_id": self.inspector_selector.current_person_id(),
            "result": self.defect_combo.currentText(),
            "note": self.note_edit.toPlainText().strip(),
            "sd_reference": self.sd_reference_edit.text().strip(),
        }
