from datetime import date

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.proverky.constants import (
    INSPECTION_COMPLETION_CONFIRM_MESSAGE,
    INSPECTION_STATUS_DOKONCENO,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


class BozpInspectionConclusionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.inspection = None
        self._on_complete = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Závěr prověrky bude dostupný až po uložení prověrky.")
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

        completion_group = QGroupBox("Dokončení prověrky")
        completion_form = QFormLayout(completion_group)
        self.status_label = QLabel("—")
        self.status_label.setObjectName("InfoText")
        self.finished_at_edit = NullableDateEdit()
        completion_form.addRow("Stav prověrky:", self.status_label)
        completion_form.addRow("Datum ukončení:", self.finished_at_edit)
        layout.addWidget(completion_group)

        self.complete_btn = QPushButton("Dokončit prověrku")
        self.complete_btn.clicked.connect(self._complete_inspection)
        layout.addWidget(self.complete_btn)

        layout.addStretch()

        self._update_state()

    def set_complete_handler(self, handler) -> None:
        self._on_complete = handler

    def load_inspection(self, inspection) -> None:
        self.inspection = inspection
        self.refresh()

    def refresh(self) -> None:
        inspection_id = self.inspection.id if self.inspection is not None else None
        self._update_state()

        if inspection_id is None:
            self.status_label.setText("—")
            self.finished_at_edit.clear_date()
            self.findings_total_label.setText("0")
            self.findings_open_label.setText("0")
            self.tasks_total_label.setText("0")
            self.tasks_active_label.setText("0")
            return

        summary = bozp_inspection_service.get_conclusion_summary(inspection_id)
        self.findings_total_label.setText(str(summary["findings_total"]))
        self.findings_open_label.setText(str(summary["findings_open"]))
        self.tasks_total_label.setText(str(summary["tasks_total"]))
        self.tasks_active_label.setText(str(summary["tasks_active"]))

        status = getattr(self.inspection, "status", None) or "—"
        self.status_label.setText(status)

        finished_at = getattr(self.inspection, "finished_at", None)
        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)
        else:
            self.finished_at_edit.clear_date()

        is_completed = status == INSPECTION_STATUS_DOKONCENO
        self.complete_btn.setEnabled(not is_completed)
        self.finished_at_edit.setEnabled(not is_completed)

    def get_data(self) -> dict:
        result: dict = {
            "finished_at": self.finished_at_edit.get_date(),
        }
        if self.inspection is not None and getattr(self.inspection, "status", None):
            result["status"] = self.inspection.status
        return result

    def _update_state(self) -> None:
        enabled = self.inspection is not None and self.inspection.id is not None
        self.info_label.setVisible(not enabled)

    def _complete_inspection(self) -> None:
        if self.inspection is None or self.inspection.id is None:
            QMessageBox.information(self, "Závěr", "Prověrku je nutné nejdříve uložit.")
            return

        inspection_id = self.inspection.id
        blockers = bozp_inspection_service.get_completion_blockers(inspection_id)
        if blockers.has_blockers():
            answer = QMessageBox.question(
                self,
                "Dokončení prověrky",
                INSPECTION_COMPLETION_CONFIRM_MESSAGE,
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

        saved = self._on_complete(
            status=INSPECTION_STATUS_DOKONCENO,
            finished_at=finished_at,
        )
        if saved:
            self.refresh()
