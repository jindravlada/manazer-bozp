"""MEETINGS-2a: zavedení bodů jednání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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

    from moduly.schuzky.constants import TAB_DISCUSSION, TAB_MEETING
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings2aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_has_discussion_tab(self) -> None:
        dialog = MeetingDialog()
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertEqual(titles, [TAB_MEETING, TAB_DISCUSSION])
        self.assertFalse(hasattr(dialog, "proceedings_edit"))
        self.assertFalse(hasattr(dialog, "conclusions_edit"))
        self.assertFalse(hasattr(dialog, "notes_edit"))

    def test_add_edit_reorder_remove_and_reload(self) -> None:
        meeting = meeting_service.create_meeting(title="Schůzka s body")
        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)

        widget._items = [
            {"title": "Úvod", "display_order": 10},
            {"title": "Kontrola úkolů", "display_order": 20},
            {"title": "Různé", "display_order": 30},
        ]
        widget._refresh_table()
        self.assertEqual(
            [item["title"] for item in widget.get_items()],
            ["Úvod", "Kontrola úkolů", "Různé"],
        )

        # úprava
        widget._items[1]["title"] = "Kontrola opatření"
        widget._refresh_table()
        self.assertEqual(widget.get_items()[1]["title"], "Kontrola opatření")

        # změna pořadí – přesun druhého nahoru
        widget.table.selectRow(1)
        widget.move_item(-1)
        self.assertEqual(
            [item["title"] for item in widget.get_items()],
            ["Kontrola opatření", "Úvod", "Různé"],
        )

        # odebrání
        widget.table.selectRow(2)
        widget.remove_item()
        self.assertEqual(
            [item["title"] for item in widget.get_items()],
            ["Kontrola opatření", "Úvod"],
        )

        meeting_agenda_item_service.save_items(meeting.id, widget.get_items())
        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(
            [item.title for item in reloaded],
            ["Kontrola opatření", "Úvod"],
        )
        self.assertEqual([item.display_order for item in reloaded], [10, 20])

        dialog = MeetingDialog(meeting=meeting)
        self.assertEqual(
            [item["title"] for item in dialog.get_agenda_items()],
            ["Kontrola opatření", "Úvod"],
        )

    def test_legacy_minutes_preserved_on_save(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Legacy zápis",
            proceedings="Původní průběh",
            conclusions="Původní závěry",
            notes="Původní poznámky",
        )
        dialog = MeetingDialog(meeting=meeting)
        data = dialog.get_data()
        self.assertEqual(data["proceedings"], "Původní průběh")
        self.assertEqual(data["conclusions"], "Původní závěry")
        self.assertEqual(data["notes"], "Původní poznámky")

        meeting_service.update_meeting(meeting.id, **data)
        meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
        loaded = meeting_service.get_by_id(meeting.id)
        assert loaded is not None
        self.assertEqual(loaded.proceedings, "Původní průběh")
        self.assertEqual(loaded.conclusions, "Původní závěry")
        self.assertEqual(loaded.notes, "Původní poznámky")


if __name__ == "__main__":
    unittest.main()
