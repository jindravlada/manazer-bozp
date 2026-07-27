from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box, configure_resizable_form_dialog
from core.widgets.editor_dialog_controller import EditorDialogController
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_FINDING_INCOMPLETE_WARNING,
    RISK_MEASURE_FINDINGS_TITLE,
    RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
    RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_PRINT_BUTTON,
    RISK_MEASURE_REVIEW_PRINT_STUB_MESSAGE,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewError,
    risk_measure_review_service,
)
from moduly.rizeni_rizik.ui.risk_measure_findings_widget import RiskMeasureFindingsWidget
from moduly.rizeni_rizik.ui.risk_measure_review_checklist_widget import (
    RiskMeasureReviewChecklistWidget,
)


class RiskMeasureReviewExecutionDialog(QDialog):
    """Provedení přezkoumání – checklist a zjištění (oddělené od evidence)."""

    def __init__(self, parent=None, *, review):
        super().__init__(parent)
        self.review = review
        self.setWindowTitle(
            f"{RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE} {review.review_number or ''}".strip()
        )
        configure_resizable_form_dialog(self, width=820, height=720, min_width=680, min_height=560)

        layout = QVBoxLayout(self)

        scope_parts = [review.operation_name or ""]
        if review.workplace_name:
            scope_parts.append(review.workplace_name)
        if review.workplace_part_name:
            scope_parts.append(review.workplace_part_name)
        scope_text = " / ".join(part for part in scope_parts if part)
        header = QLabel(
            f"Číslo: {review.review_number or '—'}\n"
            f"Rozsah: {scope_text or '—'}\n"
            f"Kontrolující: {review.reviewer_person_name or '—'}"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        checklist_page = QWidget()
        checklist_layout = QVBoxLayout(checklist_page)
        checklist_layout.setContentsMargins(0, 8, 0, 0)
        self.checklist = RiskMeasureReviewChecklistWidget(on_changed=self._on_changed)
        checklist_layout.addWidget(self.checklist)
        self.tabs.addTab(checklist_page, RISK_MEASURE_REVIEW_CHECKLIST_TITLE)

        findings_page = QWidget()
        findings_layout = QVBoxLayout(findings_page)
        findings_layout.setContentsMargins(0, 8, 0, 0)
        self.findings = RiskMeasureFindingsWidget(on_changed=self._on_changed)
        findings_layout.addWidget(self.findings)
        self.tabs.addTab(findings_page, RISK_MEASURE_FINDINGS_TITLE)
        layout.addWidget(self.tabs)

        action_row = QHBoxLayout()
        self.print_btn = QPushButton(RISK_MEASURE_REVIEW_PRINT_BUTTON)
        self.print_btn.clicked.connect(self._print_checklist_stub)
        action_row.addWidget(self.print_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        buttons = create_save_cancel_box(self, is_new=False)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=False,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()
        self._wrap_close_with_finding_warning()

        rows = risk_measure_review_service.ensure_checklist(review.id)
        self.checklist.load_rows(rows)
        self.findings.set_review_id(review.id)
        self._editor.capture_baseline()

    def get_data(self) -> dict:
        return {"checklist_updates": self.checklist.get_updates()}

    def _save(self) -> bool:
        data = self.get_data()
        try:
            updated = risk_measure_review_service.update_review(
                self.review.id,
                review_date=self.review.review_date,
                reviewer_person_id=self.review.reviewer_person_id,
                operation_id=self.review.operation_id,
                workplace_id=self.review.workplace_id,
                workplace_part_id=self.review.workplace_part_id,
                status=self.review.status,
                note=self.review.note or "",
                checklist_updates=data["checklist_updates"],
            )
            if updated is None:
                QMessageBox.warning(
                    self,
                    RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
                    "Přezkoumání nebylo nalezeno.",
                )
                return False
            self.review = updated
            self.checklist.load_rows(
                risk_measure_review_service.list_checklist_rows(updated.id)
            )
            self.findings.set_review_id(updated.id)
        except RiskMeasureReviewError as error:
            QMessageBox.warning(
                self,
                RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
                str(error),
            )
            return False
        self._warn_incomplete_findings()
        return True

    def _print_checklist_stub(self) -> None:
        QMessageBox.information(
            self,
            RISK_MEASURE_REVIEW_PRINT_BUTTON,
            RISK_MEASURE_REVIEW_PRINT_STUB_MESSAGE,
        )

    def _on_changed(self) -> None:
        if hasattr(self, "_editor"):
            self._editor.mark_dirty()

    def _wrap_close_with_finding_warning(self) -> None:
        original = self._editor.request_close

        def request_close_with_warning() -> bool:
            if not self._editor.is_dirty():
                self._warn_incomplete_findings()
                return True
            return original()

        self._editor.request_close = request_close_with_warning  # type: ignore[method-assign]

    def _warn_incomplete_findings(self) -> None:
        incomplete = risk_measure_review_service.list_incomplete_findings(self.review.id)
        if not incomplete:
            return
        numbers = ", ".join(finding.note_number for finding in incomplete)
        QMessageBox.information(
            self,
            RISK_MEASURE_FINDINGS_TITLE,
            f"{RISK_MEASURE_FINDING_INCOMPLETE_WARNING}\n\nČísla: {numbers}",
        )
