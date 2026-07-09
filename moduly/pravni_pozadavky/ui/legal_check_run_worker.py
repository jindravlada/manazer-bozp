from datetime import date

from PySide6.QtCore import QObject, QThread, Signal

from moduly.pravni_pozadavky.constants import CHECK_RUN_CANCELLED, CHECK_RUN_COMPLETED
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service


class LegalCheckRunWorker(QObject):
    progress = Signal(int, int, str)
    status = Signal(str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        *,
        period_from: date,
        period_to: date,
    ) -> None:
        super().__init__()
        self._period_from = period_from
        self._period_to = period_to
        self._cancel_requested = False

    def run(self) -> None:
        try:
            result = legal_check_run_service.run_automatic_check(
                period_from=self._period_from,
                period_to=self._period_to,
                on_status=self.status.emit,
                on_progress=self.progress.emit,
                is_cancelled=self._is_cancelled,
            )
        except ValueError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        if result.run.status == CHECK_RUN_CANCELLED:
            self.cancelled.emit()
            return
        if result.run.status == CHECK_RUN_COMPLETED:
            self.finished.emit(result)
            return

        self.failed.emit("Kontrola změn skončila v neočekávaném stavu.")

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested


class LegalCheckRunThreadRunner:
    """Spustí automatickou kontrolu ve vedlejším vlákně."""

    def __init__(
        self,
        *,
        period_from: date,
        period_to: date,
    ) -> None:
        self._thread = QThread()
        self._worker = LegalCheckRunWorker(
            period_from=period_from,
            period_to=period_to,
        )
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
    def worker(self) -> LegalCheckRunWorker:
        return self._worker

    def start(self) -> None:
        self._thread.start()

    def wait(self) -> None:
        self._thread.wait()
