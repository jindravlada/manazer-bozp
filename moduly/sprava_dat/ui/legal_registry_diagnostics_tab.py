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
from moduly.sprava_dat.ui.process_requirements_developer_actions import (
    confirm_and_delete_all_process_requirements,
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

        developer_group = QGroupBox("Vývojářské operace")
        apply_card_group_style(developer_group)
        developer_layout = QVBoxLayout(developer_group)

        developer_info = QLabel(
            "Nebezpečné servisní operace určené pouze pro vývoj a testování. "
            "Běžný uživatel by je neměl spouštět."
        )
        developer_info.setWordWrap(True)
        developer_layout.addWidget(developer_info)

        self.delete_processes_button = QPushButton("Smazat všechny řídicí procesy")
        self.delete_processes_button.clicked.connect(self._delete_all_process_requirements)
        developer_layout.addWidget(self.delete_processes_button)

        layout.addWidget(developer_group)
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

    def _delete_all_process_requirements(self) -> None:
        confirm_and_delete_all_process_requirements(self)
