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
    QVBoxLayout,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import create_save_cancel_box, configure_resizable_form_dialog
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_LABELS,
    RISK_MEASURE_REVIEW_STATUSES,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewError,
    resolve_current_thp_worker_id,
    risk_measure_review_service,
)


class RiskMeasureReviewDialog(QDialog):
    """Evidence přezkoumání – pouze hlavička (bez checklistu)."""

    def __init__(
        self,
        parent=None,
        review=None,
        *,
        current_thp_worker_id: int | None = None,
    ):
        super().__init__(parent)
        self.review = review
        self.setWindowTitle(RISK_MEASURE_REVIEW_DIALOG_TITLE)
        configure_resizable_form_dialog(self, width=560, height=420, min_width=480, min_height=360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number_label = QLabel("—")
        self.review_date = DateEdit()
        self.reviewer = ThpWorkerSelector(
            include_empty=True,
            allow_custom_value=False,
        )
        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()
        self.status = QComboBox()
        for status in RISK_MEASURE_REVIEW_STATUSES:
            self.status.addItem(RISK_MEASURE_REVIEW_STATUS_LABELS[status], status)
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(80)

        form.addRow("Číslo revize:", self.number_label)
        form.addRow("Datum *:", self.review_date)
        form.addRow("Kontrolující *:", self.reviewer)
        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        form.addRow("Stav:", self.status)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form)

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
        else:
            self.number_label.setText(risk_measure_review_service.preview_next_number())
            self.status.setCurrentIndex(self.status.findData(RISK_MEASURE_REVIEW_STATUS_DRAFT))
            self._prefill_reviewer(current_thp_worker_id)

        self._editor.capture_baseline()

    def _prefill_reviewer(self, current_thp_worker_id: int | None) -> None:
        worker_id = current_thp_worker_id
        if worker_id is None:
            worker_id = resolve_current_thp_worker_id()
        if worker_id is not None:
            self.reviewer.set_person_id(worker_id)

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
        }

    def _save(self) -> bool:
        data = self.get_data()
        try:
            if self.review is None:
                created = risk_measure_review_service.create_review(**data)
                self.review = created
                self.number_label.setText(created.review_number or "—")
                self._set_scope_editable(False)
            else:
                updated = risk_measure_review_service.update_review(
                    self.review.id,
                    **data,
                )
                if updated is None:
                    QMessageBox.warning(
                        self,
                        RISK_MEASURE_REVIEW_DIALOG_TITLE,
                        "Revize nebyla nalezena.",
                    )
                    return False
                self.review = updated
        except RiskMeasureReviewError as error:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_DIALOG_TITLE, str(error))
            return False
        return True

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
