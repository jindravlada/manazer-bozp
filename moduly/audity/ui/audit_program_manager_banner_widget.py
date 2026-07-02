"""Informační banner Manažera auditů na hlavní stránce modulu Audity."""

from PySide6.QtCore import Signal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from moduly.audity.constants import (
    AUDIT_PROGRAM_MANAGER_BANNER_TITLE,
    AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT,
    AUDIT_PROGRAM_MANAGER_OPEN_BUTTON,
)
from moduly.audity.sluzby.audit_program_service import (
    AuditProgramBannerInfo,
    audit_program_service,
)


class AuditProgramManagerBannerWidget(QFrame):
    open_manager_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AuditProgramManagerBanner")

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        content = QVBoxLayout()
        content.setSpacing(4)

        self._title_label = QLabel(AUDIT_PROGRAM_MANAGER_BANNER_TITLE)
        self._title_label.setObjectName("AuditProgramManagerBannerTitle")
        content.addWidget(self._title_label)

        self._detail_label = QLabel()
        self._detail_label.setObjectName("InfoText")
        self._detail_label.setWordWrap(True)
        content.addWidget(self._detail_label)

        root.addLayout(content, 1)

        self._open_btn = QPushButton(AUDIT_PROGRAM_MANAGER_OPEN_BUTTON)
        self._open_btn.clicked.connect(self.open_manager_requested.emit)
        root.addWidget(self._open_btn, 0, Qt.AlignmentFlag.AlignTop)

    def refresh(self) -> None:
        self.load_info(audit_program_service.get_banner_info())

    def load_info(self, info: AuditProgramBannerInfo) -> None:
        if not info.has_program:
            self._detail_label.setText(AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT)
            return

        lines = [
            f"Aktivní program: {info.program_name or '—'}",
            f"Období: {info.period_label}",
        ]
        if info.completion_percent is not None:
            lines.append(f"Plnění: {info.completion_percent:.0f} %")

        if info.nearest_visit_term and info.nearest_visit_workplace:
            lines.append(
                f"Nejbližší návštěva: {info.nearest_visit_term} · "
                f"{info.nearest_visit_workplace}"
            )
        elif info.nearest_visit_term:
            lines.append(f"Nejbližší návštěva: {info.nearest_visit_term}")
        else:
            lines.append("Nejbližší návštěva: —")

        self._detail_label.setText("\n".join(lines))
