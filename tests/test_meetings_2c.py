"""MEETINGS-2c: integrovaný editor bodů jednání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

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

    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings2cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_switch_items_flushes_working_copy(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [
            {
                "title": "Bod A",
                "moje_sdeleni": "A1",
                "prubeh_jednani": "A2",
                "zaver": "A3",
                "display_order": 10,
            },
            {
                "title": "Bod B",
                "moje_sdeleni": "B1",
                "prubeh_jednani": "B2",
                "zaver": "B3",
                "display_order": 20,
            },
        ]
        widget._refresh_table(select_row=0)
        self.assertEqual(widget.title_edit.text(), "Bod A")

        widget.title_edit.setText("Bod A upraven")
        widget.zaver_edit.setPlainText("Nový závěr A")
        widget.table.selectRow(1)

        self.assertEqual(widget.title_edit.text(), "Bod B")
        self.assertEqual(widget._items[0]["title"], "Bod A upraven")
        self.assertEqual(widget._items[0]["zaver"], "Nový závěr A")

        widget.table.selectRow(0)
        self.assertEqual(widget.title_edit.text(), "Bod A upraven")
        self.assertEqual(widget.zaver_edit.toPlainText(), "Nový závěr A")

    def test_edit_without_dialog(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget.add_item()
        self.assertTrue(widget.editor_panel.isEnabled())
        widget.title_edit.setText("Téma bez dialogu")
        widget.moje_sdeleni_edit.setPlainText("Sdělení")
        items = widget.get_items()
        self.assertEqual(items[0]["title"], "Téma bez dialogu")
        self.assertEqual(items[0]["moje_sdeleni"], "Sdělení")

        # samostatný dialog editoru už neexistuje
        with self.assertRaises(ImportError):
            importlib.import_module("moduly.schuzky.ui.meeting_agenda_item_dialog")

    def test_add_selects_new_item(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget.add_item()
        widget.title_edit.setText("První")
        widget.add_item()
        self.assertEqual(widget._selected_index(), 1)
        self.assertEqual(widget.title_edit.text(), "")
        self.assertEqual(widget.get_items()[0]["title"], "První")

    def test_remove_selects_nearest(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [
            _item("Jedna"),
            _item("Dva"),
            _item("Tři"),
        ]
        widget._refresh_table(select_row=1)
        widget.remove_item()
        self.assertEqual([item["title"] for item in widget.get_items()], ["Jedna", "Tři"])
        self.assertEqual(widget._selected_index(), 1)
        self.assertEqual(widget.title_edit.text(), "Tři")

        widget.remove_item()
        widget.remove_item()
        self.assertEqual(widget.get_items(), [])
        self.assertIsNone(widget._selected_index())
        self.assertFalse(widget.editor_panel.isEnabled())

    def test_data_preserved_through_meeting_dialog(self) -> None:
        meeting = meeting_service.create_meeting(title="Zachování")
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Téma",
                    "moje_sdeleni": "Sdělení",
                    "prubeh_jednani": "Průběh",
                    "zaver": "Závěr",
                }
            ],
        )
        dialog = MeetingDialog(meeting=meeting)
        self.assertIsInstance(dialog, QDialog)
        widget = dialog.agenda_items_widget
        self.assertEqual(widget.title_edit.text(), "Téma")
        widget.prubeh_jednani_edit.setPlainText("Upravený průběh")
        items = dialog.get_agenda_items()
        self.assertEqual(items[0]["prubeh_jednani"], "Upravený průběh")
        self.assertEqual(items[0]["moje_sdeleni"], "Sdělení")
        self.assertEqual(items[0]["zaver"], "Závěr")


def _item(title: str) -> dict:
    return {
        "title": title,
        "moje_sdeleni": "",
        "prubeh_jednani": "",
        "zaver": "",
        "display_order": 10,
    }


if __name__ == "__main__":
    unittest.main()
