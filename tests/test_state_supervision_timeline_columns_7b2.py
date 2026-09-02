"""STATE-SUPERVISION-TIMELINE-COLUMNS-7B2: šířky sloupců tabulek průběhu."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EditorDialogController
    from core.widgets.table_utils import configure_table_columns
    from moduly.statni_dozor.constants import (
        COL_FINDING_DESCRIPTION,
        COL_FINDING_DUE,
        COL_FINDING_PERSON,
        COL_FINDING_PLACE,
        COL_FINDING_STATUS,
        COL_FINDING_TASK,
        COL_FINDING_TYPE,
        COL_TIMELINE_NOTES,
        COL_TIMELINE_OCCURRED,
        COL_TIMELINE_PLACE,
        COL_TIMELINE_TITLE,
        EMPTY_VALUE,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


_TIMELINE_BASE = {
    COL_TIMELINE_OCCURRED: 145,
    COL_TIMELINE_TITLE: 265,
    COL_TIMELINE_PLACE: 210,
}
_FINDING_BASE = {
    COL_FINDING_TYPE: 205,
    COL_FINDING_DESCRIPTION: 190,
    COL_FINDING_PLACE: 165,
    COL_FINDING_STATUS: 105,
    COL_FINDING_PERSON: 180,
    COL_FINDING_DUE: 105,
}
_LONG_NOTES = (
    "Podrobný zápis z průběhu kontroly skladu chemie včetně ověření BL, "
    "školení a evidence odpadů."
)


class StateSupervisionTimelineColumns7b2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _close(self, dialog: StateSupervisionEditorDialog) -> None:
        editor = getattr(dialog, "_editor", None)
        if editor is not None:
            editor.force_close()
        else:
            dialog.close()

    def _show_course(
        self,
        dialog: StateSupervisionEditorDialog,
        width: int,
        height: int,
    ) -> None:
        dialog.setMaximumSize(max(width, 1920), max(height, 1080))
        dialog.resize(width, height)
        dialog.tabs.setCurrentIndex(dialog._course_tab_index)
        dialog.show()
        for _ in range(3):
            self._app.processEvents()

    def _fill_course(self, dialog: StateSupervisionEditorDialog) -> None:
        dialog._timeline_drafts = [
            StateSupervisionTimelineItemDraft(
                title="Zahájení kontroly",
                place="Vrátnice",
                notes=_LONG_NOTES,
                display_order=0,
            )
        ]
        dialog._findings_drafts = [
            StateSupervisionFindingDraft(
                description="Chybí aktuální BL",
                source_area_label="Sklad chemie",
                display_order=0,
            )
        ]
        dialog._refresh_timeline_table()
        dialog._refresh_findings_table()
        self._app.processEvents()

    def _assert_base_widths(self, table, expected: dict[int, int], *, delta: int = 24) -> None:
        for column, width in expected.items():
            self.assertAlmostEqual(
                table.columnWidth(column),
                width,
                delta=delta,
                msg=f"sloupec {column}: {table.columnWidth(column)} ≠ {width}",
            )

    def _assert_fills_viewport(self, table) -> None:
        used = sum(table.columnWidth(i) for i in range(table.columnCount()))
        viewport = table.viewport().width()
        self.assertGreater(viewport, 0)
        self.assertLessEqual(abs(used - viewport), 8, f"used={used} viewport={viewport}")
        self.assertEqual(table.horizontalScrollBar().maximum(), 0)
        header = table.horizontalHeader()
        for column in range(table.columnCount() - 1):
            right = header.sectionViewportPosition(column) + header.sectionSize(column)
            nxt = header.sectionViewportPosition(column + 1)
            self.assertLessEqual(right, nxt + 1, f"nadpis sloupce {column} zasahuje do {column + 1}")

    def test_01_profiles_set_interactive_then_stretch(self) -> None:
        dialog = StateSupervisionEditorDialog()
        timeline = dialog.timeline_table.horizontalHeader()
        findings = dialog.findings_table.horizontalHeader()
        self.assertEqual(
            timeline.sectionResizeMode(COL_TIMELINE_OCCURRED),
            QHeaderView.ResizeMode.Interactive,
        )
        self.assertEqual(
            timeline.sectionResizeMode(COL_TIMELINE_TITLE),
            QHeaderView.ResizeMode.Interactive,
        )
        self.assertEqual(
            timeline.sectionResizeMode(COL_TIMELINE_PLACE),
            QHeaderView.ResizeMode.Interactive,
        )
        self.assertEqual(
            timeline.sectionResizeMode(COL_TIMELINE_NOTES),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in _FINDING_BASE:
            self.assertEqual(
                findings.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
                msg=f"finding col {column}",
            )
        self.assertEqual(
            findings.sectionResizeMode(COL_FINDING_TASK),
            QHeaderView.ResizeMode.Stretch,
        )
        dialog.close()

    def test_02_viewports_filled_at_1600_and_1920(self) -> None:
        dialog = StateSupervisionEditorDialog()
        measured: dict[tuple[int, int], dict[str, list[int]]] = {}
        for width, height in ((1600, 900), (1920, 1080)):
            self._show_course(dialog, width, height)
            self._fill_course(dialog)
            for name, table, base in (
                ("timeline", dialog.timeline_table, _TIMELINE_BASE),
                ("findings", dialog.findings_table, _FINDING_BASE),
            ):
                self._assert_base_widths(table, base)
                self._assert_fills_viewport(table)
                last = table.columnCount() - 1
                self.assertGreater(table.columnWidth(last), 80)
            measured[(width, height)] = {
                "timeline": [
                    dialog.timeline_table.columnWidth(i)
                    for i in range(dialog.timeline_table.columnCount())
                ],
                "findings": [
                    dialog.findings_table.columnWidth(i)
                    for i in range(dialog.findings_table.columnCount())
                ],
            }
        t_900 = measured[(1600, 900)]["timeline"][COL_TIMELINE_NOTES]
        t_1080 = measured[(1920, 1080)]["timeline"][COL_TIMELINE_NOTES]
        f_900 = measured[(1600, 900)]["findings"][COL_FINDING_TASK]
        f_1080 = measured[(1920, 1080)]["findings"][COL_FINDING_TASK]
        self.assertGreaterEqual(t_1080, t_900)
        self.assertGreaterEqual(f_1080, f_900)
        self._close(dialog)
        print(
            "7B2 column widths: "
            f"1600x900 timeline={measured[(1600, 900)]['timeline']} "
            f"findings={measured[(1600, 900)]['findings']}; "
            f"1920x1080 timeline={measured[(1920, 1080)]['timeline']} "
            f"findings={measured[(1920, 1080)]['findings']}"
        )

    def test_03_refresh_keeps_profile(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self._show_course(dialog, 1600, 900)
        self._fill_course(dialog)
        before_t = [
            dialog.timeline_table.columnWidth(i)
            for i in range(dialog.timeline_table.columnCount())
        ]
        before_f = [
            dialog.findings_table.columnWidth(i)
            for i in range(dialog.findings_table.columnCount())
        ]
        dialog._refresh_timeline_table()
        dialog._refresh_findings_table()
        configure_table_columns(dialog.timeline_table, "state_supervision_timeline_items")
        configure_table_columns(dialog.findings_table, "state_supervision_findings")
        self._app.processEvents()
        self.assertEqual(
            dialog.timeline_table.horizontalHeader().sectionResizeMode(COL_TIMELINE_NOTES),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            dialog.findings_table.horizontalHeader().sectionResizeMode(COL_FINDING_TASK),
            QHeaderView.ResizeMode.Stretch,
        )
        for index, width in enumerate(before_t):
            self.assertAlmostEqual(dialog.timeline_table.columnWidth(index), width, delta=8)
        for index, width in enumerate(before_f):
            self.assertAlmostEqual(dialog.findings_table.columnWidth(index), width, delta=8)
        self._assert_fills_viewport(dialog.timeline_table)
        self._assert_fills_viewport(dialog.findings_table)
        self._close(dialog)

    def test_04_resize_and_section_change_are_not_dirty(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertIsInstance(dialog._editor, EditorDialogController)
        self.assertFalse(dialog._editor.is_dirty())
        self._show_course(dialog, 1600, 900)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.resize(1920, 1080)
        self._app.processEvents()
        dialog.timeline_table.horizontalHeader().resizeSection(COL_TIMELINE_TITLE, 300)
        dialog.findings_table.horizontalHeader().resizeSection(COL_FINDING_PERSON, 200)
        dialog.timeline_table.selectRow(0)
        dialog.findings_table.selectRow(0)
        self._app.processEvents()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self._close(dialog)

    def test_05_tooltips_and_row_open_stay(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self._show_course(dialog, 1600, 900)
        self._fill_course(dialog)
        notes = dialog.timeline_table.item(0, COL_TIMELINE_NOTES)
        self.assertIsNotNone(notes)
        tooltip = notes.toolTip().replace("\n", " ")
        self.assertIn("Podrobný zápis z průběhu kontroly skladu chemie", tooltip)
        self.assertIn("evidence odpadů", tooltip)
        self.assertEqual(
            dialog.timeline_table.textElideMode(), Qt.TextElideMode.ElideRight
        )
        self.assertEqual(
            dialog.findings_table.textElideMode(), Qt.TextElideMode.ElideRight
        )
        description = dialog.findings_table.item(0, COL_FINDING_DESCRIPTION)
        self.assertIsNotNone(description)
        self.assertEqual(description.toolTip(), "Chybí aktuální BL")
        self.assertEqual(dialog.findings_table.item(0, COL_FINDING_DUE).text(), EMPTY_VALUE)

        opened: list[str] = []

        def fake_timeline(*_args, **kwargs):
            opened.append("timeline")
            return None

        def fake_finding(*_args, **kwargs):
            opened.append("finding")
            return None

        with (
            patch(
                "moduly.statni_dozor.ui.state_supervision_timeline_item_dialog."
                "exec_timeline_item_dialog",
                side_effect=fake_timeline,
            ),
            patch(
                "moduly.statni_dozor.ui.state_supervision_finding_dialog."
                "exec_finding_dialog",
                side_effect=fake_finding,
            ),
        ):
            dialog.timeline_table.selectRow(0)
            dialog._edit_selected_timeline_item()
            dialog.findings_table.selectRow(0)
            dialog._edit_selected_finding()
        self.assertEqual(opened, ["timeline", "finding"])
        self._close(dialog)

    def test_06_save_does_not_write_on_column_resize(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}"
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self._show_course(dialog, 1600, 900)
        with (
            patch.object(state_supervision_service, "save_supervision_bundle") as bundle,
            patch.object(Session, "commit") as commit,
        ):
            dialog.timeline_table.horizontalHeader().resizeSection(COL_TIMELINE_PLACE, 240)
            dialog.resize(1920, 1080)
            self._app.processEvents()
            bundle.assert_not_called()
            commit.assert_not_called()
        self._close(dialog)


if __name__ == "__main__":
    unittest.main()
