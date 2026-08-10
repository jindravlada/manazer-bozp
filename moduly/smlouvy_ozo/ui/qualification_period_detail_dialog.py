"""Read-only detail historické verze ostatního osvědčení."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import configure_resizable_form_dialog, wrap_in_scroll_area
from moduly.smlouvy_ozo.constants import (
    DIALOG_TITLE_CERTIFICATE_PERIOD,
    ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
    UNIT_LABELS,
    format_date,
)


class QualificationPeriodDetailDialog(QDialog):
    def __init__(self, parent=None, *, period, certificate_name: str = ""):
        super().__init__(parent)
        self.period = period
        self.setWindowTitle(DIALOG_TITLE_CERTIFICATE_PERIOD)
        configure_resizable_form_dialog(
            self, width=560, height=500, min_width=420, min_height=360
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)
        fields = QWidget()
        form = QFormLayout(fields)
        form.addRow("Název:", QLabel((certificate_name or "").strip() or "—"))
        form.addRow("Platnost od:", QLabel(format_date(period.valid_from)))
        form.addRow("Období do:", QLabel(format_date(period.valid_to_period)))
        form.addRow(
            "Číslo osvědčení:",
            QLabel((period.certificate_number or "").strip() or "—"),
        )
        form.addRow(
            "Datum získání / zkoušky:",
            QLabel(format_date(period.exam_date)),
        )
        if period.indefinite:
            form.addRow("Platnost osvědčení:", QLabel("na dobu neurčitou"))
        else:
            form.addRow(
                "Platnost osvědčení do:",
                QLabel(format_date(period.certificate_valid_to)),
            )
        notify_value = int(period.notify_before_value or 0)
        unit = UNIT_LABELS.get(period.notify_before_unit or "", period.notify_before_unit)
        notify_text = f"{notify_value} {unit}" if notify_value > 0 else "—"
        form.addRow("Upozornit před koncem:", QLabel(notify_text))
        note_label = QLabel((period.note or "").strip() or "—")
        note_label.setWordWrap(True)
        form.addRow("Poznámka:", note_label)
        form_layout.addWidget(fields)

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments = AttachmentWidget(
            ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
            period.id,
        )
        self.attachments.btn_add.setEnabled(False)
        self.attachments.btn_add.hide()
        self.attachments.btn_remove.setEnabled(False)
        self.attachments.btn_remove.hide()
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
