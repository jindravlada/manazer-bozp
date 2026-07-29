from datetime import date, timedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QVBoxLayout

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box


class LegalCheckFirstRunDialog(QDialog):
    """Dialog pro zadání počátečního data první kontroly legislativy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("První kontrola legislativy")
        configure_resizable_form_dialog(self, width=420, height=180, min_width=360, min_height=160)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.period_from = DateEdit()
        default_from = date.today() - timedelta(days=30)
        self.period_from.setDate(QDate(default_from.year, default_from.month, default_from.day))
        form.addRow("Sledovat změny od:", self.period_from)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setText("Zkontrolovat")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_period_from(self) -> date:
        qdate = self.period_from.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def accept(self) -> None:
        period_from = self.get_period_from()
        if period_from > date.today():
            QMessageBox.warning(
                self,
                "První kontrola legislativy",
                "Datum začátku kontroly nesmí být v budoucnosti.",
            )
            return
        super().accept()
