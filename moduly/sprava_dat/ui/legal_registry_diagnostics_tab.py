from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.ui.legal_registry_diagnostic_actions import (
    show_legal_registry_diagnostic,
)
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    data_management_settings_service,
)
from moduly.sprava_dat.ui.ui_styles import apply_card_group_style


class LegalRegistryDiagnosticsTab(QWidget):
    """Diagnostika registru právních požadavků ve Správě dat."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        group = QGroupBox("Diagnostika registru právních požadavků")
        apply_card_group_style(group)
        group_layout = QVBoxLayout(group)

        description = QLabel(
            "Zkontroluje konzistenci Registru právních požadavků a vypíše nalezené problémy."
        )
        description.setWordWrap(True)
        group_layout.addWidget(description)

        self.run_button = QPushButton("Diagnostika registru")
        self.run_button.clicked.connect(self._run_diagnostic)
        group_layout.addWidget(self.run_button)

        self.last_result_label = QLabel()
        self.last_result_label.setWordWrap(True)
        group_layout.addWidget(self.last_result_label)

        layout.addWidget(group)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def refresh(self) -> None:
        diagnostic = data_management_settings_service.get_last_diagnostic()
        if diagnostic is None:
            self.last_result_label.setText("Diagnostika zatím nebyla spuštěna.")
            return

        self.last_result_label.setText(
            "Poslední diagnostika:\n"
            f"• datum a čas: {data_management_settings_service.format_timestamp(diagnostic.get('created_at', ''))}\n"
            f"• výsledek: {diagnostic.get('summary', '—')}"
        )

    def _run_diagnostic(self) -> None:
        show_legal_registry_diagnostic(self)
        self.refresh()
