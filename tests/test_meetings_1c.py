"""MEETINGS-1c: textová pole zápisu v modelu (UI nahrazeno body jednání)."""

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
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings1cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_has_discussion_tab(self) -> None:
        dialog = MeetingDialog()
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertEqual(titles, [TAB_MEETING, TAB_DISCUSSION])

    def test_save_and_reload_minutes_fields(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Schůzka se zápisem",
            proceedings="Proběhla kontrola úkolů.",
            conclusions="Úkoly budou dokončeny do pátku.",
            notes="Přítomni všichni.",
        )
        loaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.proceedings, "Proběhla kontrola úkolů.")
        self.assertEqual(loaded.conclusions, "Úkoly budou dokončeny do pátku.")
        self.assertEqual(loaded.notes, "Přítomni všichni.")

        dialog = MeetingDialog(meeting=loaded)
        data = dialog.get_data()
        self.assertEqual(data["proceedings"], loaded.proceedings)
        self.assertEqual(data["conclusions"], loaded.conclusions)
        self.assertEqual(data["notes"], loaded.notes)

    def test_empty_minutes_allowed(self) -> None:
        meeting = meeting_service.create_meeting(title="Bez zápisu")
        loaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.proceedings, "")
        self.assertEqual(loaded.conclusions, "")
        self.assertEqual(loaded.notes, "")

        data = MeetingDialog().get_data()
        self.assertEqual(data["proceedings"], "")
        self.assertEqual(data["conclusions"], "")
        self.assertEqual(data["notes"], "")

    def test_edit_existing_minutes(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Úprava zápisu",
            proceedings="Původní průběh",
            conclusions="Původní závěry",
            notes="Původní poznámka",
        )
        meeting_service.update_meeting(
            meeting.id,
            title="Úprava zápisu",
            proceedings="Upravený průběh",
            conclusions="Upravené závěry",
            notes="Upravená poznámka",
        )
        loaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.proceedings, "Upravený průběh")
        self.assertEqual(loaded.conclusions, "Upravené závěry")
        self.assertEqual(loaded.notes, "Upravená poznámka")

        dialog = MeetingDialog(meeting=loaded)
        dialog._legacy_proceedings = "Finální průběh"
        dialog._legacy_conclusions = "Finální závěry"
        dialog._legacy_notes = "Finální poznámka"
        data = dialog.get_data()
        meeting_service.update_meeting(meeting.id, **data)
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.proceedings, "Finální průběh")
        self.assertEqual(reloaded.conclusions, "Finální závěry")
        self.assertEqual(reloaded.notes, "Finální poznámka")


if __name__ == "__main__":
    unittest.main()
