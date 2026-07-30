"""Dialogy pro zálohu / ověření / obnovu instance (*.mbbackup)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RestoreConfirmDialog(QDialog):
    """Potvrzení obnovy s vysvětlením (ne jen Ano/Ne)."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        summary_text: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Potvrzení obnovy ze zálohy")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        title = QLabel("<b>Obnova nahradí současná pracovní data</b>")
        title.setWordWrap(True)
        layout.addWidget(title)

        body = QLabel(summary_text)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        warning = QLabel(
            "Pokračujte jen pokud jste si jisti, že chcete obnovit tuto zálohu. "
            "Při chybě je připraven automatický návrat původních dat (rollback)."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        buttons = QDialogButtonBox()
        self.confirm_button = buttons.addButton(
            "Ano, obnovit data ze zálohy", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.cancel_button = buttons.addButton(
            "Zrušit", QDialogButtonBox.ButtonRole.RejectRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ContinueWithoutSafetyBackupDialog(QDialog):
    """Krizový scénář: pokračování obnovy bez automatické bezpečnostní zálohy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nepodařilo se vytvořit bezpečnostní zálohu")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        body = QLabel(
            "Program se před obnovou pokusil vytvořit automatickou bezpečnostní "
            "zálohu aktuálních dat.\n\n"
            "Tento krok se nepodařilo dokončit.\n\n"
            "Pokud budete pokračovat, budou současná data přepsána a nebude možné "
            "je obnovit.\n\n"
            "Doporučujeme nejprve odstranit příčinu problému a obnovu zopakovat."
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        self.confirm_checkbox = QCheckBox(
            "Rozumím, že pokračováním bez vytvoření bezpečnostní zálohy "
            "mohu nenávratně ztratit současná data."
        )
        self.confirm_checkbox.toggled.connect(self._on_confirm_toggled)
        layout.addWidget(self.confirm_checkbox)

        buttons = QDialogButtonBox()
        self.cancel_button = buttons.addButton(
            "Zrušit obnovu", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.continue_button = buttons.addButton(
            "Pokračovat bez bezpečnostní zálohy",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.continue_button.setEnabled(False)
        self.cancel_button.setDefault(True)
        self.cancel_button.setAutoDefault(True)
        self.continue_button.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_confirm_toggled(self, checked: bool) -> None:
        self.continue_button.setEnabled(checked)
        if checked:
            self.continue_button.setDefault(True)
            self.cancel_button.setDefault(False)
        else:
            self.cancel_button.setDefault(True)
            self.continue_button.setDefault(False)


class BackupProgressDialog(QDialog):
    """Modální průběh operace – nelze zavřít během kritické fáze."""

    def __init__(self, parent: QWidget | None, *, title: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._allow_close = False

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Připravuji…")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        hint = QLabel("Prosím vyčkejte. Dialog během kritické fáze nelze zavřít.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")
        layout.addWidget(hint)

        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def allow_close(self) -> None:
        self._allow_close = True

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._allow_close:
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._allow_close:
            super().reject()


class MessageWithDetailsDialog(QDialog):
    """Uživatelská zpráva s volitelně rozbalitelnými technickými podrobnostmi."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        message: str,
        details: str = "",
        level: str = "info",
    ) -> None:
        super().__init__(parent)
        from core.dialogs.message_box import (
            MESSAGE_BOX_MIN_WIDTH,
            strip_application_title_suffix,
        )

        self.setWindowTitle(strip_application_title_suffix(title))
        self.setModal(True)
        self.setMinimumWidth(max(480, MESSAGE_BOX_MIN_WIDTH))

        layout = QVBoxLayout(self)
        body = QLabel(message)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        self._details = details.strip()
        self._details_edit: QTextEdit | None = None
        if self._details:
            toggle_row = QHBoxLayout()
            self._toggle_btn = QPushButton("Podrobnosti")
            self._toggle_btn.setCheckable(True)
            self._toggle_btn.toggled.connect(self._on_toggle_details)
            toggle_row.addWidget(self._toggle_btn)
            toggle_row.addStretch()
            layout.addLayout(toggle_row)

            self._details_edit = QTextEdit()
            self._details_edit.setReadOnly(True)
            self._details_edit.setPlainText(self._details)
            self._details_edit.setVisible(False)
            self._details_edit.setMinimumHeight(140)
            layout.addWidget(self._details_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("OK")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        if level == "critical":
            body.setStyleSheet("font-weight: 600;")

    def _on_toggle_details(self, checked: bool) -> None:
        if self._details_edit is not None:
            self._details_edit.setVisible(checked)
