from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.audity.constants import (
    AUDIT_STATUS_DOKONCEN,
    AUDIT_STATUS_PLANOVANY,
    AUDIT_STATUS_PROBIHA,
    DEFAULT_AUDIT_STATUS,
)
from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
from moduly.audity.ui.audit_participants_tab import AuditParticipantsTab


class InternalAuditDialog(QDialog):
    def __init__(self, parent=None, audit=None):
        super().__init__(parent)

        self.audit = audit

        self.setWindowTitle("Interní audit IMS")
        self.resize(860, 640)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._basic_tab(), "Základní údaje")
        self.participants_tab = AuditParticipantsTab()
        self.findings_widget = AuditFindingsWidget()
        self.tabs.addTab(self.participants_tab, "Účastníci")
        self.tabs.addTab(self.findings_widget, "Zjištění")
        self.tabs.addTab(self._summary_tab(), "Shrnutí")
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        audit_id = audit.id if audit is not None else None
        self.participants_tab.set_audit_id(audit_id)
        self.findings_widget.set_audit_id(audit_id)

        if audit is not None:
            self.number_label.setText(audit.number or "—")
            self.audit_date_edit.set_date_value(audit.audit_date)
            self._set_planned_period(audit.planned_year, audit.planned_month)
            self.title_edit.setText(audit.title or "")
            self.status_combo.setCurrentText(audit.status or DEFAULT_AUDIT_STATUS)
            self._set_workplace(audit.workplace or "")
            self.summary_edit.setPlainText(audit.summary or "")

    def _basic_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.number_label = QLabel("—")

        planned_row = QHBoxLayout()
        self.planned_year_combo = QComboBox()
        self.planned_month_combo = QComboBox()
        self._populate_planned_combos()
        planned_row.addWidget(self.planned_year_combo)
        planned_row.addWidget(self.planned_month_combo)
        planned_row.addStretch()

        self.audit_date_edit = NullableDateEdit()
        self.workplace_selector = WorkplaceSelector()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název nebo kód auditu")

        self.status_combo = QComboBox()
        self.status_combo.addItems([
            AUDIT_STATUS_PLANOVANY,
            AUDIT_STATUS_PROBIHA,
            AUDIT_STATUS_DOKONCEN,
        ])

        form.addRow("Číslo:", self.number_label)
        form.addRow("Plán (měsíc/rok):", planned_row)
        form.addRow("Datum auditu:", self.audit_date_edit)
        form.addRow("Pracoviště:", self.workplace_selector)
        form.addRow("Název:", self.title_edit)
        form.addRow("Stav:", self.status_combo)

        return tab

    def _summary_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.summary_edit = QTextEdit()
        self.summary_edit.setPlaceholderText("Celkové shrnutí auditu")
        self.summary_edit.setMinimumHeight(220)

        layout.addWidget(self.summary_edit)
        return tab

    def _populate_planned_combos(self) -> None:
        current_year = date.today().year
        self.planned_year_combo.clear()
        for year in range(current_year - 2, current_year + 4):
            self.planned_year_combo.addItem(str(year), year)
        self.planned_year_combo.setCurrentText(str(current_year))

        self.planned_month_combo.clear()
        for month in range(1, 13):
            self.planned_month_combo.addItem(f"{month:02d}", month)
        self.planned_month_combo.setCurrentIndex(date.today().month - 1)

    def _set_planned_period(self, planned_year: int | None, planned_month: int | None) -> None:
        if planned_year is not None:
            index = self.planned_year_combo.findData(planned_year)
            if index >= 0:
                self.planned_year_combo.setCurrentIndex(index)
        if planned_month is not None:
            index = self.planned_month_combo.findData(planned_month)
            if index >= 0:
                self.planned_month_combo.setCurrentIndex(index)

    def _set_workplace(self, workplace_name: str) -> None:
        index = self.workplace_selector.findText(workplace_name)
        if index >= 0:
            self.workplace_selector.setCurrentIndex(index)
        elif self.workplace_selector.include_empty:
            self.workplace_selector.setCurrentIndex(0)

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "planned_year": self.planned_year_combo.currentData(),
            "planned_month": self.planned_month_combo.currentData(),
            "audit_date": self.audit_date_edit.get_date(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "status": self.status_combo.currentText(),
            "summary": self.summary_edit.toPlainText().strip(),
        }
