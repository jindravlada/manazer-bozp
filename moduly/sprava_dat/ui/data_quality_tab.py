"""Záložka Kvalita dat — vstupní bod pro kontroly kvality databáze."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.ui.similarity_analysis_dialog import SimilarityAnalysisDialog
from moduly.sprava_dat.ui.ui_styles import apply_card_group_style


class DataQualityTab(QWidget):
    """Místo pro budoucí kontroly kvality; zatím jen Analýza podobností."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._create_similarity_section())
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _create_similarity_section(self) -> QGroupBox:
        group = QGroupBox("Analýza podobností")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        description = QLabel(
            "Vyhledá možné duplicitní nebo podobné záznamy v databázi. "
            "Porovnejte jednu oblast sama se sebou, nebo dvě různé oblasti. "
            "Analýza může u většího množství dat trvat několik minut."
        )
        description.setWordWrap(True)
        description.setObjectName("InfoText")
        layout.addWidget(description)

        buttons = QHBoxLayout()
        self.start_analysis_btn = QPushButton("Spustit analýzu")
        self.start_analysis_btn.clicked.connect(self._start_similarity_analysis)
        buttons.addWidget(self.start_analysis_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        return group

    def _start_similarity_analysis(self) -> None:
        dialog = SimilarityAnalysisDialog(self, auto_start=False)
        dialog.exec()
