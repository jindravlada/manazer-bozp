"""MEETINGS-2b: karta bodu jednání (pole v modelu a integrovaném editoru)."""

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

    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings2bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_save_reload_and_edit_all_fields(self) -> None:
        meeting = meeting_service.create_meeting(title="Karta bodu")
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Bezpečnost práce",
                    "moje_sdeleni": "Připravit shrnutí kontrol.",
                    "prubeh_jednani": "Diskuze o kontrolách na provozu.",
                    "zaver": "Doplnit opatření do registru.",
                }
            ],
        )

        loaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(loaded), 1)
        item = loaded[0]
        self.assertEqual(item.title, "Bezpečnost práce")
        self.assertEqual(item.moje_sdeleni, "Připravit shrnutí kontrol.")
        self.assertEqual(item.prubeh_jednani, "Diskuze o kontrolách na provozu.")
        self.assertEqual(item.zaver, "Doplnit opatření do registru.")

        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)
        self.assertEqual(widget.title_edit.text(), "Bezpečnost práce")
        self.assertEqual(
            widget.moje_sdeleni_edit.toPlainText(),
            "Připravit shrnutí kontrol.",
        )
        widget.title_edit.setText("Aktualizovaná bezpečnost")
        widget.moje_sdeleni_edit.setPlainText("Nové sdělení")
        widget.prubeh_jednani_edit.setPlainText("Nový průběh")
        widget.zaver_edit.setPlainText("Nový závěr")
        meeting_agenda_item_service.save_items(meeting.id, widget.get_items())

        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0].title, "Aktualizovaná bezpečnost")
        self.assertEqual(reloaded[0].moje_sdeleni, "Nové sdělení")
        self.assertEqual(reloaded[0].prubeh_jednani, "Nový průběh")
        self.assertEqual(reloaded[0].zaver, "Nový závěr")

        meeting_dialog = MeetingDialog(meeting=meeting)
        items = meeting_dialog.get_agenda_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Aktualizovaná bezpečnost")
        self.assertEqual(items[0]["moje_sdeleni"], "Nové sdělení")
        self.assertEqual(
            [
                meeting_dialog.agenda_items_widget.table.horizontalHeaderItem(i).text()
                for i in range(meeting_dialog.agenda_items_widget.table.columnCount())
            ],
            ["Pořadí", "Název tématu"],
        )

    def test_empty_fields_allowed(self) -> None:
        meeting = meeting_service.create_meeting(title="Prázdný bod")
        meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "", "moje_sdeleni": "", "prubeh_jednani": "", "zaver": ""}],
        )
        loaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "")
        self.assertEqual(loaded[0].moje_sdeleni, "")
        self.assertEqual(loaded[0].prubeh_jednani, "")
        self.assertEqual(loaded[0].zaver, "")

        widget = MeetingAgendaItemsWidget()
        widget.add_item()
        data = widget.get_items()[0]
        self.assertEqual(data["title"], "")
        self.assertEqual(data["moje_sdeleni"], "")
        self.assertEqual(data["prubeh_jednani"], "")
        self.assertEqual(data["zaver"], "")


if __name__ == "__main__":
    unittest.main()
