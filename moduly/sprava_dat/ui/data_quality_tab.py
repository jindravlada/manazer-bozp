"""Záložka Kvalita dat — vstupní bod pro kontroly kvality databáze."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.ui.similarity_analysis_dialog import (
    SCOPE_PROVERKY,
    SIMILARITY_SCOPE_DEFS,
    SimilarityAnalysisDialog,
)
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
            "Analýza může u většího množství dat trvat několik minut."
        )
        description.setWordWrap(True)
        description.setObjectName("InfoText")
        layout.addWidget(description)

        form = QFormLayout()
        self._scope_checks: dict[str, QCheckBox] = {}
        for key, label, implemented in SIMILARITY_SCOPE_DEFS:
            check = QCheckBox(label)
            check.setChecked(implemented)
            check.setEnabled(implemented)
            if not implemented:
                check.setToolTip("Připraveno pro budoucí rozšíření.")
            self._scope_checks[key] = check
            form.addRow(check)
        layout.addLayout(form)

        self._show_checked = QCheckBox("Zobrazit již zkontrolované dvojice")
        self._show_checked.setChecked(False)
        layout.addWidget(self._show_checked)

        buttons = QHBoxLayout()
        self.start_analysis_btn = QPushButton("Spustit analýzu")
        self.start_analysis_btn.clicked.connect(self._start_similarity_analysis)
        buttons.addWidget(self.start_analysis_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        return group

    def _start_similarity_analysis(self) -> None:
        if not self._scope_checks[SCOPE_PROVERKY].isChecked():
            QMessageBox.information(
                self,
                "Analýza podobností",
                "V tomto sprintu je implementována pouze oblast "
                "„Kontrolní otázky prověrek“.",
            )
            return

        dialog = SimilarityAnalysisDialog(
            self,
            include_checked=self._show_checked.isChecked(),
            auto_start=True,
        )
        dialog.exec()
