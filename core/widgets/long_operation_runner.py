"""Společný runner dlouhých operací mimo GUI vlákno.

Worker smí:

- číst čistý vstupní snapshot (běžné Python objekty, cesty, primitiva),
- volat metody ``LongOperationContext`` (fáze, progress, cancel token),
- vracet běžný Python objekt signálem,
- otevřít **vlastní** SQLAlchemy session ve svém vlákně, pokud ji po sobě zavře.

Worker nesmí:

- sahat na Qt widgety, Qt modely patřící GUI ani jiné QObject s afinitou GUI vlákna,
- dostat živou SQLAlchemy session z hlavního vlákna,
- volat ``QThread.terminate()``.

GUI vlákno zůstává odpovědné za widgety, tabulky, stromy a následnou
``ChunkedUiPump``. Runner **nespouští** UI pumpu sám.

Zrušitelná fáze: worker kontroluje ``is_cancel_requested()`` / ``check_cancel()``.
Atomická fáze: token se z workeru jeví jako neaktivní; dialog zakáže Zrušit
a zavření. Po opuštění atomicity platí další nahlášená fáze.

Příklad návaznosti bez doménového kódu::

    runner.start(work, snapshot)
    runner.succeeded.connect(lambda rows: pump.start(rows, fill_batch))
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

LongOperationWork = Callable[["LongOperationContext", Any], Any]


class LongOperationState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FINISHED = "finished"


class LongOperationCancelled(Exception):
    """Kooperativní zrušení workeru. Runner ho hlásí jako cancelled, ne failed."""


class LongOperationContext:
    """Reportér fází pro worker. Nesmí držet odkaz na dialog ani widgety."""

    def __init__(
        self,
        *,
        worker: "_LongOperationWorker",
        cancel_event: threading.Event,
        generation: int,
    ) -> None:
        self._worker = worker
        self._cancel_event = cancel_event
        self._generation = generation
        self._atomic = False

    def set_phase(
        self,
        text: str,
        *,
        indeterminate: bool = False,
        atomic: bool = False,
    ) -> None:
        """Nastaví text fáze. ``atomic=True`` dočasně skryje zrušení."""
        self._atomic = bool(atomic)
        self._worker.phase_changed.emit(
            self._generation,
            str(text),
            bool(indeterminate),
            bool(atomic),
        )

    def set_progress(self, current: int, total: int) -> None:
        """Určitý průběh ``current / total``. Přepne dialog z neurčitého baru."""
        self._worker.progress_changed.emit(
            self._generation,
            int(current),
            int(total),
        )

    def is_cancel_requested(self) -> bool:
        """True jen mimo atomickou fázi, pokud uživatel požádal o zrušení."""
        if self._atomic:
            return False
        return self._cancel_event.is_set()

    def check_cancel(self) -> None:
        """Vyvolá ``LongOperationCancelled``, pokud je zrušení právě povoleno."""
        if self.is_cancel_requested():
            raise LongOperationCancelled()


class _LongOperationWorker(QObject):
    phase_changed = Signal(int, str, bool, bool)
    progress_changed = Signal(int, int, int)
    succeeded = Signal(int, object)
    cancelled = Signal(int)
    failed = Signal(int, str)

    def __init__(
        self,
        *,
        work: LongOperationWork,
        snapshot: Any,
        cancel_event: threading.Event,
        generation: int,
    ) -> None:
        super().__init__()
        self._work = work
        self._snapshot = snapshot
        self._cancel_event = cancel_event
        self._generation = generation

    def run(self) -> None:
        context = LongOperationContext(
            worker=self,
            cancel_event=self._cancel_event,
            generation=self._generation,
        )
        try:
            result = self._work(context, self._snapshot)
        except LongOperationCancelled:
            self.cancelled.emit(self._generation)
            return
        except Exception as exc:
            logger.exception("Dlouhá operace selhala (generation=%s).", self._generation)
            self.failed.emit(self._generation, _user_message(exc))
            return
        self.succeeded.emit(self._generation, result)


def _user_message(exc: BaseException) -> str:
    text = str(exc).strip()
    if text:
        return text
    return "Operace selhala."


class LongOperationRunner(QObject):
    """Řídí QThread, výsledek, výjimky, zrušení, reentranci a cleanup.

    Veřejné signály (vzájemně vylučující outcome, poté právě jedno ``finished``):

    - ``started`` — operace přijata a vlákno spuštěno
    - ``phase_changed(text, indeterminate, atomic)``
    - ``progress_changed(current, total)``
    - ``succeeded(result)`` — doménové dokončení workeru
    - ``cancelled`` — uživatelské zrušení (není chyba)
    - ``failed(message)`` — uživatelský text bez tracebacku
    - ``finished`` — cleanup QThread dokončen (až po outcome)

    ``succeeded`` / ``cancelled`` / ``failed`` nedorazí současně. ``finished``
    nepřijde vícekrát pro jednu generaci. Runner nepředpokládá UI pumpu.
    """

    started = Signal()
    phase_changed = Signal(str, bool, bool)
    progress_changed = Signal(int, int)
    succeeded = Signal(object)
    cancelled = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = LongOperationState.IDLE
        self._generation = 0
        self._cancel_event = threading.Event()
        self._atomic = False
        self._outcome_emitted = False
        self._thread: QThread | None = None
        self._worker: _LongOperationWorker | None = None
        self._blocked: list[tuple[QWidget, bool]] = []
        self._keep_alive: tuple[object, ...] = ()
        self.destroyed.connect(self._on_destroyed)

    @property
    def state(self) -> LongOperationState:
        return self._state

    def is_running(self) -> bool:
        return self._state in {
            LongOperationState.RUNNING,
            LongOperationState.CANCELLING,
        }

    def is_atomic(self) -> bool:
        return bool(self._atomic) and self.is_running()

    def start(
        self,
        work: LongOperationWork,
        snapshot: Any = None,
        *,
        blocked_widgets: Sequence[QWidget] | None = None,
    ) -> bool:
        """Spustí ``work(context, snapshot)`` ve vlastním vlákně.

        Vrací False, pokud už operace běží (druhý thread nevznikne).
        """
        if self.is_running():
            return False

        self._generation += 1
        self._cancel_event = threading.Event()
        self._atomic = False
        self._outcome_emitted = False
        self._state = LongOperationState.RUNNING
        self._block_widgets(blocked_widgets)

        generation = self._generation
        thread = QThread()
        worker = _LongOperationWorker(
            work=work,
            snapshot=snapshot,
            cancel_event=self._cancel_event,
            generation=generation,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.phase_changed.connect(
            self._on_worker_phase,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.progress_changed.connect(
            self._on_worker_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.succeeded.connect(
            self._on_worker_succeeded,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.cancelled.connect(
            self._on_worker_cancelled,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._on_worker_failed,
            Qt.ConnectionType.QueuedConnection,
        )

        def _quit_thread(*_args) -> None:
            thread.quit()

        def _delete_worker(*_args) -> None:
            worker.deleteLater()

        for signal in (worker.succeeded, worker.cancelled, worker.failed):
            signal.connect(_quit_thread)
            signal.connect(_delete_worker)
        thread.finished.connect(
            self._on_thread_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._keep_alive = (_quit_thread, _delete_worker)
        thread.start()
        self.started.emit()
        return True

    def request_cancel(self) -> None:
        """Nastaví cancellation token. Během atomické fáze se požadavek ignoruje."""
        if not self.is_running():
            return
        if self._atomic:
            return
        self._cancel_event.set()
        self._state = LongOperationState.CANCELLING

    def _on_worker_phase(
        self,
        generation: int,
        text: str,
        indeterminate: bool,
        atomic: bool,
    ) -> None:
        if generation != self._generation or self._outcome_emitted:
            return
        self._atomic = bool(atomic)
        self.phase_changed.emit(text, bool(indeterminate), bool(atomic))

    def _on_worker_progress(self, generation: int, current: int, total: int) -> None:
        if generation != self._generation or self._outcome_emitted:
            return
        self.progress_changed.emit(int(current), int(total))

    def _on_worker_succeeded(self, generation: int, result: object) -> None:
        self._emit_outcome(generation, "succeeded", result)

    def _on_worker_cancelled(self, generation: int) -> None:
        self._emit_outcome(generation, "cancelled", None)

    def _on_worker_failed(self, generation: int, message: str) -> None:
        self._emit_outcome(generation, "failed", message)

    def _emit_outcome(self, generation: int, kind: str, payload: object) -> None:
        if generation != self._generation or self._outcome_emitted:
            return
        self._outcome_emitted = True
        self._atomic = False
        if kind == "succeeded":
            self.succeeded.emit(payload)
        elif kind == "cancelled":
            self.cancelled.emit()
        else:
            self.failed.emit(str(payload))

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if thread is not None and thread is not self._thread:
            return
        if self._state == LongOperationState.IDLE:
            return
        self._worker = None
        self._thread = None
        self._state = LongOperationState.FINISHED
        self._atomic = False
        self._restore_blocked_widgets()
        self.finished.emit()

    def _block_widgets(self, widgets: Sequence[QWidget] | None) -> None:
        self._restore_blocked_widgets()
        stored: list[tuple[QWidget, bool]] = []
        for widget in widgets or ():
            stored.append((widget, widget.isEnabled()))
            widget.setEnabled(False)
        self._blocked = stored

    def _restore_blocked_widgets(self) -> None:
        for widget, was_enabled in self._blocked:
            try:
                widget.setEnabled(was_enabled)
            except RuntimeError:
                continue
        self._blocked = []

    def _on_destroyed(self, *_args) -> None:
        self._cancel_event.set()
        self._restore_blocked_widgets()
