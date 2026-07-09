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
from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_service import (
    BulkInternetImportSummary,
)
from moduly.pravni_pozadavky.ui.legal_predpis_import_worker import LegalPredpisImportThreadRunner


class LegalPredpisImportProgressDialog(QDialog):
    """Modální průběhové okno hromadného importu právních předpisů."""

    def __init__(self, parent=None, *, import_text: str) -> None:
        super().__init__(parent)
        self._summary: BulkInternetImportSummary | None = None
        self._cancelled = False
        self._runner = LegalPredpisImportThreadRunner(import_text=import_text)

        self.setWindowTitle("Import právních předpisů")
        configure_resizable_form_dialog(self, width=560, height=220, min_width=460, min_height=180)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Připravuji import…")
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
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.cancel_btn.clicked.connect(self._request_cancel)

        worker = self._runner.worker
        worker.status.connect(self._update_status)
        worker.progress.connect(self._update_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)

        self._runner.start()

    def summary(self) -> BulkInternetImportSummary | None:
        return self._summary

    def was_cancelled(self) -> bool:
        return self._cancelled

    def _update_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            self.detail_label.setText(label)
            return

        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.detail_label.setText(f"Importuji {current} / {total}: {label}")

    def _request_cancel(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Ruším import…")
        self._runner.worker.request_cancel()

    def _on_finished(self, summary: BulkInternetImportSummary) -> None:
        self._summary = summary
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText("Hotovo.")
        self.cancel_btn.setEnabled(False)
        self.accept()

    def _on_failed(self, message: str) -> None:
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Import se nezdařil.")
        QMessageBox.warning(self, "Import právních předpisů", message)
        self.reject()

    def _on_cancelled(self, summary: BulkInternetImportSummary) -> None:
        self._summary = summary
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Import byl zrušen.")
        self.reject()
