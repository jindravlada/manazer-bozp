from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

SECTION_BACKUP = "Zálohování"
SECTION_TRANSFER = "Přenos dat a konfigurace"
SECTION_DIAGNOSTICS = "Diagnostika"


class SpravaDatPage(QWidget):
    """Servisní stránka pro správu dat aplikace."""

    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("Správa dat")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        layout.addWidget(self._backup_section())
        layout.addWidget(self._transfer_section())
        layout.addWidget(self._diagnostics_section())
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _backup_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_BACKUP)
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Kompletní záloha programu"))
        group_layout.addWidget(QLabel("Obnova kompletní zálohy"))
        return group

    def _transfer_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_TRANSFER)
        group_layout = QVBoxLayout(group)
        for item in (
            "Číselníky",
            "Registr právních požadavků",
            "Metodiky auditů",
            "Metodiky prověrek",
        ):
            group_layout.addWidget(QLabel(f"• {item}"))
        return group

    def _diagnostics_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_DIAGNOSTICS)
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Diagnostika registru právních požadavků"))
        return group
