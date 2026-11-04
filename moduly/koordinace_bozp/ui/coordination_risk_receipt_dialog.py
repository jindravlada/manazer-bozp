"""Dialog následného převzetí rizik u uzavřené koordinace."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import (
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_RISK_RECEIPT,
    COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES,
    RISK_RECEIPT_METHOD_EMAIL,
    RISK_RECEIPT_METHOD_LABELS,
    RISK_RECEIPT_METHOD_PAPER,
    RISK_RECEIPT_METHODS,
    RISK_SUBMISSION_STATUS_LABELS,
    RISK_SUBMISSION_STATUS_WILL_EMAIL,
    RISK_SUBMISSION_STATUS_WILL_PAPER,
)
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    CoordinationAttachmentError,
    coordination_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_abbreviation,
)
from moduly.koordinace_bozp.sluzby.coordination_risk_receipt_service import (
    CoordinationRiskReceiptError,
    coordination_risk_receipt_service,
)
from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
    coordination_risk_submission_service,
)

_DIALOG_TITLE = "Předání rizik"
_HISTORY_COL_NOTE = 7
_HISTORY_COL_ATTACHMENT_BEFORE = 8
_HISTORY_COL_ATTACHMENT_AFTER = 9
_HISTORY_STRETCH_COLUMNS = (5, 6, _HISTORY_COL_NOTE, 8, 9)
_UNSAVED_BACK_LABEL = "Zpět"


def _exec_message_box(box: QMessageBox) -> int:
    return int(box.exec())


def _format_day(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def _format_moment(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


class CoordinationRiskReceiptDialog(QDialog):
    """Potvrzení a oprava následného převzetí bez otevření koordinace."""

    def __init__(self, parent=None, *, coordination_id: int):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._loading = False
        self._dirty = False
        self._allow_close = False
        self._loaded_employer_id: int | None = None
        self._current_attachment_id: int | None = None
        self._pending_path: str | None = None

        self.setWindowTitle(_DIALOG_TITLE)
        configure_resizable_form_dialog(
            self,
            width=760,
            height=680,
            min_width=560,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.employer_combo = QComboBox()
        form.addRow("Dodavatel:", self.employer_combo)

        self.operational_status = QLabel("—")
        self.operational_status.setWordWrap(True)
        form.addRow("Provozní stav:", self.operational_status)

        self.agreement_method = QLabel("—")
        self.agreement_method.setWordWrap(True)
        self.agreement_date = QLabel("—")
        form.addRow("Dohodnutý způsob:", self.agreement_method)
        form.addRow("Dohodnutý termín:", self.agreement_date)

        self.received_on = NullableDateEdit()
        form.addRow("Datum skutečného převzetí:", self.received_on)

        self.receipt_method = QComboBox()
        for method in RISK_RECEIPT_METHODS:
            self.receipt_method.addItem(RISK_RECEIPT_METHOD_LABELS[method], method)
        form.addRow("Způsob převzetí:", self.receipt_method)

        self.storage_location = QLineEdit()
        self.storage_location.setMaxLength(300)
        self._storage_label = QLabel("Místo uložení dokumentu:")
        form.addRow(self._storage_label, self.storage_location)

        self.note = QTextEdit()
        note_height = self.note.fontMetrics().lineSpacing() * 5 + 16
        self.note.setFixedHeight(note_height)
        self.note.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        form.addRow("Poznámka:", self.note)

        attachment_row = QHBoxLayout()
        self.attachment_label = QLabel("Nepřipojeno")
        self.attachment_label.setWordWrap(True)
        self.choose_file_btn = QPushButton("Připojit soubor")
        self.open_attachment_btn = QPushButton("Otevřít")
        self.open_attachment_btn.setEnabled(False)
        attachment_row.addWidget(self.attachment_label, 1)
        attachment_row.addWidget(self.open_attachment_btn)
        attachment_row.addWidget(self.choose_file_btn)
        attachment_host = QWidget()
        attachment_host.setLayout(attachment_row)
        form.addRow("Příloha:", attachment_host)

        self.recorded_label = QLabel("")
        self.recorded_label.setWordWrap(True)
        form.addRow("Zaevidováno:", self.recorded_label)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        self.history_panel = QWidget()
        history_layout = QVBoxLayout(self.history_panel)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_header = QHBoxLayout()
        history_header.addWidget(QLabel("Historie změn"))
        history_header.addStretch()
        self.open_history_btn = QPushButton("Otevřít přílohu z historie")
        history_header.addWidget(self.open_history_btn)
        history_header_host = QWidget()
        history_header_host.setLayout(history_header)
        history_layout.addWidget(history_header_host)
        self.history_table = QTableWidget(0, 10)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Okamžik",
                "Datum před",
                "Datum po",
                "Způsob před",
                "Způsob po",
                "Místo před",
                "Místo po",
                "Poznámka před / po",
                "Příloha před",
                "Příloha po",
            ]
        )
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setWordWrap(True)
        self.history_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.history_table.setMinimumHeight(140)
        history_header_view = self.history_table.horizontalHeader()
        history_header_view.setStretchLastSection(False)
        for column in range(self.history_table.columnCount()):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if column in _HISTORY_STRETCH_COLUMNS
                else QHeaderView.ResizeMode.ResizeToContents
            )
            history_header_view.setSectionResizeMode(column, mode)
        self.history_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        history_layout.addWidget(self.history_table, 1)
        self.history_panel.setVisible(False)
        layout.addWidget(self.history_panel, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.save_btn = QPushButton("Uložit")
        self.save_close_btn = QPushButton("Uložit a zavřít")
        self.close_btn = QPushButton("Zavřít")
        configure_editor_save_button(self.save_btn)
        configure_editor_save_button(self.save_close_btn)
        self.save_close_btn.setText("Uložit a zavřít")
        configure_editor_close_button(self.close_btn, is_new=False)
        for button in (self.save_btn, self.save_close_btn, self.close_btn):
            button.setAutoDefault(False)
            button.setDefault(False)
            footer.addWidget(button)
        layout.addLayout(footer)

        self.save_btn.clicked.connect(lambda _checked=False: self.save_receipt())
        self.save_close_btn.clicked.connect(lambda _checked=False: self.save_and_close())
        self.close_btn.clicked.connect(lambda _checked=False: self.reject())

        self.employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        self.received_on.dateChanged.connect(self._mark_dirty)
        self.receipt_method.currentIndexChanged.connect(self._on_method_changed)
        self.storage_location.textEdited.connect(self._mark_dirty)
        self.note.textChanged.connect(self._mark_dirty)
        self.choose_file_btn.clicked.connect(self.choose_file)
        self.open_attachment_btn.clicked.connect(self.open_current_attachment)
        self.open_history_btn.clicked.connect(self.open_selected_history_attachment)
        self.history_table.itemDoubleClicked.connect(
            lambda _item: self.open_selected_history_attachment()
        )

        self._reload_employers()
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def save_and_close(self) -> bool:
        """Uloží převzetí a při úspěchu dialog zavře."""
        if not self.save_receipt():
            return False
        self._allow_close = True
        self.accept()
        return True

    def save_receipt(self) -> bool:
        """Uloží převzetí. Při chybě dialog zůstane otevřený a údaje zůstanou."""
        employer_id = self.employer_combo.currentData()
        if not isinstance(employer_id, int):
            self._warn("Vyberte dodavatele.")
            return False
        attachment_id = self._current_attachment_id
        if self._pending_path:
            try:
                created = coordination_attachment_service.add_file(
                    coordination_id=self.coordination_id,
                    coordination_employer_id=employer_id,
                    source_path=self._pending_path,
                    attachment_type=ATTACHMENT_TYPE_RISK_RECEIPT,
                )
            except CoordinationAttachmentError as error:
                self._warn(str(error))
                return False
            attachment_id = created.id
            self._current_attachment_id = created.id
            self._pending_path = None
            self._show_attachment_label()
        try:
            coordination_risk_receipt_service.save_receipt(
                employer_id,
                received_on=self.received_on.get_date(),
                receipt_method=self.receipt_method.currentData(),
                storage_location=self.storage_location.text(),
                note=self.note.toPlainText(),
                attachment_id=attachment_id,
            )
        except CoordinationRiskReceiptError as error:
            self._warn(str(error))
            return False
        self._reload_employers(select_id=employer_id)
        self._info("Změny byly úspěšně uloženy.")
        return True

    def reject(self) -> None:  # noqa: A003
        if self._allow_close:
            super().reject()
            return
        if not self._prepare_close():
            return
        self._allow_close = True
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._allow_close or not self.isVisible():
            super().closeEvent(event)
            return
        if not self._prepare_close():
            event.ignore()
            return
        self._allow_close = True
        super().closeEvent(event)

    def _prepare_close(self) -> bool:
        """Při neuložených změnách nabídne Uložit / Neukládat / Zpět."""
        if not self._dirty:
            return True
        decision = confirm_unsaved_editor_close(
            self,
            title=_DIALOG_TITLE,
            abort_label=_UNSAVED_BACK_LABEL,
        )
        if decision == "cancel":
            return False
        if decision == "discard":
            self._dirty = False
            return True
        return self.save_receipt()

    def open_current_attachment(self) -> bool:
        """Otevře aktuálně přiřazenou přílohu převzetí."""
        if not self._current_attachment_id:
            self._warn("Příloha není připojena.")
            return False
        return self._open_attachment(self._current_attachment_id)

    def open_selected_history_attachment(self) -> bool:
        """Otevře přílohu z vybrané změny. Přednost má nahrazený soubor."""
        row = self.history_table.currentRow()
        if row < 0:
            self._warn("Vyberte řádek historie.")
            return False
        before_id = self._history_attachment_id(row, _HISTORY_COL_ATTACHMENT_BEFORE)
        after_id = self._history_attachment_id(row, _HISTORY_COL_ATTACHMENT_AFTER)
        attachment_id = before_id or after_id
        if not attachment_id:
            self._warn("Vybraná změna neobsahuje přílohu.")
            return False
        return self._open_attachment(attachment_id)

    def choose_file(self) -> None:
        filters = " ".join(
            f"*{suffix}" for suffix in COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat přílohu",
            "",
            f"Podporované soubory ({filters});;Všechny soubory (*)",
        )
        if not path:
            return
        self._pending_path = path
        self.attachment_label.setText(Path(path).name)
        self._mark_dirty()

    def _reload_employers(self, select_id: int | None = None) -> None:
        if select_id is None:
            current = self.employer_combo.currentData()
            select_id = current if isinstance(current, int) else self._loaded_employer_id
        employers = [
            item
            for item in coordination_employer_service.list_for_coordination(
                self.coordination_id,
                include_inactive=True,
            )
            if not item.is_main
        ]
        self._loading = True
        self.employer_combo.clear()
        for employer in employers:
            operational = coordination_risk_submission_service.operational_handover(
                employer.id
            )
            name = employer.company_name or employer_abbreviation(employer)
            label = (
                f"{employer_abbreviation(employer)} – {name} — {operational.label}"
            )
            if not employer.active:
                label = f"{label} (neaktivní)"
            self.employer_combo.addItem(label, employer.id)
        if select_id is not None:
            index = self.employer_combo.findData(select_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self._loading = False
        self._load_employer()

    def _on_employer_changed(self) -> None:
        if self._loading:
            return
        new_id = self.employer_combo.currentData()
        if new_id == self._loaded_employer_id:
            return
        if self._dirty:
            discard = self._confirm(
                "Neuložené údaje vybraného dodavatele se zahodí. Pokračovat?"
            )
            if not discard:
                self._loading = True
                index = self.employer_combo.findData(self._loaded_employer_id)
                if index >= 0:
                    self.employer_combo.setCurrentIndex(index)
                self._loading = False
                return
        self._load_employer()

    def _on_method_changed(self) -> None:
        self._update_storage_label()
        self._mark_dirty()

    def _load_employer(self) -> None:
        employer_id = self.employer_combo.currentData()
        self._loading = True
        self._pending_path = None
        self._current_attachment_id = None
        self.history_table.setRowCount(0)
        if not isinstance(employer_id, int):
            self.operational_status.setText("—")
            self.agreement_method.setText("—")
            self.agreement_date.setText("—")
            self.received_on.clear_date()
            self.storage_location.clear()
            self.note.clear()
            self.recorded_label.setText("—")
            self.attachment_label.setText("Nepřipojeno")
            self.open_attachment_btn.setEnabled(False)
            self._loaded_employer_id = None
            self._dirty = False
            self._loading = False
            self._update_storage_label()
            self._sync_history_visibility()
            return

        operational = coordination_risk_submission_service.operational_handover(
            employer_id
        )
        self.operational_status.setText(operational.label)
        submission = coordination_risk_submission_service.get_for_employer(employer_id)
        if submission is None:
            self.agreement_method.setText("—")
            self.agreement_date.setText("—")
            method = RISK_RECEIPT_METHOD_EMAIL
        else:
            self.agreement_method.setText(
                RISK_SUBMISSION_STATUS_LABELS.get(
                    submission.submission_method,
                    submission.submission_method or "—",
                )
            )
            self.agreement_date.setText(_format_day(submission.submission_date))
            method = self._suggested_method(submission.submission_method)

        receipt = coordination_risk_receipt_service.get_for_employer(employer_id)
        if receipt is None:
            self.received_on.clear_date()
            self.storage_location.clear()
            self.note.clear()
            self.recorded_label.setText("—")
            self.attachment_label.setText("Nepřipojeno")
            self.open_attachment_btn.setEnabled(False)
        else:
            self.received_on.set_date_value(receipt.received_on)
            method = receipt.receipt_method or method
            self.storage_location.setText(receipt.storage_location or "")
            self.note.setPlainText(receipt.note or "")
            self.recorded_label.setText(_format_moment(receipt.recorded_at))
            self._current_attachment_id = receipt.attachment_id
            self._show_attachment_label()
            self._load_history(receipt.id)
        index = self.receipt_method.findData(method)
        self.receipt_method.setCurrentIndex(index if index >= 0 else 0)
        self._loaded_employer_id = employer_id
        self._dirty = False
        self._loading = False
        self._update_storage_label()
        self._sync_history_visibility()

    def _load_history(self, receipt_id: int) -> None:
        history = coordination_risk_receipt_service.list_history(receipt_id)
        self.history_table.setRowCount(len(history))
        for row, entry in enumerate(history):
            values = (
                _format_moment(entry.changed_at),
                _format_day(entry.received_on_before),
                _format_day(entry.received_on_after),
                RISK_RECEIPT_METHOD_LABELS.get(
                    entry.receipt_method_before,
                    entry.receipt_method_before or "—",
                ),
                RISK_RECEIPT_METHOD_LABELS.get(
                    entry.receipt_method_after,
                    entry.receipt_method_after or "—",
                ),
                entry.storage_location_before or "—",
                entry.storage_location_after or "—",
                f"{entry.note_before or '—'} → {entry.note_after or '—'}",
            )
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, self._history_cell(value))
            self.history_table.setItem(
                row,
                _HISTORY_COL_ATTACHMENT_BEFORE,
                self._attachment_history_item(entry.attachment_id_before),
            )
            self.history_table.setItem(
                row,
                _HISTORY_COL_ATTACHMENT_AFTER,
                self._attachment_history_item(entry.attachment_id_after),
            )
        self.history_table.resizeRowsToContents()
        self._sync_history_visibility()

    def _open_attachment(self, attachment_id: int) -> bool:
        try:
            coordination_attachment_service.open_attachment(
                attachment_id,
                parent=self,
            )
        except CoordinationAttachmentError as error:
            self._warn(str(error))
            return False
        return True

    def _history_attachment_id(self, row: int, column: int) -> int | None:
        item = self.history_table.item(row, column)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if not value:
            return None
        return int(value)

    def _history_cell(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if text and text != "—":
            item.setToolTip(text)
        return item

    def _attachment_history_item(self, attachment_id: int | None) -> QTableWidgetItem:
        item = self._history_cell(self._attachment_name(attachment_id))
        if attachment_id:
            item.setData(Qt.ItemDataRole.UserRole, int(attachment_id))
        return item

    def _sync_history_visibility(self) -> None:
        self.history_panel.setVisible(self.history_table.rowCount() > 0)

    def _attachment_name(self, attachment_id: int | None) -> str:
        if not attachment_id:
            return "—"
        attachment = coordination_attachment_service.get_by_id(attachment_id)
        if attachment is None:
            return "—"
        return attachment.original_filename or "Příloha"

    def _show_attachment_label(self) -> None:
        if self._pending_path:
            self.attachment_label.setText(Path(self._pending_path).name)
            return
        if not self._current_attachment_id:
            self.attachment_label.setText("Nepřipojeno")
            self.open_attachment_btn.setEnabled(False)
            return
        attachment = coordination_attachment_service.get_by_id(
            self._current_attachment_id
        )
        if attachment is None:
            self.attachment_label.setText("Nepřipojeno")
            self.open_attachment_btn.setEnabled(False)
            return
        self.attachment_label.setText(attachment.original_filename or "Příloha")
        self.open_attachment_btn.setEnabled(True)

    def _suggested_method(self, submission_method: str | None) -> str:
        if submission_method == RISK_SUBMISSION_STATUS_WILL_PAPER:
            return RISK_RECEIPT_METHOD_PAPER
        if submission_method == RISK_SUBMISSION_STATUS_WILL_EMAIL:
            return RISK_RECEIPT_METHOD_EMAIL
        return RISK_RECEIPT_METHOD_EMAIL

    def _update_storage_label(self) -> None:
        if self.receipt_method.currentData() == RISK_RECEIPT_METHOD_PAPER:
            self._storage_label.setText("Místo uložení dokumentu *:")
        else:
            self._storage_label.setText("Místo uložení dokumentu:")

    def _mark_dirty(self, *_args) -> None:
        if self._loading:
            return
        self._dirty = True

    def _warn(self, text: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_DIALOG_TITLE)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        _exec_message_box(box)

    def _info(self, text: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(_DIALOG_TITLE)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        _exec_message_box(box)

    def _confirm(self, text: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_DIALOG_TITLE)
        box.setText(text)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return _exec_message_box(box) == int(QMessageBox.StandardButton.Yes)
