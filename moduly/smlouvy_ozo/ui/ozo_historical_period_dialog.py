"""Editor pro doplnění historického osvědčení OZO do časové osy."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.smlouvy_ozo.constants import (
    DIALOG_TITLE_OZO_HISTORICAL,
    ENTITY_OZO_PERSON_PERIOD,
    UNIT_DAYS,
)
from moduly.smlouvy_ozo.sluzby.ozo_person_service import (
    OzoPersonValidationError,
    ozo_person_service,
)


class OzoHistoricalPeriodDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.period = None
        self.setWindowTitle(DIALOG_TITLE_OZO_HISTORICAL)
        configure_resizable_form_dialog(
            self, width=640, height=560, min_width=480, min_height=400
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_form(), 1)

        buttons = create_save_cancel_box(self, is_new=True)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=True,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        self._prefill_from_current()
        self._editor.capture_baseline()

    def _build_form(self) -> QWidget:
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)

        fields = QWidget()
        form = QFormLayout(fields)
        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.residence_address = QLineEdit()
        self.exam_date = NullableDateEdit()
        self.certificate_number = QLineEdit()
        self.certificate_valid_to = NullableDateEdit()
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(60)

        form.addRow("Titul před jménem:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za jménem:", self.title_after)
        form.addRow("Adresa bydliště / trvalého pobytu:", self.residence_address)
        form.addRow("Datum zkoušky / periodické zkoušky:", self.exam_date)
        form.addRow("Číslo osvědčení:", self.certificate_number)
        form.addRow("Platnost osvědčení do:", self.certificate_valid_to)
        form.addRow("Poznámka:", self.note)
        form_layout.addWidget(fields)

        hint = QLabel(
            "Doplníte starší nebo prostřední osvědčení do historie. "
            "Aktuální verze OZO a upozornění se nezmění. "
            "Období používání ve výstupech se přepočítá podle data zkoušky."
        )
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        form_layout.addWidget(hint)

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments_hint = QLabel(
            "Přílohy (např. sken osvědčení OZO) lze přidat až po uložení záznamu."
        )
        self.attachments_hint.setObjectName("MutedText")
        self.attachments_hint.setWordWrap(True)
        self.attachments = AttachmentWidget(ENTITY_OZO_PERSON_PERIOD, None)
        attachments_layout.addWidget(self.attachments_hint)
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        return wrap_in_scroll_area(form_host)

    def _prefill_from_current(self) -> None:
        current = ozo_person_service.get_open_period()
        if current is None:
            return
        self.title_before.setText(current.title_before or "")
        self.first_name.setText(current.first_name or "")
        self.last_name.setText(current.last_name or "")
        self.title_after.setText(current.title_after or "")
        self.residence_address.setText(current.residence_address or "")

    def get_data(self) -> dict:
        return {
            "title_before": self.title_before.text().strip(),
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "title_after": self.title_after.text().strip(),
            "residence_address": self.residence_address.text().strip(),
            "exam_date": self.exam_date.get_date(),
            "certificate_number": self.certificate_number.text().strip(),
            "certificate_valid_to": self.certificate_valid_to.get_date(),
            "notify_before_value": 0,
            "notify_before_unit": UNIT_DAYS,
            "note": self.note.toPlainText().strip(),
        }

    def _save(self) -> bool:
        try:
            self.period = ozo_person_service.insert_historical_period(**self.get_data())
        except OzoPersonValidationError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        if self.period is not None:
            self.attachments.set_entity(ENTITY_OZO_PERSON_PERIOD, self.period.id)
            self.attachments_hint.setVisible(False)
        return True
