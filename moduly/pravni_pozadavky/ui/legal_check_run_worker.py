"""Vlákno automatické kontroly změn.

Životní cyklus odpovídá ``LongOperationRunner``: výsledek workeru jde do GUI
výhradně přes ``Qt.QueuedConnection``, widgety sahá jen dialog v GUI vlákně
a ``deleteLater`` workeru i ``QThread`` proběhne až po zpracování finálního stavu.

``LongOperationRunner`` se nepoužívá přímo. Kontrola změn má jiné signály průběhu
a stav ``CHECK_RUN_ERROR`` musí zůstat výsledkem ``finished``, ne ``failed``.
"""

from __future__ import annotations

import logging
import threading
from datetime import date

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QThread, Signal, Slot

from core.services.application_log import ensure_application_file_logging
from moduly.pravni_pozadavky.constants import (
    CHECK_RUN_CANCELLED,
    CHECK_RUN_COMPLETED,
    CHECK_RUN_ERROR,
)
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service

logger = logging.getLogger(__name__)

_ACTIVE_RUNNERS: set[LegalCheckRunThreadRunner] = set()


def active_legal_check_runner_count() -> int:
    """Počet runnerů, jejichž vlákno ještě nedokončilo cleanup."""
    return len(_ACTIVE_RUNNERS)


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
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._period_from = period_from
        self._period_to = period_to
        self._cancel_event = cancel_event

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
            self._log_failure(exc)
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self._log_failure(exc)
            self.failed.emit(str(exc))
            return

        if result.run.status == CHECK_RUN_CANCELLED:
            self.cancelled.emit()
            return
        if result.run.status == CHECK_RUN_COMPLETED:
            self.finished.emit(result)
            return
        if result.run.status == CHECK_RUN_ERROR:
            self.finished.emit(result)
            return

        self.failed.emit("Kontrola změn skončila v neočekávaném stavu.")

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _log_failure(self, exc: BaseException) -> None:
        try:
            ensure_application_file_logging()
            logger.error(
                "Kontrola změn právních předpisů selhala.",
                exc_info=exc,
            )
        except Exception:
            return


class _WorkerThreadShutdown(QObject):
    """Ukončí vlákno až poté, co je worker smazán ve svém vlastním vlákně."""

    def __init__(self, worker: LegalCheckRunWorker) -> None:
        super().__init__()
        self._worker: LegalCheckRunWorker | None = worker
        self._started = False

    @Slot()
    def shutdown(self) -> None:
        if self._started:
            return
        self._started = True
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
            QCoreApplication.sendPostedEvents(
                worker,
                int(QEvent.Type.DeferredDelete),
            )
        thread = self.thread()
        application = QCoreApplication.instance()
        if application is not None and thread is not None:
            gui_thread = application.thread()
            if gui_thread is not None and gui_thread is not thread:
                self.moveToThread(gui_thread)
        if thread is not None:
            thread.quit()


class LegalCheckRunThreadRunner(QObject):
    """Řídí QThread kontroly změn, doručení výsledku a cleanup.

    Veřejné signály ``status``, ``progress``, ``finished``, ``failed`` a
    ``cancelled`` se emitují v GUI vlákně. ``cleanup_finished`` přijde jednou,
    až vlákno skutečně skončí.
    """

    status = Signal(str)
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    cleanup_finished = Signal()
    _deliver_cleanup = Signal()
    _shutdown_requested = Signal()

    def __init__(
        self,
        *,
        period_from: date,
        period_to: date,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cancel_event = threading.Event()
        self._outcome_emitted = False
        self._deletion_scheduled = False
        self._cleanup_finished = False
        self._ui_released = False
        self._started = False
        self._thread = QThread()
        self._thread.setObjectName("legal-check-run")
        self._worker = LegalCheckRunWorker(
            period_from=period_from,
            period_to=period_to,
            cancel_event=self._cancel_event,
        )
        self._shutdown = _WorkerThreadShutdown(self._worker)
        self._worker.moveToThread(self._thread)
        self._shutdown.moveToThread(self._thread)
        self._wire(self._thread, self._worker, self._shutdown)
        self.destroyed.connect(self._on_destroyed)

    @property
    def worker(self) -> LegalCheckRunWorker | None:
        return self._worker

    @property
    def deletion_scheduled(self) -> bool:
        return self._deletion_scheduled

    def is_thread_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.isRunning()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        _ACTIVE_RUNNERS.add(self)
        thread = self._thread
        if thread is not None:
            thread.start()

    def request_cancel(self) -> None:
        """Nastaví cancellation token. Lze volat z GUI vlákna opakovaně."""
        self._cancel_event.set()

    def release_ui(self) -> None:
        """Odpojí dialog. Běžící kontrolu zruší, hotový výsledek už nemění."""
        if self._ui_released:
            return
        self._ui_released = True
        if self._outcome_emitted:
            return
        self.request_cancel()
        for signal in (
            self.status,
            self.progress,
            self.finished,
            self.failed,
            self.cancelled,
        ):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                continue

    def wait(self, msecs: int = -1) -> bool:
        """Počká na vlákno. Z GUI vlákna se nesmí volat: cleanup potřebuje jeho smyčku."""
        thread = self._thread
        if thread is None:
            return True
        if msecs < 0:
            return thread.wait()
        return thread.wait(msecs)

    def _wire(
        self,
        thread: QThread,
        worker: LegalCheckRunWorker,
        shutdown: _WorkerThreadShutdown,
    ) -> None:
        queued = Qt.ConnectionType.QueuedConnection
        thread.started.connect(worker.run, Qt.ConnectionType.DirectConnection)
        worker.status.connect(self._relay_status, queued)
        worker.progress.connect(self._relay_progress, queued)
        worker.finished.connect(self._on_worker_finished, queued)
        worker.failed.connect(self._on_worker_failed, queued)
        worker.cancelled.connect(self._on_worker_cancelled, queued)
        worker.destroyed.connect(self._on_worker_destroyed, queued)
        self._deliver_cleanup.connect(self._schedule_worker_deletion, queued)
        self._shutdown_requested.connect(shutdown.shutdown, queued)
        thread.finished.connect(self._on_thread_finished, queued)
        thread.finished.connect(thread.deleteLater, queued)

    @Slot(str)
    def _relay_status(self, message: str) -> None:
        if self._outcome_emitted:
            return
        self.status.emit(message)

    @Slot(int, int, str)
    def _relay_progress(self, current: int, total: int, label: str) -> None:
        if self._outcome_emitted:
            return
        self.progress.emit(int(current), int(total), str(label))

    @Slot(object)
    def _on_worker_finished(self, result: object) -> None:
        self._emit_outcome("finished", result)

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        self._emit_outcome("failed", message)

    @Slot()
    def _on_worker_cancelled(self) -> None:
        self._emit_outcome("cancelled", None)

    def _emit_outcome(self, kind: str, payload: object) -> None:
        if self._outcome_emitted:
            return
        self._outcome_emitted = True
        if kind == "finished":
            self.finished.emit(payload)
        elif kind == "cancelled":
            self.cancelled.emit()
        else:
            self.failed.emit(str(payload))
        self._deliver_cleanup.emit()

    @Slot()
    def _schedule_worker_deletion(self) -> None:
        if self._deletion_scheduled:
            return
        self._deletion_scheduled = True
        worker = self._worker
        if worker is None:
            self._quit_thread()
            return
        self._shutdown_requested.emit()

    def _quit_thread(self) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()

    def _on_worker_destroyed(self, *_args) -> None:
        self._worker = None

    def _on_thread_finished(self) -> None:
        if self._cleanup_finished:
            return
        sender = self.sender()
        if sender is not None and sender is not self._thread:
            return
        self._cleanup_finished = True
        self._worker = None
        shutdown = self._shutdown
        self._shutdown = None
        self._thread = None
        _ACTIVE_RUNNERS.discard(self)
        if shutdown is not None:
            shutdown.deleteLater()
        self.cleanup_finished.emit()

    def _on_destroyed(self, *_args) -> None:
        self._cancel_event.set()
