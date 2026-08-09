"""Read-only detail historické verze OZO."""

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
    DIALOG_TITLE_OZO_PERIOD,
    ENTITY_OZO_PERSON_PERIOD,
    format_date,
    format_ozo_display_name,
)


class OzoPeriodDetailDialog(QDialog):
    def __init__(self, parent=None, *, period):
        super().__init__(parent)
        self.period = period
        self.setWindowTitle(DIALOG_TITLE_OZO_PERIOD)
        configure_resizable_form_dialog(
            self, width=560, height=520, min_width=420, min_height=360
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)

        fields = QWidget()
        form = QFormLayout(fields)
        full_name = format_ozo_display_name(
            period.title_before or "",
            period.first_name or "",
            period.last_name or "",
            period.title_after or "",
        )
        form.addRow("Platnost od:", QLabel(format_date(period.valid_from)))
        form.addRow("Platnost do:", QLabel(format_date(period.valid_to)))
        form.addRow("Jméno:", QLabel(full_name or "—"))
        form.addRow(
            "Adresa bydliště / trvalého pobytu:",
            QLabel((period.residence_address or "").strip() or "—"),
        )
        form.addRow(
            "Datum zkoušky / periodické zkoušky:",
            QLabel(format_date(period.exam_date)),
        )
        form.addRow(
            "Číslo osvědčení:",
            QLabel((period.certificate_number or "").strip() or "—"),
        )
        form.addRow(
            "Platnost osvědčení do:",
            QLabel(format_date(period.certificate_valid_to)),
        )
        note = (period.note or "").strip() or "—"
        note_label = QLabel(note)
        note_label.setWordWrap(True)
        form.addRow("Poznámka:", note_label)
        form_layout.addWidget(fields)

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments = AttachmentWidget(
            ENTITY_OZO_PERSON_PERIOD,
            period.id,
        )
        # Historická verze – bez přidávání / mazání.
        self.attachments.btn_add.setEnabled(False)
        self.attachments.btn_add.hide()
        self.attachments.btn_remove.setEnabled(False)
        self.attachments.btn_remove.hide()
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
