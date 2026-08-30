"""SIMILARITY-LOCATION-DISPLAY-3: čitelnější umístění výsledků analýzy podobností."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="similarity-loc-3-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QHeaderView,
        QStyleOptionViewItem,
    )

    from core.database.database_initializer import initialize_database
    from core.shared.sluzby.similarity_checked_pair_service import (
        SIMILARITY_ENTITY_AUDIT_ASSERTION,
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    )
    from core.shared.sluzby.similarity_domain import (
        SCOPE_AUDIT,
        SCOPE_LEGAL,
        SCOPE_PROVERKY,
        SCOPE_RISKS,
        domain_label,
    )
    from core.shared.sluzby.similarity_domain_analysis import SimilarityAnalysisPair
    from core.shared.sluzby.similarity_item_collectors import SimilarityItem
    from core.shared.sluzby.similarity_location_format import (
        LOCATION_PATH_SEPARATOR,
        format_similarity_location,
        similarity_location_root,
    )
    from core.ui.similarity_analysis_dialog import (
        FLOW_CANCELLED,
        FLOW_PREPARING_RESULTS,
        FLOW_RESULTS_READY,
        LocationElideLeftDelegate,
        SimilarityAnalysisDialog,
        SimilarityAnalysisSnapshot,
        _COL_LEFT_LOCATION,
        _COL_LEFT_TEXT,
        _COL_RIGHT_LOCATION,
        _COL_RIGHT_TEXT,
        _RESULT_LOCATION_COLUMNS,
        _RESULT_QUESTION_COLUMNS,
    )
    from core.widgets.info_tooltip import wrap_tooltip_text
    from moduly.audity.constants import MODULE_NAME as AUDIT_MODULE
    from moduly.proverky.constants import MODULE_NAME as PROVERKY_MODULE
    from moduly.rizeni_rizik.constants import MODULE_NAME as RISKS_MODULE

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _item(
    item_id: str,
    text: str,
    *,
    location: str,
    entity_type: str = SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
) -> SimilarityItem:
    return SimilarityItem(
        entity_type=entity_type,
        composite_id=item_id,
        text=text,
        location_label=location,
    )


def _pair(
    left: SimilarityItem,
    right: SimilarityItem,
    *,
    score: float = 0.9,
) -> SimilarityAnalysisPair:
    return SimilarityAnalysisPair(
        score=score,
        match_type="possible",
        match_label="Možná podobnost",
        left=left,
        right=right,
        pair_entity_type=f"cross:{left.entity_type}:{right.entity_type}",
    )


def _select_scope(combo, key: str) -> None:
    index = combo.findData(key)
    if index < 0:
        raise AssertionError(f"Oblast {key} není v comboboxu.")
    combo.setCurrentIndex(index)


def _wait_pump(dialog: SimilarityAnalysisDialog, timeout_ms: int = 8000) -> None:
    if not dialog._pump.is_running() and dialog._flow_state != FLOW_PREPARING_RESULTS:
        return
    loop = QEventLoop()
    dialog._pump.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    dialog._pump.finished.disconnect(loop.quit)
    timer.stop()
    QApplication.sendPostedEvents()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


class FormatSimilarityLocationTestCase(unittest.TestCase):
    def test_strips_exact_root_at_start(self) -> None:
        full = f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Řízení kompetencí{LOCATION_PATH_SEPARATOR}Cíle"
        self.assertEqual(
            format_similarity_location(full, AUDIT_MODULE),
            f"Řízení kompetencí{LOCATION_PATH_SEPARATOR}Cíle",
        )

    def test_does_not_strip_root_in_the_middle(self) -> None:
        full = (
            f"Jiná oblast{LOCATION_PATH_SEPARATOR}{AUDIT_MODULE}"
            f"{LOCATION_PATH_SEPARATOR}Cíle"
        )
        self.assertEqual(format_similarity_location(full, AUDIT_MODULE), full)

    def test_does_not_strip_different_root(self) -> None:
        full = f"{PROVERKY_MODULE}{LOCATION_PATH_SEPARATOR}Oblast{LOCATION_PATH_SEPARATOR}Sekce"
        self.assertEqual(format_similarity_location(full, AUDIT_MODULE), full)

    def test_empty_path(self) -> None:
        self.assertEqual(format_similarity_location("", AUDIT_MODULE), "")
        self.assertEqual(format_similarity_location(None, AUDIT_MODULE), "")

    def test_empty_root_keeps_path(self) -> None:
        full = f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Cíle"
        self.assertEqual(format_similarity_location(full, ""), full)
        self.assertEqual(format_similarity_location(full, None), full)

    def test_path_without_separator(self) -> None:
        self.assertEqual(
            format_similarity_location("Audity systémů řízení bez šipek", AUDIT_MODULE),
            "Audity systémů řízení bez šipek",
        )

    def test_path_equal_to_root_is_kept(self) -> None:
        self.assertEqual(
            format_similarity_location(AUDIT_MODULE, AUDIT_MODULE),
            AUDIT_MODULE,
        )

    def test_root_plus_separator_only_keeps_original(self) -> None:
        full = f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}"
        result = format_similarity_location(full, AUDIT_MODULE)
        self.assertTrue(result.strip())
        self.assertTrue(result.startswith(AUDIT_MODULE))

    def test_historical_slash_path_is_unchanged(self) -> None:
        full = f"{AUDIT_MODULE} / Řízení kompetencí / Cíle"
        self.assertEqual(format_similarity_location(full, AUDIT_MODULE), full)

    def test_same_and_different_roots_per_side(self) -> None:
        left = f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Proces{LOCATION_PATH_SEPARATOR}Kritérium"
        right_same = f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Jiný proces"
        right_other = (
            f"{PROVERKY_MODULE}{LOCATION_PATH_SEPARATOR}Oblast"
            f"{LOCATION_PATH_SEPARATOR}Sekce"
        )
        self.assertEqual(
            format_similarity_location(left, AUDIT_MODULE),
            f"Proces{LOCATION_PATH_SEPARATOR}Kritérium",
        )
        self.assertEqual(
            format_similarity_location(right_same, AUDIT_MODULE),
            "Jiný proces",
        )
        self.assertEqual(
            format_similarity_location(right_other, PROVERKY_MODULE),
            f"Oblast{LOCATION_PATH_SEPARATOR}Sekce",
        )
        self.assertEqual(format_similarity_location(right_other, AUDIT_MODULE), right_other)


class SimilarityLocationRootTestCase(unittest.TestCase):
    def test_roots_are_module_names_not_hardcoded_pair(self) -> None:
        self.assertEqual(similarity_location_root(SCOPE_AUDIT), AUDIT_MODULE)
        self.assertEqual(similarity_location_root(SCOPE_PROVERKY), PROVERKY_MODULE)
        self.assertEqual(similarity_location_root(SCOPE_RISKS), RISKS_MODULE)
        self.assertEqual(similarity_location_root(SCOPE_LEGAL), domain_label(SCOPE_LEGAL))
        self.assertNotEqual(similarity_location_root(SCOPE_AUDIT), domain_label(SCOPE_AUDIT))
        self.assertNotEqual(
            similarity_location_root(SCOPE_PROVERKY),
            domain_label(SCOPE_PROVERKY),
        )


class SimilarityLocationDisplayDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def _dialog(self) -> SimilarityAnalysisDialog:
        return SimilarityAnalysisDialog()

    def _audit_proverky_pair(self) -> SimilarityAnalysisPair:
        left = _item(
            "audit::p::c::t1",
            "Auditní tvrzení o kompetencích",
            location=(
                f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Řízení kompetencí"
                f"{LOCATION_PATH_SEPARATOR}Integrované požadavky QMS"
            ),
            entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
        )
        right = _item(
            "prov::a::s::i1",
            "Kontrolní otázka prověrky",
            location=(
                f"{PROVERKY_MODULE}{LOCATION_PATH_SEPARATOR}Dokumentace"
                f"{LOCATION_PATH_SEPARATOR}Evidence"
            ),
            entity_type=SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        )
        return _pair(left, right)

    def _show_with_snapshot(
        self,
        dialog: SimilarityAnalysisDialog,
        scope_a: str,
        scope_b: str,
        pairs: list,
    ) -> None:
        dialog._result_snapshot = SimilarityAnalysisSnapshot(scope_a, scope_b)
        dialog._pairs = list(pairs)
        dialog._cancelled = False
        dialog._show_results()

    def test_headings_two_different_domains(self) -> None:
        dialog = self._dialog()
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        self.assertFalse(dialog._scope_info_row.isHidden())
        self.assertEqual(
            dialog._scope_first_label.full_text(),
            f"První otázka: {AUDIT_MODULE}",
        )
        self.assertEqual(
            dialog._scope_second_label.full_text(),
            f"Druhá otázka: {PROVERKY_MODULE}",
        )
        dialog.close()

    def test_headings_same_domain_against_itself(self) -> None:
        dialog = self._dialog()
        pair = _pair(
            _item(
                "a1",
                "První",
                location=f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Proces A{LOCATION_PATH_SEPARATOR}K1",
                entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
            ),
            _item(
                "a2",
                "Druhá",
                location=f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Proces B{LOCATION_PATH_SEPARATOR}K2",
                entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
            ),
        )
        self._show_with_snapshot(dialog, SCOPE_AUDIT, SCOPE_AUDIT, [pair])
        self.assertEqual(
            dialog._scope_first_label.full_text(),
            f"První otázka: {AUDIT_MODULE}",
        )
        self.assertEqual(
            dialog._scope_second_label.full_text(),
            f"Druhá otázka: {AUDIT_MODULE}",
        )
        dialog.close()

    def test_headings_follow_completed_snapshot_not_combos(self) -> None:
        dialog = self._dialog()
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        _select_scope(dialog._scope_a_combo, SCOPE_LEGAL)
        _select_scope(dialog._scope_b_combo, SCOPE_LEGAL)
        dialog._update_scope_headings()
        self.assertEqual(
            dialog._scope_first_label.full_text(),
            f"První otázka: {AUDIT_MODULE}",
        )
        self.assertEqual(
            dialog._scope_second_label.full_text(),
            f"Druhá otázka: {PROVERKY_MODULE}",
        )
        self.assertNotEqual(dialog._selected_scope_a(), SCOPE_AUDIT)
        dialog.close()

    def test_new_analysis_updates_both_heading_names(self) -> None:
        dialog = self._dialog()
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        pair = _pair(
            _item(
                "l1",
                "Požadavek",
                location=f"Právní požadavky{LOCATION_PATH_SEPARATOR}BOZP{LOCATION_PATH_SEPARATOR}Zákon",
            ),
            _item(
                "r1",
                "Riziko",
                location=f"{RISKS_MODULE}{LOCATION_PATH_SEPARATOR}Sklad{LOCATION_PATH_SEPARATOR}Pád",
            ),
        )
        self._show_with_snapshot(dialog, SCOPE_LEGAL, SCOPE_RISKS, [pair])
        self.assertEqual(
            dialog._scope_first_label.full_text(),
            "První otázka: Právní požadavky",
        )
        self.assertEqual(
            dialog._scope_second_label.full_text(),
            f"Druhá otázka: {RISKS_MODULE}",
        )
        dialog.close()

    def test_headings_are_not_hardcoded_to_audit_and_proverky(self) -> None:
        dialog = self._dialog()
        pair = _pair(
            _item(
                "l1",
                "Požadavek",
                location="Právní požadavky → BOZP → Zákon",
            ),
            _item(
                "r1",
                "Riziko",
                location=f"{RISKS_MODULE} → Sklad → Pád",
            ),
        )
        self._show_with_snapshot(dialog, SCOPE_LEGAL, SCOPE_RISKS, [pair])
        first = dialog._scope_first_label.full_text()
        second = dialog._scope_second_label.full_text()
        self.assertNotIn(AUDIT_MODULE, first)
        self.assertNotIn(PROVERKY_MODULE, second)
        self.assertIn("Právní požadavky", first)
        self.assertIn(RISKS_MODULE, second)
        dialog.close()

    def test_long_heading_does_not_change_table_column_layout(self) -> None:
        dialog = self._dialog()
        dialog.resize(1600, 900)
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        dialog.show()
        QApplication.processEvents()
        table = dialog._results_table
        header = table.horizontalHeader()
        widths = [table.columnWidth(i) for i in range(table.columnCount())]
        modes = [header.sectionResizeMode(i) for i in range(table.columnCount())]
        long_name = "Velmi dlouhý název porovnávané oblasti " * 12
        with patch(
            "core.ui.similarity_analysis_dialog.similarity_location_root",
            return_value=long_name,
        ):
            dialog._update_scope_headings()
        QApplication.processEvents()
        self.assertEqual(
            [header.sectionResizeMode(i) for i in range(table.columnCount())],
            modes,
        )
        self.assertEqual(
            [table.columnWidth(i) for i in range(table.columnCount())],
            widths,
        )
        self.assertEqual(
            dialog._scope_first_label.full_text(),
            f"První otázka: {long_name}",
        )
        dialog._scope_first_label.setFixedWidth(90)
        dialog._scope_first_label._apply_elide()
        self.assertNotEqual(
            dialog._scope_first_label.text(),
            dialog._scope_first_label.full_text(),
        )
        self.assertTrue(dialog._scope_first_label.toolTip())
        dialog.close()

    def test_visible_location_is_relative_tooltip_is_full_path(self) -> None:
        dialog = self._dialog()
        pair = self._audit_proverky_pair()
        self._show_with_snapshot(dialog, SCOPE_AUDIT, SCOPE_PROVERKY, [pair])
        table = dialog._results_table
        left_item = table.item(0, _COL_LEFT_LOCATION)
        right_item = table.item(0, _COL_RIGHT_LOCATION)
        self.assertEqual(
            left_item.text(),
            f"Řízení kompetencí{LOCATION_PATH_SEPARATOR}Integrované požadavky QMS",
        )
        self.assertEqual(
            right_item.text(),
            f"Dokumentace{LOCATION_PATH_SEPARATOR}Evidence",
        )
        self.assertEqual(left_item.toolTip(), wrap_tooltip_text(pair.left.location_label))
        self.assertEqual(right_item.toolTip(), wrap_tooltip_text(pair.right.location_label))
        self.assertIn(AUDIT_MODULE, pair.left.location_label)
        self.assertNotIn(AUDIT_MODULE, left_item.text())
        stored = table.item(0, 2).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(stored.left.location_label, pair.left.location_label)
        self.assertEqual(stored.right.location_label, pair.right.location_label)
        dialog.close()

    def test_location_columns_elide_left_questions_do_not(self) -> None:
        dialog = self._dialog()
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        table = dialog._results_table
        self.assertIs(
            table.itemDelegateForColumn(_COL_LEFT_LOCATION),
            dialog._location_delegate,
        )
        self.assertIs(
            table.itemDelegateForColumn(_COL_RIGHT_LOCATION),
            dialog._location_delegate,
        )
        self.assertIsInstance(dialog._location_delegate, LocationElideLeftDelegate)
        self.assertIsNot(
            table.itemDelegateForColumn(_COL_LEFT_TEXT),
            dialog._location_delegate,
        )
        self.assertIsNot(
            table.itemDelegateForColumn(_COL_RIGHT_TEXT),
            dialog._location_delegate,
        )
        left_opt = QStyleOptionViewItem()
        dialog._location_delegate.initStyleOption(
            left_opt,
            table.model().index(0, _COL_LEFT_LOCATION),
        )
        self.assertEqual(left_opt.textElideMode, Qt.TextElideMode.ElideLeft)
        right_opt = QStyleOptionViewItem()
        dialog._location_delegate.initStyleOption(
            right_opt,
            table.model().index(0, _COL_RIGHT_LOCATION),
        )
        self.assertEqual(right_opt.textElideMode, Qt.TextElideMode.ElideLeft)
        question_index = table.model().index(0, _COL_LEFT_TEXT)
        question_delegate = table.itemDelegate()
        self.assertIsNotNone(question_delegate)
        self.assertIsNot(question_delegate, dialog._location_delegate)
        question_opt = QStyleOptionViewItem()
        question_delegate.initStyleOption(question_opt, question_index)
        self.assertNotEqual(question_opt.textElideMode, Qt.TextElideMode.ElideLeft)
        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertFalse(
            table.item(0, _COL_LEFT_LOCATION).text().startswith("…")
        )
        dialog.close()

    def test_resize_refresh_does_not_clear_full_location_tooltip(self) -> None:
        dialog = self._dialog()
        pair = self._audit_proverky_pair()
        self._show_with_snapshot(dialog, SCOPE_AUDIT, SCOPE_PROVERKY, [pair])
        table = dialog._results_table
        header = table.horizontalHeader()
        for column in _RESULT_LOCATION_COLUMNS + _RESULT_QUESTION_COLUMNS:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(column, 600)
        QApplication.processEvents()
        dialog._refresh_result_tooltips()
        self.assertEqual(
            table.item(0, _COL_LEFT_LOCATION).toolTip(),
            wrap_tooltip_text(pair.left.location_label),
        )
        self.assertEqual(
            table.item(0, _COL_RIGHT_LOCATION).toolTip(),
            wrap_tooltip_text(pair.right.location_label),
        )
        dialog.close()

    def test_column_count_order_and_resize_modes_unchanged(self) -> None:
        dialog = self._dialog()
        table = dialog._results_table
        header = table.horizontalHeader()
        self.assertEqual(table.columnCount(), 7)
        self.assertEqual(
            [
                table.horizontalHeaderItem(i).text()
                for i in range(table.columnCount())
            ],
            [
                "",
                "Podobnost",
                "Stav",
                "První otázka",
                "Umístění první",
                "Druhá otázka",
                "Umístění druhé",
            ],
        )
        self.assertEqual(
            header.sectionResizeMode(0),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.assertEqual(
            header.sectionResizeMode(1),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.assertEqual(
            header.sectionResizeMode(2),
            QHeaderView.ResizeMode.ResizeToContents,
        )
        for column in (3, 4, 5, 6):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Stretch,
            )
        dialog.close()

    def test_pump_does_not_run_global_tooltip_pass(self) -> None:
        dialog = self._dialog()
        dialog._progress_delay_ms = 0
        dialog._result_batch_size = 50
        dialog._result_snapshot = SimilarityAnalysisSnapshot(
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
        )
        pairs = [
            _pair(
                _item(
                    f"L{i}",
                    f"Text L{i}",
                    location=f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}P{i}{LOCATION_PATH_SEPARATOR}K{i}",
                    entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
                ),
                _item(
                    f"R{i}",
                    f"Text R{i}",
                    location=(
                        f"{PROVERKY_MODULE}{LOCATION_PATH_SEPARATOR}O{i}"
                        f"{LOCATION_PATH_SEPARATOR}S{i}"
                    ),
                ),
            )
            for i in range(1000)
        ]
        with patch(
            "core.ui.similarity_analysis_dialog.refresh_elided_cell_tooltips"
        ) as spy:
            dialog._begin_prepare_results(pairs)
            _wait_pump(dialog)
            spy.assert_not_called()
        self.assertEqual(dialog._flow_state, FLOW_RESULTS_READY)
        self.assertEqual(dialog._results_table.rowCount(), 1000)
        self.assertEqual(
            dialog._results_table.item(0, _COL_LEFT_LOCATION).text(),
            f"P0{LOCATION_PATH_SEPARATOR}K0",
        )
        self.assertIn(
            AUDIT_MODULE,
            dialog._results_table.item(0, _COL_LEFT_LOCATION).toolTip(),
        )
        dialog.close()

    def test_cancel_during_pump_hides_headings_and_partial_table(self) -> None:
        dialog = self._dialog()
        dialog._result_batch_size = 2
        dialog._result_snapshot = SimilarityAnalysisSnapshot(
            SCOPE_AUDIT,
            SCOPE_AUDIT,
        )
        pairs = [
            _pair(
                _item(f"L{i}", f"L{i}", location=f"{AUDIT_MODULE} → P{i}"),
                _item(f"R{i}", f"R{i}", location=f"{AUDIT_MODULE} → Q{i}"),
            )
            for i in range(40)
        ]
        original = dialog._consume_result_batch

        def consume(batch) -> None:
            original(batch)
            dialog._pump.request_cancel()

        dialog._consume_result_batch = consume
        dialog._begin_prepare_results(pairs)
        _wait_pump(dialog)
        self.assertEqual(dialog._flow_state, FLOW_CANCELLED)
        self.assertEqual(dialog._results_table.rowCount(), 0)
        self.assertTrue(dialog._scope_info_row.isHidden())
        dialog.close()

    def test_back_to_setup_hides_headings(self) -> None:
        dialog = self._dialog()
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        self.assertFalse(dialog._scope_info_row.isHidden())
        dialog._back_to_setup()
        self.assertTrue(dialog._scope_info_row.isHidden())
        self.assertIsNone(dialog._result_snapshot)
        dialog.close()

    def test_1600x900_headings_and_controls_remain_usable(self) -> None:
        dialog = self._dialog()
        dialog.resize(1600, 900)
        self._show_with_snapshot(
            dialog,
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
            [self._audit_proverky_pair()],
        )
        dialog.show()
        QApplication.processEvents()
        self.assertTrue(dialog._scope_first_label.isVisible())
        self.assertTrue(dialog._scope_second_label.isVisible())
        self.assertTrue(dialog._results_table.isVisible())
        self.assertTrue(dialog._open_first_btn.isVisible())
        self.assertTrue(dialog._open_second_btn.isVisible())
        self.assertTrue(dialog._open_both_btn.isVisible())
        self.assertGreaterEqual(dialog.width(), 1500)
        self.assertGreater(dialog._results_table.width(), 1000)
        self.assertTrue(dialog._scope_first_label.full_text())
        self.assertTrue(dialog._scope_second_label.full_text())
        dialog.close()


class SimilarityLocationOpenTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_open_uses_original_item_identity_not_visible_text(self) -> None:
        dialog = SimilarityAnalysisDialog()
        left = _item(
            "audit::proc::crit::t1",
            "Text první",
            location=(
                f"{AUDIT_MODULE}{LOCATION_PATH_SEPARATOR}Řízení kompetencí"
                f"{LOCATION_PATH_SEPARATOR}Integrované požadavky QMS"
            ),
            entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
        )
        right = _item(
            "area::sekce::bod1",
            "Text druhá",
            location=(
                f"{PROVERKY_MODULE}{LOCATION_PATH_SEPARATOR}Dokumentace"
                f"{LOCATION_PATH_SEPARATOR}Evidence"
            ),
            entity_type=SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
        )
        pair = _pair(left, right)
        dialog._result_snapshot = SimilarityAnalysisSnapshot(
            SCOPE_AUDIT,
            SCOPE_PROVERKY,
        )
        dialog._pairs = [pair]
        dialog._show_results()
        dialog._results_table.selectRow(0)
        visible_left = dialog._results_table.item(0, _COL_LEFT_LOCATION).text()
        self.assertNotEqual(visible_left, left.location_label)

        opened: list[tuple[str, str]] = []

        def fake_open(_parent, item):
            opened.append((item.entity_type, item.composite_id))

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
                (SIMILARITY_ENTITY_AUDIT_ASSERTION, "audit::proc::crit::t1"),
                (SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT, "area::sekce::bod1"),
                (SIMILARITY_ENTITY_AUDIT_ASSERTION, "audit::proc::crit::t1"),
                (SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT, "area::sekce::bod1"),
            ],
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()
