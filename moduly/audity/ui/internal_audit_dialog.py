from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.date_edit import DateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.audity.constants import DEFAULT_AUDIT_STATUS, VALID_AUDIT_STATUSES


class InternalAuditDialog(QDialog):
    def __init__(self, parent=None, audit=None):
        super().__init__(parent)

        self.audit = audit

        self.setWindowTitle("Interní audit IMS")
        self.resize(640, 360)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._basic_tab(), "Základní údaje")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if audit is not None:
            self.number_label.setText(audit.number or "—")
            if audit.audit_date:
                self.audit_date_edit.set_date_iso(audit.audit_date.isoformat())
            self.title_edit.setText(audit.title or "")
            self.status_combo.setCurrentText(audit.status or DEFAULT_AUDIT_STATUS)
            self._set_workplace(audit.workplace or "")

    def _basic_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.number_label = QLabel("—")
        self.audit_date_edit = DateEdit()
        self.workplace_selector = WorkplaceSelector()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název nebo kód auditu")

        self.status_combo = QComboBox()
        self.status_combo.addItems(sorted(VALID_AUDIT_STATUSES))

        form.addRow("Číslo:", self.number_label)
        form.addRow("Datum auditu:", self.audit_date_edit)
        form.addRow("Pracoviště:", self.workplace_selector)
        form.addRow("Název:", self.title_edit)
        form.addRow("Stav:", self.status_combo)

        return tab

    def _set_workplace(self, workplace_name: str) -> None:
        index = self.workplace_selector.findText(workplace_name)
        if index >= 0:
            self.workplace_selector.setCurrentIndex(index)
        elif self.workplace_selector.include_empty:
            self.workplace_selector.setCurrentIndex(0)

    def get_data(self) -> dict:
        qdate = self.audit_date_edit.date()
        audit_date = date(qdate.year(), qdate.month(), qdate.day())

        return {
            "title": self.title_edit.text().strip(),
            "audit_date": audit_date,
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "status": self.status_combo.currentText(),
        }
