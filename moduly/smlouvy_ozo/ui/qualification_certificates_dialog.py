"""Seznam ostatních osvědčení."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_close_box,
    exec_maximized,
)
from moduly.smlouvy_ozo.constants import (
    ACTION_EDIT,
    ACTION_RENEW_CERTIFICATE,
    CERTIFICATE_EMPTY_STATE,
    CERTIFICATE_NOT_FOUND_MESSAGE,
    DIALOG_TITLE_CERTIFICATE_NEW,
    DIALOG_TITLE_OTHER_CERTIFICATES,
    format_date,
)
from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
    qualification_certificate_service,
)
from moduly.smlouvy_ozo.ui.qualification_certificate_dialog import (
    QualificationCertificateDialog,
)


class QualificationCertificatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE_OTHER_CERTIFICATES)
        configure_resizable_form_dialog(
            self, width=780, height=480, min_width=560, min_height=360
        )

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(DIALOG_TITLE_CERTIFICATE_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.edit_btn.setEnabled(False)
        self.renew_btn = QPushButton(ACTION_RENEW_CERTIFICATE)
        self.renew_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.renew_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.empty_label = QLabel(CERTIFICATE_EMPTY_STATE)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("MutedText")
        self.empty_label.setWordWrap(True)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                "Název",
                "Číslo osvědčení",
                "Datum zkoušky",
                "Platnost do",
                "Předstih",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.selectionModel().selectionChanged.connect(self._refresh_buttons)

        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        buttons = create_close_box(self)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.new_btn.clicked.connect(self.new_certificate)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.renew_btn.clicked.connect(self.renew_selected)
        self.refresh()

    def refresh(self) -> None:
        certificates = qualification_certificate_service.get_all(active_only=True)
        self.table.setRowCount(0)
        if not certificates:
            self.empty_label.show()
            self.table.hide()
            self._refresh_buttons()
            return
        self.empty_label.hide()
        self.table.show()
        self.table.setRowCount(len(certificates))
        for row, certificate in enumerate(certificates):
            period = qualification_certificate_service.get_open_period(certificate)
            number = ""
            exam = "—"
            valid_to = "—"
            notify = "—"
            if period is not None:
                number = (period.certificate_number or "").strip()
                exam = format_date(period.exam_date)
                if period.indefinite:
                    valid_to = "neurčitá"
                else:
                    valid_to = format_date(period.certificate_valid_to)
                value = int(period.notify_before_value or 0)
                if value > 0:
                    from moduly.smlouvy_ozo.constants import UNIT_LABELS

                    unit = UNIT_LABELS.get(
                        period.notify_before_unit or "",
                        period.notify_before_unit or "",
                    )
                    notify = f"{value} {unit}"
            values = [
                certificate.name or "—",
                number or "—",
                exam,
                valid_to,
                notify,
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, certificate.id)
                self.table.setItem(row, col, item)
        self._refresh_buttons()

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        try:
            return int(item.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            return None

    def _refresh_buttons(self, *_args) -> None:
        has_selection = self._selected_id() is not None
        self.edit_btn.setEnabled(has_selection)
        self.renew_btn.setEnabled(has_selection)

    def new_certificate(self) -> None:
        dialog = QualificationCertificateDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def edit_selected(self) -> None:
        certificate = self._selected_certificate()
        if certificate is None:
            return
        dialog = QualificationCertificateDialog(self, certificate=certificate)
        exec_maximized(dialog)
        self.refresh()

    def renew_selected(self) -> None:
        certificate = self._selected_certificate()
        if certificate is None:
            return
        dialog = QualificationCertificateDialog(
            self, certificate=certificate, renew=True
        )
        exec_maximized(dialog)
        self.refresh()

    def _selected_certificate(self):
        certificate_id = self._selected_id()
        if certificate_id is None:
            return None
        certificate = qualification_certificate_service.get_by_id(certificate_id)
        if certificate is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, DIALOG_TITLE_OTHER_CERTIFICATES, CERTIFICATE_NOT_FOUND_MESSAGE
            )
            self.refresh()
            return None
        return certificate

    def open_certificate(self, certificate_id: int) -> None:
        certificate = qualification_certificate_service.get_by_id(certificate_id)
        if certificate is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, DIALOG_TITLE_OTHER_CERTIFICATES, CERTIFICATE_NOT_FOUND_MESSAGE
            )
            self.refresh()
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == certificate_id:
                self.table.selectRow(row)
                break
        dialog = QualificationCertificateDialog(self, certificate=certificate)
        exec_maximized(dialog)
        self.refresh()
