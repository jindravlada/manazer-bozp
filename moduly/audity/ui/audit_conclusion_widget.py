import traceback
from datetime import date

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.audity.constants import (
    AUDIT_COMPLETION_CONFIRM_MESSAGE,
    AUDIT_CONCLUSION_LABEL,
    AUDIT_CONCLUSION_REQUIRED_MESSAGE,
    AUDIT_DETAILED_REPORT_BUTTON_LABEL,
    AUDIT_DETAILED_REPORT_DIALOG_TITLE,
    AUDIT_LEAD_RECOMMENDATION_GENERATE_BUTTON,
    AUDIT_LEAD_RECOMMENDATION_LABEL,
    AUDIT_LEAD_RECOMMENDATION_REPLACE_CONFIRM,
    AUDIT_PROTOCOL_BUTTON_LABEL,
    AUDIT_PROTOCOL_DIALOG_TITLE,
)
from moduly.audity.sluzby.audit_lead_recommendation_service import (
    generate_lead_auditor_recommendation,
    is_recommendation_blank,
    recommendation_status_label,
    resolve_lead_auditor_recommendation_text,
)
from moduly.audity.sluzby.audit_service import AuditCompletionError, audit_service
from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service


class AuditConclusionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit = None
        self._on_complete = None
        self._on_review_needed = None
        self._recommendation_review_pending = False

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

        conclusion_group = QGroupBox(AUDIT_CONCLUSION_LABEL)
        conclusion_layout = QVBoxLayout(conclusion_group)
        conclusion_layout.addWidget(QLabel(f"{AUDIT_CONCLUSION_LABEL}:"))
        self.conclusion_edit = QTextEdit()
        self.conclusion_edit.setPlaceholderText(
            "Shrnutí průběhu a výsledků auditu. Při dokončení auditu je závěr povinný."
        )
        self.conclusion_edit.setMinimumHeight(160)
        self.conclusion_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        conclusion_layout.addWidget(self.conclusion_edit, stretch=1)
        layout.addWidget(conclusion_group, stretch=1)

        recommendation_group = QGroupBox(AUDIT_LEAD_RECOMMENDATION_LABEL)
        recommendation_layout = QVBoxLayout(recommendation_group)
        self.recommendation_edit = QTextEdit()
        self.recommendation_edit.setPlaceholderText(
            "Doporučení vedoucího auditora. Při novém dokončení auditu je povinné."
        )
        self.recommendation_edit.setMinimumHeight(90)
        recommendation_layout.addWidget(self.recommendation_edit)
        self.generate_recommendation_btn = QPushButton(
            AUDIT_LEAD_RECOMMENDATION_GENERATE_BUTTON
        )
        self.generate_recommendation_btn.clicked.connect(
            self._generate_recommendation_clicked
        )
        recommendation_layout.addWidget(self.generate_recommendation_btn)
        self.recommendation_status_label = QLabel("")
        self.recommendation_status_label.setObjectName("InfoText")
        self.recommendation_status_label.setWordWrap(True)
        recommendation_layout.addWidget(self.recommendation_status_label)
        layout.addWidget(recommendation_group)

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

        self._update_state()

    def set_complete_handler(self, handler) -> None:
        self._on_complete = handler

    def set_review_needed_handler(self, handler) -> None:
        self._on_review_needed = handler

    def load_audit(self, audit) -> None:
        self.audit = audit
        self._load_editor_fields()
        self.refresh()

    def _load_editor_fields(self) -> None:
        """Načte editovatelná pole jen při load — ne při refresh souhrnu."""
        if self.audit is None:
            self.finished_at_edit.clear_date()
            self.silne_stranky_edit.clear()
            self.conclusion_edit.clear()
            self.recommendation_edit.clear()
            self._recommendation_review_pending = False
            return

        finished_at = getattr(self.audit, "finished_at", None)
        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)
        else:
            self.finished_at_edit.clear_date()

        self.silne_stranky_edit.setPlainText(
            getattr(self.audit, "silne_stranky", "") or ""
        )
        self.conclusion_edit.setPlainText(
            getattr(self.audit, "conclusion_text", None) or ""
        )
        saved_rec = getattr(self.audit, "lead_auditor_recommendation", None)
        if is_recommendation_blank(saved_rec) and getattr(
            self.audit, "finished_at", None
        ) is not None:
            self.recommendation_edit.setPlainText(
                resolve_lead_auditor_recommendation_text(self.audit)
            )
        else:
            self.recommendation_edit.setPlainText(saved_rec or "")
        self._recommendation_review_pending = False

    def refresh(self) -> None:
        audit_id = self.audit.id if self.audit is not None else None
        self._update_state()

        if audit_id is None:
            self.status_label.setText("—")
            self.findings_total_label.setText("0")
            self.findings_open_label.setText("0")
            self.tasks_total_label.setText("0")
            self.tasks_active_label.setText("0")
            self.complete_btn.setEnabled(False)
            self._refresh_recommendation_status()
            return

        summary = audit_service.get_conclusion_summary(audit_id)
        self.findings_total_label.setText(str(summary["findings_total"]))
        self.findings_open_label.setText(str(summary["findings_open"]))
        self.tasks_total_label.setText(str(summary["tasks_total"]))
        self.tasks_active_label.setText(str(summary["tasks_active"]))

        # Stav odvozuj z editoru (finished_at) + started_at auditu — nepřepisuj textová pole.
        started_at = getattr(self.audit, "started_at", None)
        finished_at = self.finished_at_edit.get_date()
        status = audit_service.derive_status(started_at, finished_at)
        self.status_label.setText(status)
        self.complete_btn.setEnabled(finished_at is None)
        self._refresh_recommendation_status()

    def get_data(self) -> dict:
        return {
            "finished_at": self.finished_at_edit.get_date(),
            "silne_stranky": self.silne_stranky_edit.toPlainText().strip(),
            "conclusion_text": self.conclusion_edit.toPlainText(),
            "lead_auditor_recommendation": self.recommendation_edit.toPlainText(),
        }

    def recommendation_review_pending(self) -> bool:
        return self._recommendation_review_pending

    def mark_recommendation_review_pending(self) -> None:
        self._recommendation_review_pending = True
        self._refresh_recommendation_status()

    def apply_generated_recommendation(self, text: str) -> None:
        self.recommendation_edit.setPlainText(text)
        self._recommendation_review_pending = True
        self._refresh_recommendation_status()

    def _refresh_recommendation_status(self) -> None:
        if self.audit is None or getattr(self.audit, "id", None) is None:
            self.recommendation_status_label.setText("")
            return
        self.recommendation_status_label.setText(
            recommendation_status_label(self.audit)
        )

    def _generate_recommendation_clicked(self) -> None:
        if self.audit is None or getattr(self.audit, "id", None) is None:
            QMessageBox.information(self, "Závěr", "Audit je nutné nejdříve uložit.")
            return
        current = self.recommendation_edit.toPlainText()
        if not is_recommendation_blank(current):
            answer = QMessageBox.question(
                self,
                AUDIT_LEAD_RECOMMENDATION_LABEL,
                AUDIT_LEAD_RECOMMENDATION_REPLACE_CONFIRM,
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer != QMessageBox.Yes:
                return
        draft = generate_lead_auditor_recommendation(int(self.audit.id))
        self.recommendation_edit.setPlainText(draft)
        self._refresh_recommendation_status()

    def _update_state(self) -> None:
        enabled = self.audit is not None and self.audit.id is not None
        self.info_label.setVisible(not enabled)
        self.protocol_btn.setEnabled(enabled)
        self.detailed_report_btn.setEnabled(enabled)
        self.generate_recommendation_btn.setEnabled(enabled)

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

        if audit_service.is_conclusion_blank(self.conclusion_edit.toPlainText()):
            QMessageBox.warning(self, "Závěr", AUDIT_CONCLUSION_REQUIRED_MESSAGE)
            self.conclusion_edit.setFocus()
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
        auto_finished_at = False
        if finished_at is None:
            finished_at = date.today()
            auto_finished_at = True
            self.finished_at_edit.set_date_value(finished_at)

        if self._on_complete is None:
            return

        try:
            saved = self._on_complete(finished_at=finished_at)
        except AuditCompletionError as exc:
            QMessageBox.warning(self, "Závěr", str(exc) or AUDIT_CONCLUSION_REQUIRED_MESSAGE)
            self._load_editor_fields()
            self.refresh()
            return

        if saved:
            self.refresh()
        else:
            if auto_finished_at:
                self.finished_at_edit.clear_date()
            self.refresh()
