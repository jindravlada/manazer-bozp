"""Karta údajů odborně způsobilé osoby + historie verzí."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
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
    DIALOG_TITLE_OZO_PERSON,
    ENTITY_OZO_PERSON_PERIOD,
    TAB_OZO_DATA,
    TAB_OZO_HISTORY,
    format_date,
    format_ozo_display_name,
)
from moduly.smlouvy_ozo.sluzby.ozo_person_service import (
    OzoPersonValidationError,
    ozo_person_service,
)
from moduly.smlouvy_ozo.ui.ozo_period_detail_dialog import OzoPeriodDetailDialog


class OzoPersonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.person = ozo_person_service.get()
        self.period = ozo_person_service.get_open_period(self.person)
        self.setWindowTitle(DIALOG_TITLE_OZO_PERSON)
        configure_resizable_form_dialog(
            self, width=640, height=620, min_width=480, min_height=440
        )

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_data_tab(), TAB_OZO_DATA)
        self.tabs.addTab(self._build_history_tab(), TAB_OZO_HISTORY)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=self.person is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=self.person is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        if self.period is not None:
            self._load_period(self.period)
        elif self.person is not None:
            self._load_period(self.person)
        self._sync_attachments_hint()
        self._reload_history()
        self._editor.capture_baseline()

    def _build_data_tab(self) -> QWidget:
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
            "Nové datum zkoušky / periodické zkoušky pozdější než u současné "
            "verze založí novou historickou verzi a uzavře předchozí."
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
        period_id = self.period.id if self.period is not None else None
        self.attachments = AttachmentWidget(ENTITY_OZO_PERSON_PERIOD, period_id)
        attachments_layout.addWidget(self.attachments_hint)
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        return wrap_in_scroll_area(form_host)

    def _build_history_tab(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        self.history_empty = QLabel(
            "Zatím nejsou evidovány uzavřené historické verze údajů OZO."
        )
        self.history_empty.setObjectName("MutedText")
        self.history_empty.setWordWrap(True)
        self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Platnost od",
                "Platnost do",
                "Jméno",
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
        self.history_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.history_table.doubleClicked.connect(self._open_history_period)

        layout.addWidget(self.history_empty)
        layout.addWidget(self.history_table)
        return host

    def _load_period(self, source) -> None:
        self.title_before.setText(getattr(source, "title_before", "") or "")
        self.first_name.setText(source.first_name or "")
        self.last_name.setText(source.last_name or "")
        self.title_after.setText(getattr(source, "title_after", "") or "")
        self.residence_address.setText(source.residence_address or "")
        self.exam_date.set_date_value(source.exam_date)
        self.certificate_number.setText(source.certificate_number or "")
        self.certificate_valid_to.set_date_value(source.certificate_valid_to)
        self.note.setPlainText(source.note or "")

    def _sync_attachments_hint(self) -> None:
        has_id = self.period is not None and self.period.id is not None
        self.attachments_hint.setVisible(not has_id)

    def _reload_history(self) -> None:
        periods = ozo_person_service.list_closed_periods(self.person)
        self.history_table.setRowCount(0)
        if not periods:
            self.history_empty.show()
            self.history_table.hide()
            return
        self.history_empty.hide()
        self.history_table.show()
        self.history_table.setRowCount(len(periods))
        for row, period in enumerate(periods):
            full_name = format_ozo_display_name(
                period.title_before or "",
                period.first_name or "",
                period.last_name or "",
                period.title_after or "",
            )
            values = [
                format_date(period.valid_from),
                format_date(period.valid_to),
                full_name or "—",
                format_date(period.exam_date),
                (period.certificate_number or "").strip() or "—",
                format_date(period.certificate_valid_to),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, period.id)
                self.history_table.setItem(row, col, item)

    def _open_history_period(self, *_args) -> None:
        rows = self.history_table.selectionModel().selectedRows()
        if not rows:
            index = self.history_table.currentIndex()
            if not index.isValid():
                return
            row = index.row()
        else:
            row = rows[0].row()
        item = self.history_table.item(row, 0)
        if item is None:
            return
        period_id = item.data(Qt.ItemDataRole.UserRole)
        period = ozo_person_service.get_period(int(period_id))
        if period is None:
            return
        dialog = OzoPeriodDetailDialog(self, period=period)
        dialog.exec()

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
            "note": self.note.toPlainText().strip(),
        }

    def _save(self) -> bool:
        try:
            self.person = ozo_person_service.save(**self.get_data())
        except OzoPersonValidationError as error:
            QMessageBox.warning(self, DIALOG_TITLE_OZO_PERSON, str(error))
            return False
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, DIALOG_TITLE_OZO_PERSON, str(error))
            return False
        self.period = ozo_person_service.get_open_period(self.person)
        if self.period is not None:
            self.attachments.set_entity(ENTITY_OZO_PERSON_PERIOD, self.period.id)
            self._load_period(self.period)
        self._sync_attachments_hint()
        self._reload_history()
        return True
