from datetime import date, datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.pravni_pozadavky.constants import (
    CHECK_RUN_STATUS_LABELS,
    DEFAULT_CHECK_RUN_STATUS,
    VALID_CHECK_RUN_STATUSES,
)
from moduly.pravni_pozadavky.ui.legal_check_run_changes_tab import LegalCheckRunChangesTab


class LegalCheckRunDialog(QDialog):
    def __init__(self, parent=None, run=None):
        super().__init__(parent)
        self.run = run

        self.setWindowTitle("Kontrola legislativy" if run is None else "Upravit kontrolu")
        configure_resizable_form_dialog(self, width=760, height=680, min_width=560, min_height=480)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), "Kontrola")
        if run is None:
            changes_tab = QWidget()
            changes_layout = QVBoxLayout(changes_tab)
            changes_layout.addWidget(QLabel("Změny budou dostupné až po uložení kontroly."))
            self.tabs.addTab(wrap_in_scroll_area(changes_tab), "Změny")
        else:
            self.changes_tab = LegalCheckRunChangesTab(run_id=run.id)
            self.tabs.addTab(wrap_in_scroll_area(self.changes_tab), "Změny")
        layout.addWidget(self.tabs, 1)
        add_save_cancel_footer(layout, self)

        if run is not None:
            self._load_run(run)

    def _main_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.title = QLineEdit()
        self.period_from = NullableDateEdit()
        self.period_to = NullableDateEdit()
        self.checked_at = NullableDateEdit()
        self.checked_by = QLineEdit()
        self.status = QComboBox()
        for key in sorted(CHECK_RUN_STATUS_LABELS, key=lambda item: CHECK_RUN_STATUS_LABELS[item]):
            self.status.addItem(CHECK_RUN_STATUS_LABELS[key], key)
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Název:", self.title)
        form.addRow("Období od:", self.period_from)
        form.addRow("Období do:", self.period_to)
        form.addRow("Datum kontroly:", self.checked_at)
        form.addRow("Kontroloval:", self.checked_by)
        form.addRow("Stav:", self.status)
        form.addRow("Poznámka:", self.note)
        return tab

    def _load_run(self, run) -> None:
        self.title.setText(run.title)
        self.period_from.set_date_value(run.period_from)
        self.period_to.set_date_value(run.period_to)
        if run.checked_at is not None:
            self.checked_at.set_date_value(run.checked_at.date())
        self.checked_by.setText(run.checked_by)
        self._set_combo_value(self.status, run.status)
        self.note.setPlainText(run.note)

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def get_data(self) -> dict:
        checked_date = self.checked_at.get_date()
        checked_at = None
        if checked_date is not None:
            checked_at = datetime.combine(checked_date, datetime.min.time())
        status = self.status.currentData() or DEFAULT_CHECK_RUN_STATUS
        if status not in VALID_CHECK_RUN_STATUSES:
            status = DEFAULT_CHECK_RUN_STATUS

        return {
            "title": self.title.text().strip(),
            "period_from": self.period_from.get_date(),
            "period_to": self.period_to.get_date(),
            "checked_at": checked_at,
            "checked_by": self.checked_by.text().strip(),
            "status": status,
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, "Kontrola legislativy", "Název je povinný.")
            return
        if data["period_from"] is None:
            QMessageBox.warning(self, "Kontrola legislativy", "Období od je povinné.")
            return
        if data["period_to"] is None:
            QMessageBox.warning(self, "Kontrola legislativy", "Období do je povinné.")
            return
        super().accept()
