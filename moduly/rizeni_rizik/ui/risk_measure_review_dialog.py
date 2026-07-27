from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import create_save_cancel_box, configure_resizable_form_dialog
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.person_selector import PersonSelector
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_FINDING_INCOMPLETE_WARNING,
    RISK_MEASURE_FINDINGS_TITLE,
    RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
    RISK_MEASURE_REVIEW_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_LABELS,
    RISK_MEASURE_REVIEW_STATUSES,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewError,
    risk_measure_review_service,
)
from moduly.rizeni_rizik.ui.risk_measure_review_checklist_widget import (
    RiskMeasureReviewChecklistWidget,
)
from moduly.rizeni_rizik.ui.risk_measure_findings_widget import RiskMeasureFindingsWidget


class RiskMeasureReviewDialog(QDialog):
    def __init__(self, parent=None, review=None):
        super().__init__(parent)
        self.review = review
        self.setWindowTitle(RISK_MEASURE_REVIEW_DIALOG_TITLE)
        configure_resizable_form_dialog(self, width=760, height=760, min_width=640, min_height=580)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number_label = QLabel("—")
        self.review_date = DateEdit()
        self.reviewer = PersonSelector(
            include_empty=True,
            allow_custom_value=False,
            allow_add_new=True,
        )
        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()
        self.status = QComboBox()
        for status in RISK_MEASURE_REVIEW_STATUSES:
            self.status.addItem(RISK_MEASURE_REVIEW_STATUS_LABELS[status], status)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(50)

        form.addRow("Číslo přezkoumání:", self.number_label)
        form.addRow("Datum *:", self.review_date)
        form.addRow("Kontrolující *:", self.reviewer)
        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        form.addRow("Stav:", self.status)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form)

        self.tabs = QTabWidget()
        checklist_page = QWidget()
        checklist_layout = QVBoxLayout(checklist_page)
        checklist_layout.setContentsMargins(0, 8, 0, 0)
        self.checklist = RiskMeasureReviewChecklistWidget(
            on_changed=self._on_checklist_changed,
            on_note_number_committed=self._on_note_number_committed,
        )
        checklist_layout.addWidget(self.checklist)
        self.tabs.addTab(checklist_page, RISK_MEASURE_REVIEW_CHECKLIST_TITLE)

        findings_page = QWidget()
        findings_layout = QVBoxLayout(findings_page)
        findings_layout.setContentsMargins(0, 8, 0, 0)
        self.findings = RiskMeasureFindingsWidget(on_changed=self._on_findings_changed)
        findings_layout.addWidget(self.findings)
        self.tabs.addTab(findings_page, RISK_MEASURE_FINDINGS_TITLE)
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self, is_new=review is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=review is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()
        self._wrap_close_with_finding_warning()

        self.operation.currentIndexChanged.connect(self._on_operation_changed)
        self.workplace.currentIndexChanged.connect(self._on_workplace_changed)

        self._reload_operations()
        self._reset_workplaces()
        self._reset_workplace_parts()

        if review is not None:
            self.number_label.setText(review.review_number or "—")
            if review.review_date:
                self.review_date.setDate(
                    QDate(review.review_date.year, review.review_date.month, review.review_date.day)
                )
            self.reviewer.set_person_id(review.reviewer_person_id)
            self._select_combo(self.operation, review.operation_id)
            self._reload_workplaces(review.operation_id, preserve_id=review.workplace_id)
            self._select_combo(self.workplace, review.workplace_id)
            self._reload_workplace_parts(
                review.workplace_id,
                preserve_id=review.workplace_part_id,
            )
            self._select_combo(self.workplace_part, review.workplace_part_id)
            status_index = self.status.findData(review.status)
            if status_index >= 0:
                self.status.setCurrentIndex(status_index)
            elif review.status not in RISK_MEASURE_REVIEW_STATUSES:
                self.status.setCurrentIndex(
                    self.status.findData(RISK_MEASURE_REVIEW_STATUS_DRAFT)
                )
            self.note.setPlainText(review.note or "")
            self._set_scope_editable(False)
            self.checklist.load_rows(
                risk_measure_review_service.list_checklist_rows(review.id)
            )
            self.findings.set_review_id(review.id)
        else:
            self.number_label.setText(risk_measure_review_service.preview_next_number())
            self.status.setCurrentIndex(self.status.findData(RISK_MEASURE_REVIEW_STATUS_DRAFT))
            self.checklist.load_rows([])
            self.findings.set_review_id(None)

        self._editor.capture_baseline()

    def get_data(self) -> dict:
        qdate = self.review_date.date()
        return {
            "review_date": date(qdate.year(), qdate.month(), qdate.day()),
            "reviewer_person_id": self.reviewer.current_person_id(),
            "operation_id": self.operation.currentData(),
            "workplace_id": self.workplace.currentData(),
            "workplace_part_id": self.workplace_part.currentData(),
            "status": self.status.currentData() or RISK_MEASURE_REVIEW_STATUS_DRAFT,
            "note": self.note.toPlainText().strip(),
            "checklist_updates": self.checklist.get_updates(),
        }

    def _save(self) -> bool:
        data = self.get_data()
        checklist_updates = data.pop("checklist_updates", [])
        try:
            if self.review is None:
                created = risk_measure_review_service.create_review(**data)
                self.review = created
                self.number_label.setText(created.review_number or "—")
                self._set_scope_editable(False)
                self.checklist.load_rows(
                    risk_measure_review_service.list_checklist_rows(created.id)
                )
                self.findings.set_review_id(created.id)
            else:
                updated = risk_measure_review_service.update_review(
                    self.review.id,
                    checklist_updates=checklist_updates,
                    **data,
                )
                if updated is None:
                    QMessageBox.warning(
                        self,
                        RISK_MEASURE_REVIEW_DIALOG_TITLE,
                        "Přezkoumání nebylo nalezeno.",
                    )
                    return False
                self.review = updated
                self.checklist.load_rows(
                    risk_measure_review_service.list_checklist_rows(updated.id)
                )
                self.findings.set_review_id(updated.id)
        except RiskMeasureReviewError as error:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_DIALOG_TITLE, str(error))
            return False

        self._warn_incomplete_findings()
        return True

    def _wrap_close_with_finding_warning(self) -> None:
        original = self._editor.request_close

        def request_close_with_warning() -> bool:
            if not self._editor.is_dirty():
                self._warn_incomplete_findings()
                return True
            return original()

        self._editor.request_close = request_close_with_warning  # type: ignore[method-assign]

    def _warn_incomplete_findings(self) -> None:
        if self.review is None:
            return
        incomplete = risk_measure_review_service.list_incomplete_findings(self.review.id)
        if not incomplete:
            return
        numbers = ", ".join(finding.note_number for finding in incomplete)
        QMessageBox.information(
            self,
            RISK_MEASURE_FINDINGS_TITLE,
            f"{RISK_MEASURE_FINDING_INCOMPLETE_WARNING}\n\nČísla: {numbers}",
        )

    def _on_checklist_changed(self) -> None:
        if hasattr(self, "_editor"):
            self._editor.mark_dirty()

    def _on_findings_changed(self) -> None:
        if hasattr(self, "_editor"):
            self._editor.mark_dirty()

    def _on_note_number_committed(self, note_number: str) -> None:
        if self.review is None:
            return
        normalized = (note_number or "").strip()
        if not normalized:
            return
        # Nejprve uložit aktuální checklist hodnoty, aby vazba existovala v DB.
        data = self.get_data()
        checklist_updates = data.pop("checklist_updates", [])
        try:
            risk_measure_review_service.update_review(
                self.review.id,
                checklist_updates=checklist_updates,
                review_date=data["review_date"],
                reviewer_person_id=data["reviewer_person_id"],
                operation_id=data["operation_id"],
                workplace_id=data["workplace_id"],
                workplace_part_id=data["workplace_part_id"],
                status=data["status"],
                note=data["note"],
            )
        except RiskMeasureReviewError:
            return
        finding = risk_measure_review_service.ensure_finding_for_note_number(
            self.review.id,
            normalized,
        )
        self.findings.refresh()
        if finding is not None:
            self.findings.open_by_note_number(finding.note_number)
        if hasattr(self, "_editor"):
            self._editor.capture_baseline()

    def _set_scope_editable(self, editable: bool) -> None:
        self.operation.setEnabled(editable)
        self.workplace.setEnabled(editable)
        self.workplace_part.setEnabled(editable)

    def _on_operation_changed(self) -> None:
        if self.review is not None:
            return
        self._reload_workplaces(self.operation.currentData())
        self._reset_workplace_parts()

    def _on_workplace_changed(self) -> None:
        if self.review is not None:
            return
        self._reload_workplace_parts(self.workplace.currentData())

    def _reload_operations(self, *, preserve_id: int | None = None) -> None:
        self._populate_combo(
            self.operation,
            risk_measure_review_service.get_active_operations(include_inactive=True),
            preserve_id=preserve_id,
            required=True,
        )

    def _reload_workplaces(
        self,
        operation_id: int | None,
        *,
        preserve_id: int | None = None,
    ) -> None:
        workplaces = risk_measure_review_service.get_workplaces_for_operation(
            operation_id,
            include_inactive=True,
        )
        self._populate_combo(
            self.workplace,
            workplaces,
            preserve_id=preserve_id,
            required=False,
        )

    def _reload_workplace_parts(
        self,
        workplace_id: int | None,
        *,
        preserve_id: int | None = None,
    ) -> None:
        parts = risk_measure_review_service.get_workplace_parts_for_workplace(
            workplace_id,
            include_inactive=True,
        )
        self._populate_combo(
            self.workplace_part,
            parts,
            preserve_id=preserve_id,
            required=False,
        )

    def _reset_workplaces(self) -> None:
        self._populate_combo(self.workplace, [], required=False)

    def _reset_workplace_parts(self) -> None:
        self._populate_combo(self.workplace_part, [], required=False)

    def _populate_combo(
        self,
        combo: QComboBox,
        items: list,
        *,
        preserve_id: int | None = None,
        required: bool,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        if not required:
            combo.addItem("—", None)
        for item in items:
            combo.addItem(item.name, item.id)
        if preserve_id is not None:
            self._select_combo(combo, preserve_id)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    @staticmethod
    def _select_combo(combo: QComboBox, value) -> None:
        if value is None:
            index = combo.findData(None)
            if index >= 0:
                combo.setCurrentIndex(index)
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
