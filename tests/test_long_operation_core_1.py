"""LONG-OPERATION-CORE-1: společný základ dlouhých operací (bez produkčních modulů)."""

from __future__ import annotations

import os
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from core.widgets.chunked_ui_pump import ChunkedUiPump
from core.widgets.long_operation_dialog import LongOperationDialog
from core.widgets.long_operation_runner import (
    LongOperationContext,
    LongOperationRunner,
    LongOperationState,
)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _SignalLog:
    """Zachytí argumenty signálu a umí počkat bez blokujícího sleep."""

    def __init__(self, signal) -> None:
        self.items: list[tuple] = []
        self._signal = signal
        signal.connect(self._on)

    def _on(self, *args) -> None:
        self.items.append(args)

    @property
    def count(self) -> int:
        return len(self.items)

    def wait(self, timeout_ms: int = 2000) -> None:
        if self.items:
            return
        loop = QEventLoop()

        def _quit(*_args) -> None:
            loop.quit()

        self._signal.connect(_quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        self._signal.disconnect(_quit)
        timer.stop()
        if not self.items:
            raise AssertionError("Očekávaný signál nedorazil.")


class LongOperationRunnerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_success_result_and_worker_off_gui_thread(self) -> None:
        runner = LongOperationRunner()
        main_thread = QThread.currentThread()
        seen: dict[str, object] = {}

        def work(_ctx: LongOperationContext, snapshot: object) -> object:
            seen["worker_thread"] = QThread.currentThread()
            return snapshot

        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)
        failed = _SignalLog(runner.failed)
        cancelled = _SignalLog(runner.cancelled)

        self.assertTrue(runner.start(work, "ok-payload"))
        finished.wait()

        self.assertEqual(succeeded.count, 1)
        self.assertEqual(succeeded.items[0][0], "ok-payload")
        self.assertEqual(failed.count, 0)
        self.assertEqual(cancelled.count, 0)
        self.assertEqual(finished.count, 1)
        self.assertIsNot(seen["worker_thread"], main_thread)
        self.assertEqual(runner.state, LongOperationState.FINISHED)
        self.assertFalse(runner.is_running())
        self.assertIsNone(runner._thread)

    def test_progress_and_phases_arrive_on_gui_thread(self) -> None:
        runner = LongOperationRunner()
        gui_thread = QThread.currentThread()
        progress_threads: list[QThread] = []
        phases: list[tuple] = []
        runner.progress_changed.connect(
            lambda _c, _t: progress_threads.append(QThread.currentThread())
        )
        runner.phase_changed.connect(
            lambda text, ind, atomic: phases.append((text, ind, atomic))
        )
        finished = _SignalLog(runner.finished)

        def work(ctx: LongOperationContext, snapshot: object) -> object:
            ctx.set_phase("Načítám…", indeterminate=True)
            ctx.set_phase("Počítám…")
            ctx.set_progress(1, 4)
            ctx.set_progress(4, 4)
            ctx.set_phase("Ukládám…", atomic=True)
            return snapshot

        runner.start(work, None)
        finished.wait()

        self.assertEqual(
            phases,
            [
                ("Načítám…", True, False),
                ("Počítám…", False, False),
                ("Ukládám…", False, True),
            ],
        )
        self.assertTrue(progress_threads)
        self.assertTrue(all(thread is gui_thread for thread in progress_threads))

    def test_exception_emits_only_failed(self) -> None:
        runner = LongOperationRunner()
        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)
        failed = _SignalLog(runner.failed)
        cancelled = _SignalLog(runner.cancelled)

        def work(_ctx: LongOperationContext, _snapshot: object) -> object:
            raise ValueError("Nelze dokončit výpočet.")

        runner.start(work, None)
        finished.wait()

        self.assertEqual(failed.count, 1)
        self.assertEqual(failed.items[0][0], "Nelze dokončit výpočet.")
        self.assertEqual(succeeded.count, 0)
        self.assertEqual(cancelled.count, 0)
        self.assertEqual(finished.count, 1)

    def test_cancel_emits_only_cancelled(self) -> None:
        runner = LongOperationRunner()
        entered = threading.Event()
        proceed = threading.Event()
        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)
        failed = _SignalLog(runner.failed)
        cancelled = _SignalLog(runner.cancelled)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            entered.set()
            proceed.wait(timeout=5)
            ctx.check_cancel()
            return "should-not"

        self.assertTrue(runner.start(work, None))
        self.assertTrue(entered.wait(timeout=2))
        try:
            runner.request_cancel()
            self.assertEqual(runner.state, LongOperationState.CANCELLING)
            proceed.set()
            finished.wait()
        finally:
            proceed.set()

        self.assertEqual(cancelled.count, 1)
        self.assertEqual(succeeded.count, 0)
        self.assertEqual(failed.count, 0)

    def test_atomic_phase_ignores_cancel(self) -> None:
        runner = LongOperationRunner()
        entered = threading.Event()
        proceed = threading.Event()
        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)
        cancelled = _SignalLog(runner.cancelled)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Ukládám…", atomic=True)
            entered.set()
            proceed.wait(timeout=5)
            ctx.check_cancel()
            return "saved"

        runner.start(work, None)
        self.assertTrue(entered.wait(timeout=2))
        try:
            runner.request_cancel()
            proceed.set()
            finished.wait()
        finally:
            proceed.set()

        self.assertEqual(succeeded.count, 1)
        self.assertEqual(succeeded.items[0][0], "saved")
        self.assertEqual(cancelled.count, 0)

    def test_second_start_while_running_is_rejected(self) -> None:
        runner = LongOperationRunner()
        gates = {"entered": threading.Event(), "proceed": threading.Event()}
        finished = _SignalLog(runner.finished)
        started = _SignalLog(runner.started)

        def work(_ctx: LongOperationContext, snapshot: object) -> object:
            gates["entered"].set()
            gates["proceed"].wait(timeout=5)
            return snapshot

        self.assertTrue(runner.start(work, "first"))
        self.assertTrue(gates["entered"].wait(timeout=2))
        try:
            self.assertFalse(runner.start(work, "second"))
            gates["proceed"].set()
            finished.wait()
        finally:
            gates["proceed"].set()
        self.assertEqual(started.count, 1)

        gates["entered"] = threading.Event()
        gates["proceed"] = threading.Event()
        succeeded = _SignalLog(runner.succeeded)
        finished2 = _SignalLog(runner.finished)
        self.assertTrue(runner.start(work, "again"))
        self.assertTrue(gates["entered"].wait(timeout=2))
        try:
            gates["proceed"].set()
            finished2.wait()
        finally:
            gates["proceed"].set()
        self.assertEqual(succeeded.count, 1)
        self.assertEqual(succeeded.items[0][0], "again")

    def test_stale_generation_does_not_emit_outcome(self) -> None:
        runner = LongOperationRunner()
        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)

        def work(_ctx: LongOperationContext, snapshot: object) -> object:
            return snapshot

        runner.start(work, "fresh")
        finished.wait()
        runner._on_worker_succeeded(0, "stale")
        self.assertEqual(succeeded.count, 1)
        self.assertEqual(succeeded.items[0][0], "fresh")

    def test_blocked_widgets_restored_after_failure(self) -> None:
        runner = LongOperationRunner()
        button = QPushButton("Spustit")
        button.setEnabled(True)
        finished = _SignalLog(runner.finished)

        def work(_ctx: LongOperationContext, _snapshot: object) -> object:
            raise RuntimeError("selhání")

        runner.start(work, None, blocked_widgets=[button])
        self.assertFalse(button.isEnabled())
        finished.wait()
        self.assertTrue(button.isEnabled())


class LongOperationDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_fast_operation_does_not_show_dialog(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Rychlá operace",
            runner=runner,
            delay_ms=300,
        )
        finished = _SignalLog(runner.finished)
        presented = _SignalLog(dialog.presented)

        def work(_ctx: LongOperationContext, snapshot: object) -> object:
            return snapshot

        runner.start(work, True)
        finished.wait()
        QApplication.sendPostedEvents()
        self._app.processEvents()

        self.assertFalse(dialog.was_presented())
        self.assertFalse(dialog.isVisible())
        self.assertEqual(presented.count, 0)
        self.assertFalse(dialog._show_timer.isActive())
        dialog.deleteLater()

    def test_delay_zero_shows_dialog_for_running_operation(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Dlouhá operace",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)
        phases = _SignalLog(runner.phase_changed)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Kontroluji data…", indeterminate=True)
            proceed.wait(timeout=5)
            ctx.set_phase("Počítám…")
            ctx.set_progress(2, 5)
            return "done"

        try:
            runner.start(work, None)
            presented.wait()
            phases.wait()
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.windowTitle(), "Dlouhá operace")
            self.assertEqual(dialog._phase_label.text(), "Kontroluji data…")
            self.assertEqual(dialog._progress_bar.minimum(), 0)
            self.assertEqual(dialog._progress_bar.maximum(), 0)
            self.assertTrue(dialog._cancel_btn.isEnabled())
        finally:
            proceed.set()
        finished.wait()
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_determinate_progress_and_phase_text(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Průběh",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)
        progress = _SignalLog(runner.progress_changed)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Zpracovávám…")
            ctx.set_progress(3, 10)
            proceed.wait(timeout=5)
            return None

        try:
            runner.start(work, None)
            presented.wait()
            progress.wait()
            self.assertEqual(dialog._phase_label.text(), "Zpracovávám…")
            self.assertEqual(dialog._progress_bar.maximum(), 10)
            self.assertEqual(dialog._progress_bar.value(), 3)
            self.assertEqual(dialog._count_label.text(), "3 / 10")
        finally:
            proceed.set()
        finished.wait()
        dialog.deleteLater()

    def test_atomic_phase_blocks_close_and_cancel(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Zápis",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)
        succeeded = _SignalLog(runner.succeeded)
        phases = _SignalLog(runner.phase_changed)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Ukládám data…", atomic=True)
            proceed.wait(timeout=5)
            ctx.check_cancel()
            return "written"

        try:
            runner.start(work, None)
            presented.wait()
            phases.wait()
            self.assertFalse(dialog._cancel_btn.isEnabled())

            event = QCloseEvent()
            dialog.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertTrue(dialog.isVisible())

            dialog.reject()
            self.assertTrue(dialog.isVisible())
            dialog._cancel_btn.click()
        finally:
            proceed.set()
        finished.wait()
        self.assertEqual(succeeded.count, 1)
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_cancel_button_requests_cancel(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Rušení",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        cancelled = _SignalLog(runner.cancelled)
        finished = _SignalLog(runner.finished)
        phases = _SignalLog(runner.phase_changed)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            proceed.wait(timeout=5)
            ctx.check_cancel()
            return "no"

        try:
            runner.start(work, None)
            presented.wait()
            phases.wait()
            dialog._cancel_btn.click()
        finally:
            proceed.set()
        finished.wait()
        self.assertEqual(cancelled.count, 1)
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_failure_closes_dialog_and_restores_button(self) -> None:
        parent = QWidget()
        button = QPushButton("Spustit", parent)
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            parent,
            title="Chyba",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)
        failed = _SignalLog(runner.failed)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Pracuji…", indeterminate=True)
            proceed.wait(timeout=5)
            raise RuntimeError("Operace se nezdařila.")

        try:
            runner.start(work, None, blocked_widgets=[button])
            presented.wait()
            self.assertFalse(button.isEnabled())
        finally:
            proceed.set()
        finished.wait()
        self.assertEqual(failed.count, 1)
        self.assertEqual(failed.items[0][0], "Operace se nezdařila.")
        self.assertFalse(dialog.isVisible())
        self.assertTrue(button.isEnabled())
        dialog.deleteLater()
        parent.deleteLater()

    def test_status_text_is_shown_and_cleared(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Stav",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        status = _SignalLog(runner.status_changed)
        finished = _SignalLog(runner.finished)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            ctx.set_progress(1, 2)
            ctx.set_status("Doplňkový stav")
            proceed.wait(timeout=5)
            ctx.set_status("")
            return None

        try:
            runner.start(work, None)
            presented.wait()
            status.wait()
            self.assertTrue(dialog._status_label.isVisible())
            self.assertEqual(dialog._status_label.text(), "Doplňkový stav")
        finally:
            proceed.set()
        finished.wait()
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_close_on_success_false_keeps_dialog_until_complete(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Navazující fáze",
            runner=runner,
            delay_ms=0,
            close_on_success=False,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        succeeded = _SignalLog(runner.succeeded)
        finished = _SignalLog(runner.finished)
        visibility: list[bool] = []

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            ctx.set_progress(10, 10)
            proceed.wait(timeout=5)
            return "rows"

        try:
            runner.start(work, None)
            presented.wait()
            self.assertTrue(dialog.isVisible())
        finally:
            proceed.set()
        succeeded.wait()
        finished.wait()
        QApplication.sendPostedEvents()
        self._app.processEvents()

        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog.is_followup_active())
        visibility.append(dialog.isVisible())

        dialog.set_phase("Připravuji výsledky k zobrazení…")
        dialog.set_status("")
        dialog.set_progress(20, 100)
        self.assertEqual(dialog._phase_label.text(), "Připravuji výsledky k zobrazení…")
        self.assertEqual(dialog._count_label.text(), "20 / 100")
        self.assertFalse(dialog._status_label.isVisible())
        self.assertTrue(dialog._cancel_btn.isEnabled())

        dialog.complete()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog.is_followup_active())
        self.assertEqual(visibility, [True])
        dialog.deleteLater()

    def test_followup_cancel_emits_without_closing_until_complete(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Follow-up",
            runner=runner,
            delay_ms=0,
            close_on_success=False,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)
        cancel_log = _SignalLog(dialog.cancel_requested)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            proceed.wait(timeout=5)
            return "ok"

        try:
            runner.start(work, None)
            presented.wait()
        finally:
            proceed.set()
        finished.wait()
        QApplication.sendPostedEvents()
        self._app.processEvents()

        self.assertTrue(dialog.isVisible())
        dialog._cancel_btn.click()
        self.assertEqual(cancel_log.count, 1)
        self.assertTrue(dialog.isVisible())
        dialog.complete()
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

    def test_close_on_success_false_fast_complete_does_not_flash(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Rychlé dojetí",
            runner=runner,
            delay_ms=300,
            close_on_success=False,
        )
        succeeded = _SignalLog(runner.succeeded)
        presented = _SignalLog(dialog.presented)

        def work(_ctx: LongOperationContext, snapshot: object) -> object:
            return snapshot

        runner.start(work, True)
        succeeded.wait()
        dialog.complete()
        QApplication.sendPostedEvents()
        self._app.processEvents()

        self.assertFalse(dialog.was_presented())
        self.assertFalse(dialog.isVisible())
        self.assertEqual(presented.count, 0)
        self.assertFalse(dialog._show_timer.isActive())
        dialog.deleteLater()

    def test_default_close_on_success_still_hides_after_succeeded(self) -> None:
        runner = LongOperationRunner()
        dialog = LongOperationDialog(
            None,
            title="Samostatná operace",
            runner=runner,
            delay_ms=0,
        )
        proceed = threading.Event()
        presented = _SignalLog(dialog.presented)
        finished = _SignalLog(runner.finished)

        def work(ctx: LongOperationContext, _snapshot: object) -> object:
            ctx.set_phase("Počítám…")
            proceed.wait(timeout=5)
            return "done"

        try:
            runner.start(work, None)
            presented.wait()
            self.assertTrue(dialog.isVisible())
        finally:
            proceed.set()
        finished.wait()
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()


class ChunkedUiPumpTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_batches_preserve_order_and_process_once(self) -> None:
        pump = ChunkedUiPump()
        collected: list[int] = []
        order: list[object] = []
        progress: list[tuple[int, int]] = []
        pump.progress.connect(lambda done, total: progress.append((done, total)))

        def consumer(batch) -> None:
            order.append(("batch", list(batch)))
            collected.extend(batch)

        finished = _SignalLog(pump.finished)
        succeeded = _SignalLog(pump.succeeded)
        self.assertTrue(pump.start(range(1, 7), consumer, batch_size=2))
        QTimer.singleShot(0, lambda: order.append("loop"))
        finished.wait()

        self.assertEqual(collected, [1, 2, 3, 4, 5, 6])
        self.assertEqual(collected.count(1), 1)
        self.assertIn("loop", order)
        self.assertLess(order.index("loop"), order.index(("batch", [3, 4])))
        self.assertEqual(progress, [(2, 6), (4, 6), (6, 6)])
        self.assertEqual(succeeded.count, 1)
        self.assertEqual(finished.count, 1)

    def test_empty_collection_succeeds(self) -> None:
        pump = ChunkedUiPump()
        called: list = []
        finished = _SignalLog(pump.finished)
        succeeded = _SignalLog(pump.succeeded)
        progress = _SignalLog(pump.progress)

        def consumer(batch) -> None:
            called.append(list(batch))

        self.assertTrue(pump.start([], consumer, batch_size=10))
        finished.wait()
        self.assertEqual(called, [])
        self.assertEqual(succeeded.count, 1)
        self.assertEqual(progress.count, 1)
        self.assertEqual(progress.items[0], (0, 0))

    def test_cancel_stops_further_batches_and_is_not_success(self) -> None:
        pump = ChunkedUiPump()
        collected: list[int] = []
        finished = _SignalLog(pump.finished)
        succeeded = _SignalLog(pump.succeeded)
        cancelled = _SignalLog(pump.cancelled)

        def consumer(batch) -> None:
            collected.extend(batch)
            pump.request_cancel()

        pump.start([1, 2, 3, 4, 5], consumer, batch_size=2)
        finished.wait()
        self.assertEqual(collected, [1, 2])
        self.assertEqual(cancelled.count, 1)
        self.assertEqual(succeeded.count, 0)

    def test_stale_generation_after_new_start_is_ignored(self) -> None:
        pump = ChunkedUiPump()
        first: list[int] = []
        second: list[int] = []
        finished = _SignalLog(pump.finished)

        pump.start([1, 2, 3, 4], lambda batch: first.extend(batch), batch_size=2)
        finished.wait()
        old_generation = pump._generation

        finished2 = _SignalLog(pump.finished)
        pump.start([9, 8], lambda batch: second.extend(batch), batch_size=2)
        pump._run_batch(old_generation)
        finished2.wait()
        self.assertEqual(second, [9, 8])
        self.assertEqual(first, [1, 2, 3, 4])

    def test_second_start_while_running_is_rejected(self) -> None:
        pump = ChunkedUiPump()
        finished = _SignalLog(pump.finished)

        self.assertTrue(pump.start([1, 2, 3], lambda _batch: None, batch_size=1))
        self.assertFalse(pump.start([9], lambda _batch: None, batch_size=1))
        finished.wait()

    def test_consumer_exception_is_failure(self) -> None:
        pump = ChunkedUiPump()
        finished = _SignalLog(pump.finished)
        succeeded = _SignalLog(pump.succeeded)
        failed = _SignalLog(pump.failed)

        def consumer(_batch) -> None:
            raise ValueError("Řádek nelze vložit.")

        pump.start(["a", "b"], consumer, batch_size=10)
        finished.wait()
        self.assertEqual(failed.count, 1)
        self.assertEqual(failed.items[0][0], "Řádek nelze vložit.")
        self.assertEqual(succeeded.count, 0)


if __name__ == "__main__":
    unittest.main()
