import traceback
from datetime import date

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.audity.constants import (
    AUDIT_COMPLETION_CONFIRM_MESSAGE,
    AUDIT_DETAILED_REPORT_BUTTON_LABEL,
    AUDIT_DETAILED_REPORT_DIALOG_TITLE,
    AUDIT_PROTOCOL_BUTTON_LABEL,
    AUDIT_PROTOCOL_DIALOG_TITLE,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service


class AuditConclusionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit = None
        self._on_complete = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Závěr auditu bude dostupný až po uložení auditu.")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        summary_group = QGroupBox("Souhrn")
        summary_form = QFormLayout(summary_group)
        self.findings_total_label = QLabel("0")
        self.findings_open_label = QLabel("0")
        self.tasks_total_label = QLabel("0")
        self.tasks_active_label = QLabel("0")
        summary_form.addRow("Zjištění celkem:", self.findings_total_label)
        summary_form.addRow("Otevřená zjištění:", self.findings_open_label)
        summary_form.addRow("Úkoly celkem:", self.tasks_total_label)
        summary_form.addRow("Aktivní úkoly:", self.tasks_active_label)
        layout.addWidget(summary_group)

        strengths_group = QGroupBox("Silné stránky systému")
        strengths_layout = QVBoxLayout(strengths_group)
        self.silne_stranky_edit = QTextEdit()
        self.silne_stranky_edit.setPlaceholderText(
            "Každý řádek bude ve zprávě uveden jako samostatná silná stránka."
        )
        self.silne_stranky_edit.setMinimumHeight(90)
        strengths_layout.addWidget(self.silne_stranky_edit)
        layout.addWidget(strengths_group)

        completion_group = QGroupBox("Dokončení auditu")
        completion_form = QFormLayout(completion_group)
        self.status_label = QLabel("—")
        self.status_label.setObjectName("InfoText")
        self.finished_at_edit = NullableDateEdit()
        completion_form.addRow("Stav auditu:", self.status_label)
        completion_form.addRow("Datum ukončení:", self.finished_at_edit)
        layout.addWidget(completion_group)

        self.complete_btn = QPushButton("Dokončit audit")
        self.complete_btn.clicked.connect(self._complete_audit)
        layout.addWidget(self.complete_btn)

        self.protocol_btn = QPushButton(AUDIT_PROTOCOL_BUTTON_LABEL)
        self.protocol_btn.clicked.connect(self._export_protocol)
        layout.addWidget(self.protocol_btn)

        self.detailed_report_btn = QPushButton(AUDIT_DETAILED_REPORT_BUTTON_LABEL)
        self.detailed_report_btn.clicked.connect(self._export_detailed_report)
        layout.addWidget(self.detailed_report_btn)

        layout.addStretch()

        self._update_state()

    def set_complete_handler(self, handler) -> None:
        self._on_complete = handler

    def load_audit(self, audit) -> None:
        self.audit = audit
        self.refresh()

    def refresh(self) -> None:
        audit_id = self.audit.id if self.audit is not None else None
        self._update_state()

        if audit_id is None:
            self.status_label.setText("—")
            self.finished_at_edit.clear_date()
            self.silne_stranky_edit.clear()
            self.findings_total_label.setText("0")
            self.findings_open_label.setText("0")
            self.tasks_total_label.setText("0")
            self.tasks_active_label.setText("0")
            return

        summary = audit_service.get_conclusion_summary(audit_id)
        self.findings_total_label.setText(str(summary["findings_total"]))
        self.findings_open_label.setText(str(summary["findings_open"]))
        self.tasks_total_label.setText(str(summary["tasks_total"]))
        self.tasks_active_label.setText(str(summary["tasks_active"]))

        started_at = getattr(self.audit, "started_at", None)
        finished_at = getattr(self.audit, "finished_at", None)
        status = audit_service.derive_status(started_at, finished_at)
        self.status_label.setText(status)

        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)
        else:
            self.finished_at_edit.clear_date()

        self.silne_stranky_edit.setPlainText(getattr(self.audit, "silne_stranky", "") or "")

        self.complete_btn.setEnabled(finished_at is None)

    def get_data(self) -> dict:
        return {
            "finished_at": self.finished_at_edit.get_date(),
            "silne_stranky": self.silne_stranky_edit.toPlainText().strip(),
        }

    def _update_state(self) -> None:
        enabled = self.audit is not None and self.audit.id is not None
        self.info_label.setVisible(not enabled)
        self.protocol_btn.setEnabled(enabled)
        self.detailed_report_btn.setEnabled(enabled)

    def _export_protocol(self) -> None:
        if self.audit is None or self.audit.id is None:
            QMessageBox.information(
                self, AUDIT_PROTOCOL_DIALOG_TITLE, "Audit je nutné nejdříve uložit."
            )
            return

        try:
            warning = protokol_audit_service.incomplete_warning(self.audit)
            if warning:
                QMessageBox.warning(self, AUDIT_PROTOCOL_DIALOG_TITLE, warning)

            protokol_audit_service.open_for_audit(self.audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                f"Protokol se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _export_detailed_report(self) -> None:
        if self.audit is None or self.audit.id is None:
            QMessageBox.information(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                "Audit je nutné nejdříve uložit.",
            )
            return

        try:
            warning = protokol_audit_service.incomplete_warning(self.audit)
            if warning:
                QMessageBox.warning(self, AUDIT_DETAILED_REPORT_DIALOG_TITLE, warning)

            protokol_audit_service.open_detailed_report_for_audit(self.audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                f"Podrobnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _complete_audit(self) -> None:
        if self.audit is None or self.audit.id is None:
            QMessageBox.information(self, "Závěr", "Audit je nutné nejdříve uložit.")
            return

        audit_id = self.audit.id
        blockers = audit_service.get_completion_blockers(audit_id)
        if blockers.has_blockers():
            answer = QMessageBox.question(
                self,
                "Dokončení auditu",
                AUDIT_COMPLETION_CONFIRM_MESSAGE,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        finished_at = self.finished_at_edit.get_date()
        if finished_at is None:
            finished_at = date.today()
            self.finished_at_edit.set_date_value(finished_at)

        if self._on_complete is None:
            return

        saved = self._on_complete(finished_at=finished_at)
        if saved:
            self.refresh()
