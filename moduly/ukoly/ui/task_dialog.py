from datetime import date, timedelta

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.date_edit import DateEdit
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.person_selector import PersonSelector
from core.widgets.workplace_selector import WorkplaceSelector


class TaskDialog(QDialog):
    def __init__(self, parent=None, task=None):
        super().__init__(parent)

        self.task = task

        self.setWindowTitle("Nápravné opatření")
        self.resize(760, 680)

        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._main_tab(), "Opatření")
        self.tabs.addTab(self._attachments_tab(), "Přílohy")

        main_layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        main_layout.addWidget(buttons)

        self.completed_checkbox.stateChanged.connect(self._completed_changed)
        self.requires_verification_checkbox.stateChanged.connect(self._verification_changed)
        self.canceled_checkbox.stateChanged.connect(self._refresh_status)
        self.checked_date_edit.dateChanged.connect(self._refresh_status)
        self.checked_by_selector.currentIndexChanged.connect(self._refresh_status)

        if task is not None:
            self.title_edit.setPlainText(task.title)
            self.priority_combo.setCurrentText(task.priority)
            if task.due_date:
                self.due_date_edit.set_date_iso(task.due_date.isoformat())
            self.person_selector.set_person_id(task.responsible_person_id)
            self.workplace_selector.set_workplace_id(task.workplace_id)

            self.completed_checkbox.setChecked(task.completed)
            self.completed_date_edit.set_date_value(task.completed_date)
            self.requires_verification_checkbox.setChecked(task.requires_verification)
            self.check_due_date_edit.set_date_value(task.check_due_date)
            self.checked_date_edit.set_date_value(task.checked_date)
            self.checked_by_selector.set_person_id(task.checked_by_id)
            self.canceled_checkbox.setChecked(task.canceled)
            self.note_edit.setPlainText(task.note)

        self._verification_changed()
        self._refresh_status()

    def _main_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.title_edit = QTextEdit()
        self.title_edit.setPlaceholderText("Popište stanovené opatření / úkol.")
        self.title_edit.setFixedHeight(95)

        self.person_selector = PersonSelector()

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Nízká", "Normální", "Vysoká", "Kritická"])
        self.priority_combo.setCurrentText("Normální")

        self.due_date_edit = DateEdit()

        self.completed_checkbox = QCheckBox("Opatření splněno")
        self.completed_date_edit = NullableDateEdit()

        self.workplace_selector = WorkplaceSelector()

        self.requires_verification_checkbox = QCheckBox("Vyžaduje kontrolu účinnosti opatření")

        self.check_due_date_edit = NullableDateEdit()
        self.checked_date_edit = NullableDateEdit()
        self.checked_by_selector = PersonSelector()

        self.canceled_checkbox = QCheckBox("Opatření zrušeno / netrvá")

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Poznámka, zjištěné závady nebo výsledek kontroly.")

        self.status_label = QLabel("Aktivní")

        layout.addRow("Opatření:", self.title_edit)
        layout.addRow("Odpovídá:", self.person_selector)
        layout.addRow("Priorita:", self.priority_combo)
        layout.addRow("Termín splnění:", self.due_date_edit)
        layout.addRow("Splnění:", self.completed_checkbox)
        layout.addRow("Splněno dne:", self.completed_date_edit)
        layout.addRow("Pracoviště:", self.workplace_selector)
        layout.addRow("Kontrolovat:", self.requires_verification_checkbox)
        layout.addRow("Kontrola do:", self.check_due_date_edit)
        layout.addRow("Datum kontroly:", self.checked_date_edit)
        layout.addRow("Kontroloval:", self.checked_by_selector)
        layout.addRow("Zrušeno:", self.canceled_checkbox)
        layout.addRow("Stav:", self.status_label)
        layout.addRow("Poznámka / zjištěné závady:", self.note_edit)

        return tab

    def _attachments_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        entity_id = self.task.id if self.task is not None else None
        self.attachment_widget = AttachmentWidget("task", entity_id)

        if entity_id is None:
            info = QLabel("Přílohy lze přidat až po prvním uložení opatření.")
            layout.addWidget(info)

        layout.addWidget(self.attachment_widget)
        return tab

    def _completed_changed(self):
        if self.completed_checkbox.isChecked():
            if not self.completed_date_edit.has_date():
                today = date.today()
                self.completed_date_edit.set_date_value(today)

            if self.requires_verification_checkbox.isChecked() and not self.check_due_date_edit.has_date():
                completed_date = self.completed_date_edit.get_date() or date.today()
                self.check_due_date_edit.set_date_value(completed_date + timedelta(days=15))
        else:
            self.completed_date_edit.clear_date()
            self.check_due_date_edit.clear_date()
            self.checked_date_edit.clear_date()
            self.checked_by_selector.set_person_id(None)

        self._refresh_status()

    def _verification_changed(self):
        enabled = self.requires_verification_checkbox.isChecked()

        self.check_due_date_edit.setEnabled(enabled)
        self.checked_date_edit.setEnabled(enabled)
        self.checked_by_selector.setEnabled(enabled)

        if not enabled:
            self.check_due_date_edit.clear_date()
            self.checked_date_edit.clear_date()
            self.checked_by_selector.set_person_id(None)
        elif self.completed_checkbox.isChecked() and not self.check_due_date_edit.has_date():
            completed_date = self.completed_date_edit.get_date() or date.today()
            self.check_due_date_edit.set_date_value(completed_date + timedelta(days=15))

        self._refresh_status()

    def _refresh_status(self):
        if self.canceled_checkbox.isChecked():
            self.status_label.setText("Zrušeno")
        elif self.completed_checkbox.isChecked():
            if not self.requires_verification_checkbox.isChecked():
                self.status_label.setText("Ukončeno")
            elif self.checked_date_edit.has_date():
                self.status_label.setText("Ukončeno")
            else:
                self.status_label.setText("Splněno - čeká na kontrolu")
        else:
            self.status_label.setText("Aktivní")

    def get_data(self) -> dict:
        qdate = self.due_date_edit.date()
        due_date = date(qdate.year(), qdate.month(), qdate.day())

        requires_verification = self.requires_verification_checkbox.isChecked()

        return {
            "title": self.title_edit.toPlainText().strip(),
            "description": "",
            "priority": self.priority_combo.currentText(),
            "due_date": due_date,
            "responsible_person_id": self.person_selector.current_person_id(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "completed": self.completed_checkbox.isChecked(),
            "completed_date": self.completed_date_edit.get_date() if self.completed_checkbox.isChecked() else None,
            "requires_verification": requires_verification,
            "check_due_date": self.check_due_date_edit.get_date() if requires_verification else None,
            "checked_date": self.checked_date_edit.get_date() if requires_verification else None,
            "checked_by_id": self.checked_by_selector.current_person_id() if requires_verification else None,
            "canceled": self.canceled_checkbox.isChecked(),
            "note": self.note_edit.toPlainText().strip(),
        }
