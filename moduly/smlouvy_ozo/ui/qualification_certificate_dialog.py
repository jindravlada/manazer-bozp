"""Editor ostatního osvědčení / odborné způsobilosti."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
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
    DIALOG_TITLE_CERTIFICATE_EDIT,
    DIALOG_TITLE_CERTIFICATE_NEW,
    DIALOG_TITLE_CERTIFICATE_RENEW,
    ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
    NOTIFY_UNITS,
    TAB_CERTIFICATE_DATA,
    TAB_CERTIFICATE_HISTORY,
    UNIT_DAYS,
    UNIT_LABELS,
    format_date,
)
from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
    QualificationCertificateValidationError,
    qualification_certificate_service,
)
from moduly.smlouvy_ozo.ui.qualification_period_detail_dialog import (
    QualificationPeriodDetailDialog,
)


class QualificationCertificateDialog(QDialog):
    def __init__(self, parent=None, certificate=None, *, renew: bool = False):
        super().__init__(parent)
        self.certificate = certificate
        self._renew = bool(renew) and certificate is not None
        self.period = (
            qualification_certificate_service.get_open_period(certificate)
            if certificate is not None and not self._renew
            else None
        )
        if self._renew:
            title = DIALOG_TITLE_CERTIFICATE_RENEW
        elif certificate is not None:
            title = DIALOG_TITLE_CERTIFICATE_EDIT
        else:
            title = DIALOG_TITLE_CERTIFICATE_NEW
        self.setWindowTitle(title)
        configure_resizable_form_dialog(
            self, width=640, height=620, min_width=480, min_height=440
        )

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_data_tab(), TAB_CERTIFICATE_DATA)
        self.tabs.addTab(self._build_history_tab(), TAB_CERTIFICATE_HISTORY)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(
            self, is_new=certificate is None or self._renew
        )
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=certificate is None or self._renew,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        self.indefinite_checkbox.toggled.connect(self._sync_validity_fields)
        if self._renew and certificate is not None:
            self._prepare_renew(certificate)
        elif self.period is not None:
            self._load(self.certificate, self.period)
        self._sync_validity_fields()
        self._sync_attachments_hint()
        self._reload_history()
        self._editor.capture_baseline()

    def _prepare_renew(self, certificate) -> None:
        current = qualification_certificate_service.get_open_period(certificate)
        self.name.setText(certificate.name or "")
        self.name.setReadOnly(True)
        self.certificate_number.clear()
        self.exam_date.clear_date()
        self.indefinite_checkbox.setChecked(False)
        self.certificate_valid_to.clear_date()
        self.note.clear()
        if current is not None:
            self.notify_before_value.setValue(int(current.notify_before_value or 0))
            unit_index = self.notify_before_unit.findData(
                current.notify_before_unit or UNIT_DAYS
            )
            if unit_index >= 0:
                self.notify_before_unit.setCurrentIndex(unit_index)
        self.attachments.set_entity(ENTITY_QUALIFICATION_CERTIFICATE_PERIOD, None)
        self.hint_label.setText(
            "Zadáte údaje nové zkoušky / nového osvědčení stejné odborné "
            "způsobilosti. Po uložení se současná verze uzavře a vznikne "
            "nová historická verze. Přílohy nové verze přidáte až po uložení."
        )

    def _build_data_tab(self) -> QWidget:
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)
        fields = QWidget()
        form = QFormLayout(fields)

        self.name = QLineEdit()
        self.certificate_number = QLineEdit()
        self.exam_date = NullableDateEdit()
        self.indefinite_checkbox = QCheckBox("Na dobu neurčitou")
        self.certificate_valid_to = NullableDateEdit()

        self.notify_before_value = QSpinBox()
        self.notify_before_value.setRange(0, 9999)
        self.notify_before_value.setValue(0)
        self.notify_before_unit = QComboBox()
        for unit in NOTIFY_UNITS:
            self.notify_before_unit.addItem(UNIT_LABELS[unit], unit)
        self.notify_before_unit.setCurrentIndex(NOTIFY_UNITS.index(UNIT_DAYS))
        notify_row = QHBoxLayout()
        notify_row.addWidget(self.notify_before_value)
        notify_row.addWidget(self.notify_before_unit, 1)
        notify_row.addWidget(QLabel("předem"))
        self.notify_widget = QWidget()
        self.notify_widget.setLayout(notify_row)

        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(60)

        form.addRow("Název odborné způsobilosti *:", self.name)
        form.addRow("Číslo osvědčení:", self.certificate_number)
        form.addRow("Datum získání / zkoušky:", self.exam_date)
        form.addRow("", self.indefinite_checkbox)
        form.addRow("Platnost do:", self.certificate_valid_to)
        form.addRow("Upozornit před koncem:", self.notify_widget)
        form.addRow("Poznámka:", self.note)
        form_layout.addWidget(fields)

        self.hint_label = QLabel(
            "Upravit mění jen aktuální verzi. Novou zkoušku stejné "
            "způsobilosti založíte akcí Obnovit osvědčení. Předstih 0 = "
            "bez upozornění předem."
        )
        self.hint_label.setObjectName("MutedText")
        self.hint_label.setWordWrap(True)
        form_layout.addWidget(self.hint_label)

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments_hint = QLabel(
            "Přílohy (např. sken osvědčení) lze přidat až po uložení záznamu."
        )
        self.attachments_hint.setObjectName("MutedText")
        self.attachments_hint.setWordWrap(True)
        period_id = self.period.id if self.period is not None else None
        self.attachments = AttachmentWidget(
            ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
            period_id,
        )
        attachments_layout.addWidget(self.attachments_hint)
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)
        return wrap_in_scroll_area(form_host)

    def _build_history_tab(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        self.history_empty = QLabel(
            "Zatím nejsou evidovány uzavřené historické verze osvědčení."
        )
        self.history_empty.setObjectName("MutedText")
        self.history_empty.setWordWrap(True)
        self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Platnost od",
                "Platnost do",
                "Datum zkoušky",
                "Číslo osvědčení",
                "Platnost osvědčení do",
            ]
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.doubleClicked.connect(self._open_history_period)
        layout.addWidget(self.history_empty)
        layout.addWidget(self.history_table)
        return host

    def _load(self, certificate, period) -> None:
        self.name.setText(certificate.name or "")
        self.certificate_number.setText(period.certificate_number or "")
        self.exam_date.set_date_value(period.exam_date)
        self.indefinite_checkbox.setChecked(bool(period.indefinite))
        self.certificate_valid_to.set_date_value(period.certificate_valid_to)
        self.notify_before_value.setValue(int(period.notify_before_value or 0))
        unit_index = self.notify_before_unit.findData(
            period.notify_before_unit or UNIT_DAYS
        )
        if unit_index >= 0:
            self.notify_before_unit.setCurrentIndex(unit_index)
        self.note.setPlainText(period.note or "")

    def _sync_validity_fields(self) -> None:
        indefinite = self.indefinite_checkbox.isChecked()
        self.certificate_valid_to.setEnabled(not indefinite)
        self.notify_widget.setEnabled(not indefinite)
        if indefinite:
            self.certificate_valid_to.clear_date()
            self.notify_before_value.setValue(0)

    def _sync_attachments_hint(self) -> None:
        has_id = (
            not self._renew
            and self.period is not None
            and self.period.id is not None
        )
        self.attachments_hint.setVisible(not has_id)
        if self._renew:
            self.attachments_hint.setText(
                "Přílohy nové verze (např. sken osvědčení) lze přidat až po uložení."
            )
            self.attachments_hint.setVisible(True)

    def _reload_history(self) -> None:
        if self.certificate is None:
            periods = []
        else:
            periods = qualification_certificate_service.list_closed_periods(
                self.certificate
            )
        self.history_table.setRowCount(0)
        if not periods:
            self.history_empty.show()
            self.history_table.hide()
            return
        self.history_empty.hide()
        self.history_table.show()
        self.history_table.setRowCount(len(periods))
        for row, period in enumerate(periods):
            values = [
                format_date(period.valid_from),
                format_date(period.valid_to_period),
                format_date(period.exam_date),
                (period.certificate_number or "").strip() or "—",
                "neurčitá"
                if period.indefinite
                else format_date(period.certificate_valid_to),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, period.id)
                self.history_table.setItem(row, col, item)

    def _open_history_period(self, *_args) -> None:
        index = self.history_table.currentIndex()
        if not index.isValid():
            return
        item = self.history_table.item(index.row(), 0)
        if item is None:
            return
        period = qualification_certificate_service.get_period(
            int(item.data(Qt.ItemDataRole.UserRole))
        )
        if period is None:
            return
        name = self.certificate.name if self.certificate is not None else ""
        dialog = QualificationPeriodDetailDialog(
            self, period=period, certificate_name=name
        )
        dialog.exec()

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "certificate_number": self.certificate_number.text().strip(),
            "exam_date": self.exam_date.get_date(),
            "indefinite": self.indefinite_checkbox.isChecked(),
            "certificate_valid_to": self.certificate_valid_to.get_date(),
            "notify_before_value": int(self.notify_before_value.value()),
            "notify_before_unit": self.notify_before_unit.currentData() or UNIT_DAYS,
            "note": self.note.toPlainText().strip(),
        }

    def _save(self) -> bool:
        data = self.get_data()
        try:
            if self._renew:
                if self.certificate is None:
                    raise QualificationCertificateValidationError(
                        "Osvědčení nebylo nalezeno."
                    )
                self.certificate = qualification_certificate_service.renew(
                    self.certificate.id,
                    **data,
                )
                self._renew = False
                self.name.setReadOnly(False)
            elif self.certificate is None:
                self.certificate = qualification_certificate_service.save(**data)
            else:
                self.certificate = qualification_certificate_service.save(
                    certificate_id=self.certificate.id,
                    **data,
                )
        except QualificationCertificateValidationError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        self.period = qualification_certificate_service.get_open_period(self.certificate)
        if self.period is not None:
            self.attachments.set_entity(
                ENTITY_QUALIFICATION_CERTIFICATE_PERIOD,
                self.period.id,
            )
        self.setWindowTitle(DIALOG_TITLE_CERTIFICATE_EDIT)
        self.hint_label.setText(
            "Upravit mění jen aktuální verzi. Novou zkoušku stejné "
            "způsobilosti založíte akcí Obnovit osvědčení. Předstih 0 = "
            "bez upozornění předem."
        )
        self._sync_attachments_hint()
        self._reload_history()
        return True
