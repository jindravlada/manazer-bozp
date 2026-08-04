"""MEETINGS-UX-1: zpřehlednění seznamu bodů jednání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QListWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.schuzky.constants import (
        AGENDA_ITEM_NONE_SELECTED,
        AGENDA_ITEM_STATUS_DISCUSSED,
        AGENDA_ITEM_STATUS_ICONS,
        AGENDA_ITEM_STATUS_POSTPONED,
        AGENDA_ITEM_STATUS_READY,
        AGENDA_ITEMS_COUNT_TEMPLATE,
    )
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget


def _item(title: str, *, status: str = AGENDA_ITEM_STATUS_READY) -> dict:
    return {
        "title": title,
        "status": status,
        "moje_sdeleni": "",
        "prubeh_jednani": "",
        "zaver": "",
        "display_order": 10,
    }


class MeetingsUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_compact_list_labels(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [
            _item("Revize elektro", status=AGENDA_ITEM_STATUS_DISCUSSED),
            _item("Školení zaměstnanců", status=AGENDA_ITEM_STATUS_READY),
            _item("Rekonstrukce skladu", status=AGENDA_ITEM_STATUS_POSTPONED),
        ]
        widget._refresh_table(select_row=0)
        self.assertIsInstance(widget.table, QListWidget)
        self.assertEqual(
            widget.table.item(0).text(),
            f"{AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_DISCUSSED]} 1. Revize elektro",
        )
        self.assertEqual(
            widget.table.item(1).text(),
            f"{AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_READY]} 2. Školení zaměstnanců",
        )
        self.assertEqual(
            widget.table.item(2).text(),
            f"{AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_POSTPONED]} 3. Rekonstrukce skladu",
        )

    def test_active_item_highlight(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [_item("A"), _item("B")]
        widget._refresh_table(select_row=1)
        self.assertEqual(widget.table.currentRow(), 1)
        self.assertTrue(widget.table.item(1).isSelected())
        self.assertIn("item:selected", widget.table.styleSheet())
        self.assertIn("border-left", widget.table.styleSheet())

    def test_empty_state_hides_editor_fields(self) -> None:
        widget = MeetingAgendaItemsWidget()
        self.assertEqual(widget.count_label.text(), AGENDA_ITEMS_COUNT_TEMPLATE.format(count=0))
        self.assertIsNot(widget.editor_stack.currentWidget(), widget.editor_panel)
        self.assertEqual(widget.none_selected_label.text(), AGENDA_ITEM_NONE_SELECTED)
        self.assertFalse(widget.title_edit.isVisibleTo(widget.editor_stack))

    def test_item_count_label(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget.add_item()
        widget.add_item()
        self.assertEqual(widget.count_label.text(), AGENDA_ITEMS_COUNT_TEMPLATE.format(count=2))
        widget.remove_item()
        self.assertEqual(widget.count_label.text(), AGENDA_ITEMS_COUNT_TEMPLATE.format(count=1))

    def test_select_after_add_and_focus_title(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget.add_item()
        widget.title_edit.setText("První")
        with (
            patch.object(widget.title_edit, "setFocus") as set_focus,
            patch.object(widget.title_edit, "selectAll") as select_all,
        ):
            widget.add_item()
        self.assertEqual(widget._selected_index(), 1)
        self.assertEqual(widget.table.currentRow(), 1)
        self.assertIs(widget.editor_stack.currentWidget(), widget.editor_panel)
        set_focus.assert_called_once()
        select_all.assert_called_once()
        self.assertEqual(widget.get_items()[0]["title"], "První")

    def test_select_nearest_after_remove(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [_item("Jedna"), _item("Dva"), _item("Tři")]
        widget._refresh_table(select_row=1)
        widget.remove_item()
        self.assertEqual(widget._selected_index(), 1)
        self.assertEqual(widget.title_edit.text(), "Tři")
        self.assertIn("2. Tři", widget.table.item(1).text())

        widget.remove_item()
        widget.remove_item()
        self.assertIsNone(widget._selected_index())
        self.assertEqual(widget.count_label.text(), AGENDA_ITEMS_COUNT_TEMPLATE.format(count=0))
        self.assertEqual(widget.none_selected_label.text(), AGENDA_ITEM_NONE_SELECTED)
        self.assertIsNot(widget.editor_stack.currentWidget(), widget.editor_panel)


if __name__ == "__main__":
    unittest.main()
