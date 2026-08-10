"""Dialog pro přesun řídicího procesu mezi návštěvami."""

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QVBoxLayout

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.editor_dialog_controller import EditorDialogController
from moduly.audity.constants import (
    AUDIT_PROGRAM_MOVE_PROCESS_DIALOG_TITLE,
    AUDIT_PROGRAM_VISIT_SKIPPED_SUFFIX,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
    MONTH_NAMES_CAPITALIZED,
)
from moduly.audity.modely.audit_program import AuditProgramVisit, AuditProgramVisitProcess
from moduly.audity.sluzby.audit_program_service import audit_program_service


def format_visit_label(visit: AuditProgramVisit) -> str:
    month = visit.planned_month or 0
    year = visit.planned_year or 0
    if 1 <= month <= 12:
        label = f"{MONTH_NAMES_CAPITALIZED[month - 1]} {year}"
    else:
        label = f"{month}/{year}"
    if visit.planned_date is not None:
        label = f"{label} ({visit.planned_date.strftime('%d.%m.%Y')})"
    return label


class AuditProgramMoveProcessDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        visit_process: AuditProgramVisitProcess,
        visits: list[AuditProgramVisit],
    ):
        super().__init__(parent)

        self._visit_process = visit_process
        self.setWindowTitle(AUDIT_PROGRAM_MOVE_PROCESS_DIALOG_TITLE)
        self.resize(460, 180)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        process_label = visit_process.process_name or visit_process.process_id
        form.addRow("Proces:", QLabel(process_label))

        self._visit_combo = QComboBox()
        for visit in visits:
            if visit.id == visit_process.visit_id:
                continue
            label = format_visit_label(visit)
            if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
                label = f"{label} {AUDIT_PROGRAM_VISIT_SKIPPED_SUFFIX}"
            self._visit_combo.addItem(label, visit.id)

        form.addRow("Cílová návštěva:", self._visit_combo)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self, is_new=True)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=True,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(lambda: self.target_visit_id())
        self._editor.install_auto_dirty_tracking()
        self._editor.capture_baseline()

    def accept(self) -> None:
        if self._visit_combo.count() == 0:
            return
        super().accept()

    def target_visit_id(self) -> int | None:
        if self._visit_combo.count() == 0:
            return None
        return int(self._visit_combo.currentData())


def load_target_visits(
    program_id: int,
    *,
    workplace_id: int | None,
    current_visit_id: int,
) -> list[AuditProgramVisit]:
    return [
        visit
        for visit in audit_program_service.list_workplace_visits(
            program_id,
            workplace_id,
            include_skipped=False,
        )
        if visit.id != current_visit_id
    ]
