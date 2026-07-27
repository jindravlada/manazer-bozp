from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
    instance_backup_workflow_service,
)
from moduly.sprava_dat.ui.ui_styles import apply_card_group_style


class BackupTab(QWidget):
    """Záložka úplné zálohy a obnovy (*.mbbackup)."""

    def __init__(
        self,
        on_status_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_status_changed = on_status_changed
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

        layout.addWidget(self._create_backup_card())
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _create_backup_card(self) -> QGroupBox:
        group = QGroupBox("Úplná záloha Manažera BOZP (*.mbbackup)")
        apply_card_group_style(group)
        layout = QVBoxLayout(group)

        description = QLabel(
            "Záloha obsahuje databázi, přílohy, fotografie, číselníky, šablony, "
            "konfiguraci a uživatelská nastavení."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.recovery_status_label = QLabel()
        self.recovery_status_label.setWordWrap(True)
        layout.addWidget(self.recovery_status_label)

        buttons = QHBoxLayout()
        self.create_mbbackup_button = QPushButton("Vytvořit zálohu")
        self.create_mbbackup_button.clicked.connect(self._create_instance_backup)
        buttons.addWidget(self.create_mbbackup_button)

        self.verify_mbbackup_button = QPushButton("Ověřit zálohu")
        self.verify_mbbackup_button.clicked.connect(self._verify_instance_backup)
        buttons.addWidget(self.verify_mbbackup_button)

        self.restore_mbbackup_button = QPushButton("Obnovit ze zálohy")
        self.restore_mbbackup_button.clicked.connect(self._restore_instance_backup)
        buttons.addWidget(self.restore_mbbackup_button)

        self.recovery_diag_button = QPushButton("Diagnostika obnovy")
        self.recovery_diag_button.clicked.connect(self._show_recovery_diagnostics)
        buttons.addWidget(self.recovery_diag_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        note = QLabel(
            "Obnova nahradí současná pracovní data. Před obnovou se záloha vždy ověří. "
            "Po úspěšné obnově je nutný restart aplikace."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def refresh(self) -> None:
        self._update_recovery_status()

    def _update_recovery_status(self) -> None:
        markers = instance_backup_workflow_service.refresh_recovery_markers()
        blocked = instance_backup_workflow_service.restore_blocked
        self.restore_mbbackup_button.setEnabled(not blocked)
        if blocked:
            self.recovery_status_label.setText(
                "⚠ Nedokončená obnova: další obnova je zakázána. "
                f"Markerů: {len(markers)}. Použijte Diagnostiku obnovy."
            )
            self.recovery_status_label.setStyleSheet("color: #a40000; font-weight: 600;")
        else:
            self.recovery_status_label.setText(
                "Stav obnovy: v pořádku (žádný recovery marker)."
            )
            self.recovery_status_label.setStyleSheet("")

    def _notify_status_changed(self) -> None:
        if self._on_status_changed is not None:
            self._on_status_changed()
        else:
            self.refresh()

    def _create_instance_backup(self) -> None:
        if instance_backup_workflow_service.create_instance_backup_ui(self):
            self._notify_status_changed()
        else:
            self.refresh()

    def _verify_instance_backup(self) -> None:
        instance_backup_workflow_service.verify_instance_backup_ui(self)

    def _restore_instance_backup(self) -> None:
        instance_backup_workflow_service.restore_instance_backup_ui(self)
        self.refresh()

    def _show_recovery_diagnostics(self) -> None:
        instance_backup_workflow_service.show_recovery_diagnostics(self)
        self.refresh()
