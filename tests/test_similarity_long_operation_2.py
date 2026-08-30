"""SIMILARITY-LONG-OPERATION-2: napojení analýzy na dlouhé operace a UI pumpu."""

from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-lo-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import QEventLoop, Qt, QThread, QTimer
    from PySide6.QtWidgets import QApplication

    from core.database.database_initializer import initialize_database
    from core.shared.sluzby.similarity_domain import SCOPE_PROVERKY
    from core.shared.sluzby.similarity_domain_analysis import (
        SimilarityAnalysisPair,
        analyze_domain_similarities,
    )
    from core.shared.sluzby.similarity_item_collectors import SimilarityItem
    from core.ui.similarity_analysis_dialog import (
        FLOW_ANALYZING,
        FLOW_CANCELLED,
        FLOW_IDLE,
        FLOW_PREPARING_RESULTS,
        FLOW_RESULTS_READY,
        PHASE_ANALYZING,
        PHASE_PREPARING_RESULTS,
        PREPARING_CANCELLED_MESSAGE,
        SimilarityAnalysisDialog,
        SimilarityAnalysisSnapshot,
        run_similarity_analysis,
    )

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _SignalLog:
    def __init__(self, signal) -> None:
        self.items: list[tuple] = []
        self._signal = signal
        signal.connect(self._on)

    def _on(self, *args) -> None:
        self.items.append(args)

    @property
    def count(self) -> int:
        return len(self.items)

    def wait(self, timeout_ms: int = 4000) -> None:
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


def _item(
    item_id: str,
    text: str,
    *,
    location: str = "Umístění",
    entity_type: str = "proverky_kontrolni_otazka",
) -> SimilarityItem:
    return SimilarityItem(
        entity_type=entity_type,
        composite_id=item_id,
        text=text,
        location_label=location,
    )


def _pair(
    left_id: str,
    right_id: str,
    *,
    checked: bool = False,
    score: float = 0.9,
    text_left: str | None = None,
    text_right: str | None = None,
) -> SimilarityAnalysisPair:
    return SimilarityAnalysisPair(
        score=score,
        match_type="possible",
        match_label="Možná podobnost",
        left=_item(left_id, text_left or f"Text {left_id}"),
        right=_item(right_id, text_right or f"Text {right_id}"),
        checked=checked,
        pair_entity_type="proverky_kontrolni_otazka",
    )


def _wait_pump(dialog: SimilarityAnalysisDialog, log: _SignalLog, timeout_ms: int = 8000) -> None:
    if not dialog._pump.is_running() and dialog._flow_state != FLOW_PREPARING_RESULTS:
        return
    log.wait(timeout_ms=timeout_ms)
    QApplication.sendPostedEvents()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


class SimilarityLongOperation2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def _dialog(self) -> SimilarityAnalysisDialog:
        dialog = SimilarityAnalysisDialog()
        dialog._progress_delay_ms = 0
        dialog._result_batch_size = 50
        return dialog

    def test_domain_worker_class_is_gone(self) -> None:
        import core.ui.similarity_analysis_dialog as module

        self.assertFalse(hasattr(module, "_DomainAnalysisWorker"))
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("class _DomainAnalysisWorker", source)
        self.assertIn("LongOperationRunner", source)
        self.assertIn("ChunkedUiPump", source)

    def test_run_similarity_analysis_matches_service(self) -> None:
        catalog = [
            _item("1", "Stejný bezpečnostní text"),
            _item("2", "Stejný bezpečnostní text."),
            _item("3", "Úplně odlišný obsah qwerty"),
        ]
        snapshot = SimilarityAnalysisSnapshot(
            scope_a=SCOPE_PROVERKY,
            scope_b=SCOPE_PROVERKY,
        )

        class _Ctx:
            def set_phase(self, *_args, **_kwargs) -> None:
                return None

            def set_progress(self, *_args, **_kwargs) -> None:
                return None

            def set_status(self, *_args, **_kwargs) -> None:
                return None

            def is_cancel_requested(self) -> bool:
                return False

        with patch(
            "core.shared.sluzby.similarity_domain_analysis.collect_similarity_items",
            return_value=catalog,
        ):
            expected, expected_cancelled = analyze_domain_similarities(
                SCOPE_PROVERKY, SCOPE_PROVERKY, include_checked=False
            )
            result = run_similarity_analysis(_Ctx(), snapshot)

        self.assertFalse(expected_cancelled)
        self.assertFalse(result.cancelled)
        self.assertEqual(len(result.pairs), len(expected))
        self.assertEqual(
            [pair.normalized_ids for pair in result.pairs],
            [pair.normalized_ids for pair in expected],
        )
        self.assertEqual(
            [pair.score for pair in result.pairs],
            [pair.score for pair in expected],
        )

    def test_analysis_uses_runner_off_gui_thread_with_progress(self) -> None:
        dialog = self._dialog()
        main_thread = QThread.currentThread()
        seen: dict[str, object] = {}
        pair = _pair("a", "b")
        proceed = threading.Event()
        entered = threading.Event()
        runner_done = _SignalLog(dialog._runner.finished)
        pump_done = _SignalLog(dialog._pump.finished)
        status = _SignalLog(dialog._runner.status_changed)
        progress = _SignalLog(dialog._runner.progress_changed)
        phases = _SignalLog(dialog._runner.phase_changed)
        progress_dialog = dialog._ensure_progress_dialog()
        presented = _SignalLog(progress_dialog.presented)

        def fake_analyze(*_args, **kwargs):
            seen["worker_thread"] = QThread.currentThread()
            callback = kwargs.get("progress_callback")
            if callback is not None:
                callback(3, 10, 7)
            entered.set()
            proceed.wait(timeout=5)
            return ([pair], False)

        try:
            with patch(
                "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
                side_effect=fake_analyze,
            ), patch.object(dialog, "_refresh_scope_estimates"):
                dialog._start_analysis()
                presented.wait()
                self.assertTrue(entered.wait(timeout=2))
                status.wait()
                progress.wait()
                self.assertTrue(dialog._runner.is_running())
                self.assertIsNot(seen["worker_thread"], main_thread)
                self.assertEqual(dialog._flow_state, FLOW_ANALYZING)
                self.assertEqual(
                    dialog._progress_dialog._phase_label.text(), PHASE_ANALYZING
                )
                self.assertEqual(dialog._progress_dialog._count_label.text(), "3 / 10")
                self.assertEqual(
                    dialog._progress_dialog._status_label.text(),
                    "Nalezeno kandidátů: 7",
                )
                self.assertTrue(dialog._progress_dialog.isVisible())
                self.assertFalse(dialog._start_btn.isEnabled())
        finally:
            proceed.set()

        runner_done.wait()
        _wait_pump(dialog, pump_done)
        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertFalse(dialog._progress_dialog.isVisible())
        self.assertIsNone(dialog._runner._thread)
        self.assertFalse(dialog._pump.is_running())
        self.assertTrue(any(item[0] == PHASE_ANALYZING for item in phases.items))
        dialog.close()

    def test_dialog_stays_visible_between_worker_and_pump(self) -> None:
        dialog = self._dialog()
        dialog._result_batch_size = 1
        pairs = [_pair(str(i), str(i + 1000)) for i in range(8)]
        proceed = threading.Event()
        runner_done = _SignalLog(dialog._runner.finished)
        pump_done = _SignalLog(dialog._pump.finished)
        presented = _SignalLog(dialog._ensure_progress_dialog().presented)
        visible_after_success: list[bool] = []
        states_during_pump: list[str] = []
        ready_too_early = False

        def fake_analyze(*_args, **kwargs):
            callback = kwargs.get("progress_callback")
            if callback is not None:
                callback(len(pairs), len(pairs), len(pairs))
            proceed.wait(timeout=5)
            return (pairs, False)

        def on_pump_progress(_done: int, _total: int) -> None:
            nonlocal ready_too_early
            states_during_pump.append(dialog._flow_state)
            if dialog._flow_state == FLOW_RESULTS_READY:
                ready_too_early = True
            progress = dialog._progress_dialog
            visible_after_success.append(
                progress is not None and (progress.isVisible() or progress.is_followup_active())
            )
            self.assertFalse(dialog._open_first_btn.isEnabled())
            self.assertFalse(dialog._start_btn.isEnabled())
            self.assertNotEqual(
                dialog._stack.currentWidget(), dialog._results_page
            )

        dialog._pump.progress.connect(on_pump_progress)

        try:
            with patch(
                "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
                side_effect=fake_analyze,
            ), patch.object(dialog, "_refresh_scope_estimates"):
                dialog._start_analysis()
                presented.wait()
                self.assertTrue(dialog._progress_dialog.isVisible())
        finally:
            proceed.set()

        runner_done.wait()
        QApplication.sendPostedEvents()
        self._app.processEvents()
        self.assertEqual(dialog._flow_state, FLOW_PREPARING_RESULTS)
        self.assertTrue(dialog._progress_dialog.isVisible())
        self.assertEqual(
            dialog._progress_dialog._phase_label.text(), PHASE_PREPARING_RESULTS
        )
        _wait_pump(dialog, pump_done)
        self.assertFalse(ready_too_early)
        self.assertTrue(states_during_pump)
        self.assertTrue(all(state == FLOW_PREPARING_RESULTS for state in states_during_pump))
        self.assertTrue(visible_after_success)
        self.assertTrue(all(visible_after_success))
        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertFalse(dialog._progress_dialog.isVisible())
        self.assertEqual(dialog._stack.currentWidget(), dialog._results_page)
        dialog.close()

    def test_fast_analysis_does_not_lose_followup_phase(self) -> None:
        dialog = self._dialog()
        dialog._progress_delay_ms = 300
        pair = _pair("a", "b")
        runner_done = _SignalLog(dialog._runner.finished)
        pump_done = _SignalLog(dialog._pump.finished)
        progress_dialog = dialog._ensure_progress_dialog()
        presented = _SignalLog(progress_dialog.presented)

        def fake_analyze(*_args, **_kwargs):
            return ([pair], False)

        with patch(
            "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
            side_effect=fake_analyze,
        ), patch.object(dialog, "_refresh_scope_estimates"):
            dialog._start_analysis()
            runner_done.wait()
            _wait_pump(dialog, pump_done)

        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertEqual(presented.count, 0)
        self.assertFalse(dialog._progress_dialog.was_presented())
        dialog.close()

    def test_table_pump_inserts_6317_rows_once_in_order(self) -> None:
        dialog = self._dialog()
        dialog._result_batch_size = 50
        pairs = [_pair(f"L{i}", f"R{i}", score=1.0 - (i / 100000)) for i in range(6317)]
        pairs.append(_pair("checked-a", "checked-b", checked=True))
        pump_done = _SignalLog(dialog._pump.finished)
        loop_marks: list[object] = []
        batch_sizes: list[int] = []
        original_consume = dialog._consume_result_batch

        def consume(batch) -> None:
            batch_sizes.append(len(batch))
            original_consume(batch)

        dialog._consume_result_batch = consume
        dialog._begin_prepare_results(pairs)
        QTimer.singleShot(0, lambda: loop_marks.append("loop"))
        _wait_pump(dialog, pump_done)

        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertEqual(dialog._results_table.rowCount(), 6317)
        self.assertEqual(len(dialog._pairs), 6317)
        self.assertGreater(len(batch_sizes), 1)
        self.assertIn("loop", loop_marks)
        self.assertLess(loop_marks.index("loop"), len(batch_sizes))
        ids = []
        for row in range(dialog._results_table.rowCount()):
            pair = dialog._pair_at_row(row)
            self.assertIsNotNone(pair)
            ids.append(pair.normalized_ids)
            select = dialog._results_table.item(row, 0)
            self.assertEqual(select.checkState(), Qt.CheckState.Unchecked)
            self.assertIs(dialog._results_table.item(row, 2).data(Qt.ItemDataRole.UserRole), pair)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], pairs[0].normalized_ids)
        self.assertEqual(ids[-1], pairs[6316].normalized_ids)
        self.assertNotIn(pairs[-1].normalized_ids, ids)
        self.assertIn("Celkem nalezeno: 6317", dialog._results_counts.text())
        self.assertIn("Analýza dokončena", dialog._results_summary.text())
        dialog.close()

    def test_open_first_second_both_after_pump(self) -> None:
        dialog = self._dialog()
        left = _item(
            "p::a::s::i1",
            "Prověrka",
            entity_type="proverky_kontrolni_otazka",
        )
        right = _item(
            "audit::p::c::t",
            "Audit",
            entity_type="audit_tvrzeni",
        )
        pair = SimilarityAnalysisPair(
            score=0.92,
            match_type="very_similar",
            match_label="Velmi podobné",
            left=left,
            right=right,
            pair_entity_type="cross:proverky_kontrolni_otazka:audit_tvrzeni",
        )
        pump_done = _SignalLog(dialog._pump.finished)
        dialog._result_batch_size = 1
        dialog._begin_prepare_results([pair])
        _wait_pump(dialog, pump_done)
        dialog._results_table.selectRow(0)
        opened: list[str] = []

        def fake_open(_parent, item):
            opened.append(item.entity_type)

        with patch(
            "core.ui.similarity_analysis_dialog.open_similarity_item",
            side_effect=fake_open,
        ):
            dialog._open_selected("first")
            dialog._open_selected("second")
            dialog._open_selected("both")
        self.assertEqual(
            opened,
            [
                "proverky_kontrolni_otazka",
                "audit_tvrzeni",
                "proverky_kontrolni_otazka",
                "audit_tvrzeni",
            ],
        )
        dialog.close()

    def test_cancel_during_worker_keeps_partial_results(self) -> None:
        dialog = self._dialog()
        pair = _pair("a", "b")
        proceed = threading.Event()
        runner_done = _SignalLog(dialog._runner.finished)
        pump_done = _SignalLog(dialog._pump.finished)
        presented = _SignalLog(dialog._ensure_progress_dialog().presented)

        def fake_analyze(*_args, **kwargs):
            callback = kwargs.get("progress_callback")
            should_cancel = kwargs.get("should_cancel")
            if callback is not None:
                callback(1, 4, 1)
            proceed.wait(timeout=5)
            cancelled = bool(should_cancel and should_cancel())
            return ([pair], cancelled)

        try:
            with patch(
                "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
                side_effect=fake_analyze,
            ), patch.object(dialog, "_refresh_scope_estimates"):
                dialog._start_analysis()
                presented.wait()
                dialog._progress_dialog._cancel_btn.click()
        finally:
            proceed.set()

        runner_done.wait()
        _wait_pump(dialog, pump_done)
        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertTrue(dialog._cancelled)
        self.assertEqual(dialog._results_table.rowCount(), 1)
        self.assertIn("Analýza byla zrušena", dialog._results_summary.text())
        dialog._back_to_setup()
        self.assertEqual(dialog._flow_state, FLOW_IDLE)
        dialog.close()

    def test_cancel_during_pump_discards_partial_table(self) -> None:
        dialog = self._dialog()
        dialog._result_batch_size = 2
        pairs = [_pair(str(i), str(i + 50)) for i in range(40)]
        pump_done = _SignalLog(dialog._pump.finished)
        original = dialog._consume_result_batch

        def consume(batch) -> None:
            original(batch)
            dialog._pump.request_cancel()

        dialog._consume_result_batch = consume
        dialog._begin_prepare_results(pairs)
        _wait_pump(dialog, pump_done)

        self.assertEqual(dialog._flow_state, FLOW_CANCELLED)
        self.assertEqual(dialog._results_table.rowCount(), 0)
        self.assertIn(PREPARING_CANCELLED_MESSAGE, dialog._results_summary.text())
        self.assertFalse(dialog._open_first_btn.isEnabled())
        self.assertTrue(dialog._again_btn.isEnabled())
        dialog._back_to_setup()
        self.assertEqual(dialog._flow_state, FLOW_IDLE)
        dialog.close()

    def test_close_during_worker_does_not_block_or_show_results(self) -> None:
        dialog = self._dialog()
        proceed = threading.Event()
        runner_done = _SignalLog(dialog._runner.finished)
        accepted = _SignalLog(dialog.finished)
        presented = _SignalLog(dialog._ensure_progress_dialog().presented)

        def fake_analyze(*_args, **kwargs):
            proceed.wait(timeout=5)
            should_cancel = kwargs.get("should_cancel")
            return ([], bool(should_cancel and should_cancel()))

        try:
            with patch(
                "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
                side_effect=fake_analyze,
            ), patch.object(dialog, "_refresh_scope_estimates"):
                dialog._start_analysis()
                presented.wait()
                dialog.close()
                self.assertTrue(dialog._close_when_idle)
                self.assertEqual(dialog._flow_state, FLOW_ANALYZING)
        finally:
            proceed.set()

        runner_done.wait()
        accepted.wait()
        self.assertFalse(dialog._runner.is_running())
        self.assertIsNone(dialog._runner._thread)
        self.assertNotEqual(dialog._flow_state, FLOW_RESULTS_READY)

    def test_close_during_pump_cancels_and_closes(self) -> None:
        dialog = self._dialog()
        dialog._result_batch_size = 1
        pairs = [_pair(str(i), str(i + 80)) for i in range(30)]
        pump_done = _SignalLog(dialog._pump.finished)
        original = dialog._consume_result_batch

        def consume(batch) -> None:
            original(batch)
            dialog.close()

        dialog._consume_result_batch = consume
        dialog._begin_prepare_results(pairs)
        _wait_pump(dialog, pump_done)
        QApplication.sendPostedEvents()
        self._app.processEvents()
        self.assertEqual(dialog._flow_state, FLOW_CANCELLED)
        self.assertFalse(dialog._pump.is_running())
        self.assertEqual(dialog._results_table.rowCount(), 0)

    def test_worker_exception_returns_to_setup(self) -> None:
        dialog = self._dialog()
        runner_done = _SignalLog(dialog._runner.finished)

        def fake_analyze(*_args, **_kwargs):
            raise RuntimeError("Výpočet selhal.")

        with patch(
            "core.ui.similarity_analysis_dialog.analyze_domain_similarities",
            side_effect=fake_analyze,
        ), patch.object(dialog, "_refresh_scope_estimates"), patch(
            "core.ui.similarity_analysis_dialog.QMessageBox.critical"
        ) as critical:
            dialog._start_analysis()
            runner_done.wait()
            QApplication.sendPostedEvents()
            self._app.processEvents()

        self.assertEqual(dialog._flow_state, FLOW_IDLE)
        self.assertEqual(dialog._stack.currentWidget(), dialog._setup_page)
        self.assertTrue(dialog._start_btn.isEnabled())
        critical.assert_called_once()
        self.assertIsNone(dialog._runner._thread)
        dialog.close()

    def test_pump_consumer_exception_returns_to_setup(self) -> None:
        dialog = self._dialog()
        pairs = [_pair("a", "b"), _pair("c", "d")]
        pump_done = _SignalLog(dialog._pump.finished)

        def consume(_batch) -> None:
            raise ValueError("Řádek nelze vložit.")

        dialog._consume_result_batch = consume
        with patch("core.ui.similarity_analysis_dialog.QMessageBox.critical") as critical:
            dialog._begin_prepare_results(pairs)
            _wait_pump(dialog, pump_done)

        self.assertEqual(dialog._flow_state, FLOW_IDLE)
        self.assertEqual(dialog._results_table.rowCount(), 0)
        self.assertTrue(dialog._start_btn.isEnabled())
        critical.assert_called_once()
        dialog.close()

    def test_new_analysis_allowed_after_outcomes(self) -> None:
        dialog = self._dialog()
        pair = _pair("a", "b")
        pump_done = _SignalLog(dialog._pump.finished)
        dialog._begin_prepare_results([pair])
        _wait_pump(dialog, pump_done)
        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        dialog._back_to_setup()
        self.assertEqual(dialog._flow_state, FLOW_IDLE)
        self.assertTrue(dialog._start_btn.isEnabled())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
