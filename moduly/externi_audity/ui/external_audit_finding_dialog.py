"""Editor položky zjištění externího auditu (Neshoda / PKZ / Silná stránka)."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_FINDING_STATUS_LABELS,
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
    EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
    EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
    format_display_date,
)
from moduly.externi_audity.sluzby.external_audit_service import (
    ExternalAuditError,
    normalize_finding_draft_fields,
)


class ExternalAuditFindingDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        finding_type: str,
        title: str,
        description: str = "",
        status: str | None = None,
        due_date: date | None = None,
        resolution_text: str | None = None,
        resolved_at: datetime | None = None,
    ):
        super().__init__(parent)
        self._finding_type = finding_type
        self._is_strength = finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH
        self._previous_status = status
        self._previous_resolved_at = resolved_at
        self.setWindowTitle(title)
        configure_resizable_form_dialog(
            self, width=640, height=520, min_width=480, min_height=360
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.description_edit = QTextEdit()
        self.description_edit.setPlainText(description or "")
        self.description_edit.setMinimumHeight(120)
        form.addRow(
            "Text silné stránky:" if self._is_strength else "Text zjištění:",
            self.description_edit,
        )

        self.status_combo = QComboBox()
        if self._is_strength:
            self.status_combo.addItem(
                EXTERNAL_AUDIT_FINDING_STATUS_LABELS[
                    EXTERNAL_AUDIT_FINDING_STATUS_RECORDED
                ],
                EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
            )
            self.status_combo.setEnabled(False)
        else:
            for value in (
                EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
                EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            ):
                self.status_combo.addItem(
                    EXTERNAL_AUDIT_FINDING_STATUS_LABELS[value], value
                )
            index = self.status_combo.findData(
                status or EXTERNAL_AUDIT_FINDING_STATUS_OPEN
            )
            self.status_combo.setCurrentIndex(index if index >= 0 else 0)
            self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        form.addRow("Stav:", self.status_combo)

        self.due_date_edit = NullableDateEdit()
        self.due_date_edit.set_date_value(due_date)
        self.resolution_edit = QTextEdit()
        self.resolution_edit.setPlainText(resolution_text or "")
        self.resolution_edit.setMinimumHeight(80)
        self.resolved_at_label = QLabel(format_display_date(resolved_at))

        if not self._is_strength:
            form.addRow("Termín vypořádání:", self.due_date_edit)
            form.addRow("Způsob vypořádání:", self.resolution_edit)
            form.addRow("Datum vypořádání:", self.resolved_at_label)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Zrušit")
        save_btn = QPushButton("Uložit")
        cancel_btn.setAutoDefault(False)
        save_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._on_accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        self._result: dict | None = None
        self._on_status_changed()

    def _on_status_changed(self) -> None:
        if self._is_strength:
            return
        # Jen vizuální nápověda – validace při accept
        is_resolved = (
            self.status_combo.currentData() == EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED
        )
        self.resolution_edit.setPlaceholderText(
            "Povinné při stavu Vypořádáno" if is_resolved else ""
        )

    def _on_accept(self) -> None:
        try:
            normalized = normalize_finding_draft_fields(
                finding_type=self._finding_type,
                description=self.description_edit.toPlainText(),
                status=str(self.status_combo.currentData() or ""),
                due_date=None if self._is_strength else self.due_date_edit.get_date(),
                resolution_text=(
                    None if self._is_strength else self.resolution_edit.toPlainText()
                ),
                previous_status=self._previous_status,
                previous_resolved_at=self._previous_resolved_at,
            )
        except ExternalAuditError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._result = normalized
        self.accept()

    def get_data(self) -> dict | None:
        return self._result
