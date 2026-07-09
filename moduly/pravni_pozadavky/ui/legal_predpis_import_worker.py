from PySide6.QtCore import QObject, QThread, Signal

from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_service import (
    BulkInternetImportSummary,
    legal_document_bulk_internet_import_service,
)


class LegalPredpisImportWorker(QObject):
    status = Signal(str)
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal(object)

    def __init__(self, *, import_text: str) -> None:
        super().__init__()
        self._import_text = import_text
        self._cancel_requested = False

    def run(self) -> None:
        try:
            summary = legal_document_bulk_internet_import_service.import_lines(
                self._import_text,
                on_progress=self.progress.emit,
                on_status=self.status.emit,
                is_cancelled=self._is_cancelled,
            )
        except ValueError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        if self._cancel_requested:
            self.cancelled.emit(summary)
            return
        self.finished.emit(summary)

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested


class LegalPredpisImportThreadRunner:
    """Spustí hromadný import předpisů ve vedlejším vlákně."""

    def __init__(self, *, import_text: str) -> None:
        self._thread = QThread()
        self._worker = LegalPredpisImportWorker(import_text=import_text)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker.cancelled.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

    @property
    def worker(self) -> LegalPredpisImportWorker:
        return self._worker

    def start(self) -> None:
        self._thread.start()

    def wait(self) -> None:
        self._thread.wait()
