"""Read-only záložka Stav procesu — výsledky auditů a prověrek řídicího procesu."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
    LegalRequirementProcessAuditStatus,
    LegalRequirementProcessInspectionStatus,
    legal_requirement_process_status_service,
)

_UNSAVED_STATUS_TEXT = "Stav procesu bude dostupný až po uložení procesu."


class LegalRequirementProcessStatusWidget(QWidget):
    def __init__(self, requirement_id: int | None = None, parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Stav procesu")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading.setFont(heading_font)
        self._layout.addWidget(heading)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        self.refresh()

    def refresh(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self.requirement_id is None:
            self._layout.addWidget(QLabel(_UNSAVED_STATUS_TEXT))
            self._layout.addStretch()
            return

        audit_status = legal_requirement_process_status_service.get_audit_status(
            self.requirement_id,
        )
        self._render_audit_section(audit_status)

        inspection_status = legal_requirement_process_status_service.get_inspection_status(
            self.requirement_id,
        )
        self._render_inspection_section(inspection_status)

        self._layout.addStretch()

    def _render_audit_section(self, status: LegalRequirementProcessAuditStatus) -> None:
        self._add_section_heading("Audity")
        empty_message = status.empty_message
        if empty_message:
            self._layout.addWidget(QLabel(empty_message))
            return

        date_text = (
            status.last_audit_date.strftime("%d.%m.%Y")
            if status.last_audit_date is not None
            else "—"
        )
        self._layout.addWidget(QLabel(f"Poslední dokončený audit: {date_text}"))
        self._layout.addWidget(QLabel(f"Audit: {status.last_audit_label or '—'}"))
        self._layout.addWidget(
            QLabel(f"Hodnocená auditní tvrzení procesu: {status.evaluated_count}"),
        )
        self._add_section_heading("Výsledky hodnocení")
        for item in status.result_counts:
            self._layout.addWidget(QLabel(f"• {item.result_label}: {item.count}"))

    def _render_inspection_section(
        self,
        status: LegalRequirementProcessInspectionStatus,
    ) -> None:
        self._add_section_heading("Prověrky")
        empty_message = status.empty_message
        if empty_message:
            self._layout.addWidget(QLabel(empty_message))
            return

        date_text = (
            status.last_inspection_date.strftime("%d.%m.%Y")
            if status.last_inspection_date is not None
            else "—"
        )
        self._layout.addWidget(QLabel(f"Poslední dokončená prověrka: {date_text}"))
        self._layout.addWidget(QLabel(f"Prověrka: {status.last_inspection_label or '—'}"))
        self._layout.addWidget(
            QLabel(f"Hodnocené kontrolní otázky procesu: {status.evaluated_count}"),
        )
        self._add_section_heading("Výsledky hodnocení")
        for item in status.result_counts:
            self._layout.addWidget(QLabel(f"• {item.result_label}: {item.count}"))
        self._layout.addWidget(QLabel(f"Zjištění z otázek procesu: {status.findings_total}"))
        self._layout.addWidget(
            QLabel(f"Z toho otevřená zjištění: {status.findings_open}"),
        )

    def _add_section_heading(self, title: str) -> None:
        section_heading = QLabel(title)
        section_font = QFont(section_heading.font())
        section_font.setBold(True)
        section_heading.setFont(section_font)
        self._layout.addWidget(section_heading)
