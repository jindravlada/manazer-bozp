from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.table_header_settings import configure_and_persist_table_columns
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import (
    current_table_row,
    refresh_and_restore_selection,
)
from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    COORD_HEADER_RISKS,
    COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES,
    MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
    MAIN_EMPLOYER_RISK_HANDOVER_PROTOCOL_TEXT,
    RISK_HANDOVER_STATUS_LABELS,
    RISK_SUBMISSION_METHOD_LABELS,
    RISK_SUBMISSION_METHOD_NOT_SUBMITTED,
    RISK_SUBMISSION_METHODS,
    TAB_RISK_SUBMISSIONS,
)
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    CoordinationAttachmentError,
    coordination_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
    CoordinationRiskSubmissionError,
    coordination_risk_submission_service,
)
from moduly.koordinace_bozp.ui.coordination_attachment_table import (
    CoordinationAttachmentTable,
)


class CoordinationRiskSubmissionsTab(QWidget):
    """Záložka předání rizik dodavatelů (COORD-006)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._loading = False

        layout = QVBoxLayout(self)
        self.unavailable_label = QLabel(
            "Předání rizik dodavatelů lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        main_info = QLabel(
            f"{MAIN_EMPLOYER_RISK_HANDOVER_PROTOCOL_TEXT}\n"
            f"Příloha: „{MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE}“ "
            "(generuje se v záložce Příloha PBP)."
        )
        main_info.setWordWrap(True)
        content_layout.addWidget(main_info)

        employer_row = QHBoxLayout()
        employer_row.addWidget(QLabel("Dodavatel:"))
        self.employer_combo = QComboBox()
        employer_row.addWidget(self.employer_combo, 1)
        content_layout.addLayout(employer_row)

        self.status_label = QLabel()
        content_layout.addWidget(self.status_label)

        form = QFormLayout()
        self.submission_method = QComboBox()
        for method in RISK_SUBMISSION_METHODS:
            self.submission_method.addItem(RISK_SUBMISSION_METHOD_LABELS[method], method)
        self.submission_date = NullableDateEdit()
        self.document_reference = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)
        form.addRow("Způsob předání:", self.submission_method)
        form.addRow("Datum předání:", self.submission_date)
        form.addRow("Označení dokumentu:", self.document_reference)
        form.addRow("Poznámka:", self.note)
        content_layout.addLayout(form)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("Uložit předání")
        save_row.addWidget(self.save_btn)
        save_row.addStretch()
        content_layout.addLayout(save_row)

        content_layout.addWidget(QLabel("Přílohy:"))
        att_toolbar = QHBoxLayout()
        self.add_attachment_btn = QPushButton("Přidat přílohu")
        self.open_attachment_btn = QPushButton("Otevřít")
        self.deactivate_attachment_btn = QPushButton("Deaktivovat")
        att_toolbar.addWidget(self.add_attachment_btn)
        att_toolbar.addWidget(self.open_attachment_btn)
        att_toolbar.addWidget(self.deactivate_attachment_btn)
        att_toolbar.addStretch()
        content_layout.addLayout(att_toolbar)

        self.attachments_table = CoordinationAttachmentTable()
        configure_and_persist_table_columns(
            self.attachments_table,
            "coordination_attachments",
            COORD_HEADER_RISKS,
        )
        content_layout.addWidget(self.attachments_table)
        layout.addWidget(self.content)

        self.employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        self.save_btn.clicked.connect(self.save_submission)
        self.add_attachment_btn.clicked.connect(self.add_attachment)
        self.open_attachment_btn.clicked.connect(self.open_attachment)
        self.deactivate_attachment_btn.clicked.connect(self.deactivate_attachment)
        self.attachments_table.doubleClicked.connect(self.open_attachment)
        install_table_row_actions(
            self.attachments_table,
            on_edit=self.open_attachment,
            on_deactivate=self.deactivate_attachment,
            can_edit=lambda: self.open_attachment_btn.isEnabled(),
            can_deactivate=lambda: self.deactivate_attachment_btn.isEnabled(),
        )
        self.attachments_table.itemSelectionChanged.connect(self._update_attachment_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh_employers()
        else:
            self.employer_combo.clear()
            self.attachments_table.setRowCount(0)

    def refresh_employers(self) -> None:
        if self.coordination_id is None:
            return
        previous = self.employer_combo.currentData()
        coordination_employer_service.ensure_main_employer(self.coordination_id)
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
            label = f"{employer.abbreviation} – {employer.company_name}".strip(" –")
            if not employer.active:
                label = f"{label} (neaktivní)"
            self.employer_combo.addItem(label, employer.id)
        self._loading = False
        if previous is not None:
            index = self.employer_combo.findData(previous)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.load_selected_employer()

    def load_selected_employer(
        self,
        *,
        select_attachment_id: int | None = None,
        fallback_row: int | None = None,
        preserve_scroll: bool = False,
        ensure_visible: bool = False,
    ) -> None:
        employer_id = self.employer_combo.currentData()
        enabled = isinstance(employer_id, int)
        self.save_btn.setEnabled(enabled)
        self.add_attachment_btn.setEnabled(enabled)
        if not enabled:
            self.submission_method.setCurrentIndex(
                self.submission_method.findData(RISK_SUBMISSION_METHOD_NOT_SUBMITTED)
            )
            self.submission_date.clear_date()
            self.document_reference.clear()
            self.note.clear()
            self.status_label.setText("")
            self.attachments_table.setRowCount(0)
            self._update_attachment_buttons()
            return

        scroll_value = (
            self.attachments_table.verticalScrollBar().value()
            if preserve_scroll
            else None
        )
        record_id = (
            select_attachment_id
            if select_attachment_id is not None
            else self.attachments_table.selected_attachment_id()
        )

        submission = coordination_risk_submission_service.get_for_employer(employer_id)
        status = coordination_risk_submission_service.handover_status(employer_id)
        self.status_label.setText(
            f"Stav: {RISK_HANDOVER_STATUS_LABELS.get(status, status)}"
        )
        if submission is None:
            self.submission_method.setCurrentIndex(
                self.submission_method.findData(RISK_SUBMISSION_METHOD_NOT_SUBMITTED)
            )
            self.submission_date.clear_date()
            self.document_reference.clear()
            self.note.clear()
        else:
            index = self.submission_method.findData(submission.submission_method)
            self.submission_method.setCurrentIndex(index if index >= 0 else 0)
            if submission.submission_date:
                self.submission_date.set_date_value(submission.submission_date)
            else:
                self.submission_date.clear_date()
            self.document_reference.setText(submission.document_reference or "")
            self.note.setPlainText(submission.note or "")

        attachments = coordination_attachment_service.list_for_employer(
            employer_id,
            include_inactive=True,
        )
        self.attachments_table.load_attachments(attachments)
        configure_and_persist_table_columns(
            self.attachments_table,
            "coordination_attachments",
            COORD_HEADER_RISKS,
        )
        refresh_and_restore_selection(
            self.attachments_table,
            record_id,
            fallback_row=fallback_row,
            scroll=ensure_visible and not preserve_scroll,
            preserve_scroll_value=scroll_value,
            focus=True,
        )
        self._update_attachment_buttons()

    def save_submission(self) -> None:
        employer_id = self.employer_combo.currentData()
        if not isinstance(employer_id, int):
            return
        try:
            coordination_risk_submission_service.save_submission(
                employer_id,
                submission_method=self.submission_method.currentData(),
                submission_date=self.submission_date.get_date(),
                document_reference=self.document_reference.text().strip(),
                note=self.note.toPlainText().strip(),
            )
        except CoordinationRiskSubmissionError as error:
            QMessageBox.warning(self, TAB_RISK_SUBMISSIONS, str(error))
            return
        self.load_selected_employer(preserve_scroll=True)

    def add_attachment(self) -> None:
        employer_id = self.employer_combo.currentData()
        if not isinstance(employer_id, int) or self.coordination_id is None:
            return
        filters = " ".join(f"*{suffix}" for suffix in COORDINATION_ATTACHMENT_ALLOWED_SUFFIXES)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat přílohu",
            "",
            f"Podporované soubory ({filters});;Všechny soubory (*)",
        )
        if not path:
            return
        try:
            created = coordination_attachment_service.add_file(
                coordination_id=self.coordination_id,
                coordination_employer_id=employer_id,
                source_path=path,
                attachment_type=ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            )
        except CoordinationAttachmentError as error:
            QMessageBox.warning(self, TAB_RISK_SUBMISSIONS, str(error))
            return
        self.load_selected_employer(
            select_attachment_id=created.id,
            ensure_visible=True,
        )

    def open_attachment(self) -> None:
        attachment_id = self.attachments_table.selected_attachment_id()
        if attachment_id is None:
            QMessageBox.information(self, TAB_RISK_SUBMISSIONS, "Vyberte přílohu.")
            return
        try:
            coordination_attachment_service.open_attachment(attachment_id, parent=self)
        except CoordinationAttachmentError as error:
            QMessageBox.warning(self, TAB_RISK_SUBMISSIONS, str(error))

    def deactivate_attachment(self) -> None:
        attachment_id = self.attachments_table.selected_attachment_id()
        if attachment_id is None:
            QMessageBox.information(self, TAB_RISK_SUBMISSIONS, "Vyberte přílohu.")
            return
        attachment = coordination_attachment_service.get_by_id(attachment_id)
        if attachment is None:
            return
        if not attachment.active:
            QMessageBox.information(self, TAB_RISK_SUBMISSIONS, "Příloha je již neaktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            "Opravdu deaktivovat přílohu? Soubor zůstane v úložišti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            row = current_table_row(self.attachments_table)
            coordination_attachment_service.deactivate(attachment_id)
            self.load_selected_employer(
                select_attachment_id=attachment_id,
                fallback_row=row,
                ensure_visible=True,
            )

    def _on_employer_changed(self) -> None:
        if self._loading:
            return
        self.load_selected_employer()

    def _update_attachment_buttons(self) -> None:
        attachment_id = self.attachments_table.selected_attachment_id()
        has_selection = attachment_id is not None
        self.open_attachment_btn.setEnabled(has_selection)
        if not has_selection:
            self.deactivate_attachment_btn.setEnabled(False)
            return
        attachment = coordination_attachment_service.get_by_id(attachment_id)
        self.deactivate_attachment_btn.setEnabled(
            attachment is not None and bool(attachment.active)
        )
