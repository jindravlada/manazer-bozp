from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import AutomaticCheckRunResult
from moduly.pravni_pozadavky.ui.legal_check_run_worker import LegalCheckRunThreadRunner


class LegalCheckProgressDialog(QDialog):
    """Modální průběhové okno automatické kontroly změn."""

    def __init__(
        self,
        parent=None,
        *,
        period_from: date,
        period_to: date,
    ) -> None:
        super().__init__(parent)
        self._result: AutomaticCheckRunResult | None = None
        self._runner = LegalCheckRunThreadRunner(
            period_from=period_from,
            period_to=period_to,
        )

        self.setWindowTitle("Kontrola změn právních předpisů")
        configure_resizable_form_dialog(self, width=520, height=220, min_width=420, min_height=180)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Připravuji kontrolu…")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_btn = QPushButton("Zrušit")
        self.close_btn = QPushButton("Zavřít")
        self.close_btn.setEnabled(False)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.cancel_btn.clicked.connect(self._request_cancel)
        self.close_btn.clicked.connect(self.reject)

        queued = Qt.ConnectionType.QueuedConnection
        runner = self._runner
        runner.status.connect(self._update_status, queued)
        runner.progress.connect(self._update_progress, queued)
        runner.finished.connect(self._on_finished, queued)
        runner.failed.connect(self._on_failed, queued)
        runner.cancelled.connect(self._on_cancelled, queued)
        self.destroyed.connect(lambda *_args: runner.release_ui())

        self._runner.start()

    def result_data(self) -> AutomaticCheckRunResult | None:
        return self._result

    def closeEvent(self, event: QCloseEvent) -> None:
        self._runner.release_ui()
        super().closeEvent(event)

    def _update_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            self.detail_label.setText(label)
            return

        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.detail_label.setText(f"Kontroluji {current} / {total}: {label}")

    def _request_cancel(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Ruším kontrolu…")
        self._runner.request_cancel()

    def _on_finished(self, result: AutomaticCheckRunResult) -> None:
        self._result = result
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText("Kontrola dokončena.")
        self.cancel_btn.setEnabled(False)
        self.accept()

    def _on_failed(self, message: str) -> None:
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.status_label.setText("Kontrola se nezdařila.")
        QMessageBox.warning(self, "Kontrola změn", message)
        self.reject()

    def _on_cancelled(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.status_label.setText("Kontrola byla zrušena.")
        self.reject()
