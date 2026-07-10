from PySide6.QtCore import QObject, QThread, Signal

from moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service import (
    ValidTextDocument,
    legal_document_valid_text_service,
)


class LegalDocumentValidTextWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, *, version_id: int) -> None:
        super().__init__()
        self._version_id = version_id

    def run(self) -> None:
        try:
            document = legal_document_valid_text_service.compose_version(self._version_id)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(document)


class LegalDocumentValidTextThreadRunner:
    """Sestaví platné znění verze předpisu ve vedlejším vlákně."""

    def __init__(self, *, version_id: int) -> None:
        self._thread = QThread()
        self._worker = LegalDocumentValidTextWorker(version_id=version_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

    @property
    def worker(self) -> LegalDocumentValidTextWorker:
        return self._worker

    def start(self) -> None:
        self._thread.start()

    def wait(self) -> None:
        self._thread.wait()
