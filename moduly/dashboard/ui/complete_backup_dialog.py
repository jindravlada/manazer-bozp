"""Potvrzovací dialogy pro kompletní zálohu a obnovu z Dashboardu."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

BACKUP_DIALOG_TITLE = "Kompletní záloha programu"
BACKUP_DIALOG_TEXT = (
    "Bude vytvořena kompletní záloha všech uživatelských dat Manažera BOZP.\n\n"
    "Pokud chcete exportovat pouze určitou část dat, například Registr právních požadavků "
    "nebo číselníky, použijte modul Správa dat."
)

RESTORE_DIALOG_TITLE = "Kompletní obnova programu"
RESTORE_DIALOG_TEXT = (
    "Bude provedena kompletní obnova uživatelských dat Manažera BOZP ze zvolené úplné zálohy.\n\n"
    "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu.\n\n"
    "Pokud chcete importovat pouze určitou oblast dat, například Registr právních požadavků "
    "nebo číselníky, použijte modul Správa dat."
)

ACTION_PROCEED = "proceed"
ACTION_GO_TO_SPRAVA_DAT = "go_to_sprava_dat"
ACTION_CANCEL = "cancel"


class _CompleteOperationDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        text: str,
        proceed_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._action = ACTION_CANCEL
        self.setWindowTitle(title)

        layout = QVBoxLayout(self)

        message = QLabel(text)
        message.setWordWrap(True)
        layout.addWidget(message)

        button_box = QDialogButtonBox()
        proceed_button = button_box.addButton(proceed_label, QDialogButtonBox.ButtonRole.AcceptRole)
        sprava_dat_button = button_box.addButton(
            "Přejít na Správu dat",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        cancel_button = button_box.addButton("Zrušit", QDialogButtonBox.ButtonRole.RejectRole)

        proceed_button.clicked.connect(self._on_proceed)
        sprava_dat_button.clicked.connect(self._on_go_to_sprava_dat)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def action(self) -> str:
        return self._action

    def _on_proceed(self) -> None:
        self._action = ACTION_PROCEED
        self.accept()

    def _on_go_to_sprava_dat(self) -> None:
        self._action = ACTION_GO_TO_SPRAVA_DAT
        self.accept()


class CompleteBackupConfirmDialog(_CompleteOperationDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title=BACKUP_DIALOG_TITLE,
            text=BACKUP_DIALOG_TEXT,
            proceed_label="Provést kompletní zálohu",
            parent=parent,
        )


class CompleteRestoreConfirmDialog(_CompleteOperationDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title=RESTORE_DIALOG_TITLE,
            text=RESTORE_DIALOG_TEXT,
            proceed_label="Provést kompletní obnovu",
            parent=parent,
        )
