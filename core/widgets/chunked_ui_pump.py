"""Dávkové zpracování UI položek v hlavním Qt vlákně.

Pumpa musí běžet výhradně v GUI vlákně. Mezi dávkami vrací řízení
event loopu přes ``QTimer.singleShot`` — **ne** ``QApplication.processEvents()``.

Nepředpokládá ``QTableWidget``. Optimalizace tabulky (signály, tooltipy)
patří adaptéru konkrétního dialogu.

Zrušitelná: zastaví další dávky, hlásí ``cancelled`` (ne success).
Atomická fáze sem nepatří — pumpa je UI, ne zápis dat.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50

ChunkConsumer = Callable[[Sequence[Any]], None]


class ChunkedUiPump(QObject):
    """Dávkuje ``consumer(batch)`` v GUI vlákně s průběhem ``processed / total``.

    Signály jedné generace: právě jeden z ``succeeded`` / ``cancelled`` /
    ``failed``, poté právě jedno ``finished``. Stará generace po novém
    ``start()`` nebo zrušení nic nezmění.
    """

    progress = Signal(int, int)
    succeeded = Signal()
    cancelled = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._generation = 0
        self._running = False
        self._cancel_requested = False
        self._items: tuple[Any, ...] = ()
        self._index = 0
        self._batch_size = DEFAULT_BATCH_SIZE
        self._consumer: ChunkConsumer | None = None
        self._outcome_emitted = False

    def is_running(self) -> bool:
        return self._running

    def start(
        self,
        items: Sequence[Any] | Iterable[Any],
        consumer: ChunkConsumer,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> bool:
        """Začne dávkovat. Vrací False, pokud už pumpa běží."""
        app = QApplication.instance()
        if app is not None and QThread.currentThread() is not app.thread():
            raise RuntimeError("ChunkedUiPump musí běžet v hlavním Qt vlákně.")
        if self._running:
            return False

        size = max(1, int(batch_size))
        if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
            collected: tuple[Any, ...] = tuple(items)
        else:
            collected = tuple(items)

        self._generation += 1
        self._running = True
        self._cancel_requested = False
        self._outcome_emitted = False
        self._items = collected
        self._index = 0
        self._batch_size = size
        self._consumer = consumer
        generation = self._generation

        if not collected:
            self.progress.emit(0, 0)
            self._complete(generation, "succeeded")
            return True

        QTimer.singleShot(0, lambda: self._run_batch(generation))
        return True

    def request_cancel(self) -> None:
        if not self._running:
            return
        self._cancel_requested = True

    def _run_batch(self, generation: int) -> None:
        if generation != self._generation:
            return
        if not self._running:
            return

        if self._cancel_requested:
            self._complete(generation, "cancelled")
            return

        total = len(self._items)
        batch = self._items[self._index : self._index + self._batch_size]
        if not batch:
            self._complete(generation, "succeeded")
            return

        consumer = self._consumer
        try:
            if consumer is not None:
                consumer(batch)
        except Exception as exc:
            logger.exception("Chunked UI pump selhala (generation=%s).", generation)
            message = str(exc).strip() or "Zpracování položek selhalo."
            self._complete(generation, "failed", message)
            return

        if generation != self._generation:
            return

        self._index += len(batch)
        self.progress.emit(self._index, total)

        if self._cancel_requested:
            self._complete(generation, "cancelled")
            return
        if self._index >= total:
            self._complete(generation, "succeeded")
            return

        QTimer.singleShot(0, lambda: self._run_batch(generation))

    def _complete(
        self,
        generation: int,
        kind: str,
        message: str = "",
    ) -> None:
        if generation != self._generation or self._outcome_emitted:
            return
        self._outcome_emitted = True
        self._running = False
        self._consumer = None
        self._items = ()
        if kind == "succeeded":
            self.succeeded.emit()
        elif kind == "cancelled":
            self.cancelled.emit()
        else:
            self.failed.emit(message)
        self.finished.emit()
