from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)
from core.shared.finding_display import finding_status_label


class FindingSummaryPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FindingSummaryPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.separator_top = QLabel("─" * 40)
        self.total_label = QLabel("Zjištění: 0")
        self.resolved_label = QLabel()
        self.in_progress_label = QLabel()
        self.open_label = QLabel()
        self.separator_bottom = QLabel("─" * 40)

        for label in (
            self.separator_top,
            self.total_label,
            self.resolved_label,
            self.in_progress_label,
            self.open_label,
            self.separator_bottom,
        ):
            label.setWordWrap(True)

        layout.addWidget(self.separator_top)
        layout.addWidget(self.total_label)
        layout.addWidget(self.resolved_label)
        layout.addWidget(self.in_progress_label)
        layout.addWidget(self.open_label)
        layout.addWidget(self.separator_bottom)

        self.update_summary({})

    def update_summary(self, summary: dict) -> None:
        total = int(summary.get("total", 0))
        resolved = int(summary.get(FINDING_STATUS_VYPORADANO, 0))
        in_progress = int(summary.get(FINDING_STATUS_V_PROCESU, 0))
        open_count = int(summary.get(FINDING_STATUS_OTEVRENE, 0))

        self.total_label.setText(f"Zjištění: {total}")
        self.resolved_label.setText(
            f"🟢 {finding_status_label(FINDING_STATUS_VYPORADANO)}: {resolved}"
        )
        self.in_progress_label.setText(
            f"🟠 {finding_status_label(FINDING_STATUS_V_PROCESU)}: {in_progress}"
        )
        self.open_label.setText(
            f"🔴 {finding_status_label(FINDING_STATUS_OTEVRENE)}: {open_count}"
        )
