"""MEETINGS-1a: základní evidence schůzek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton

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

    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import (
        DEFAULT_MEETING_STATUS,
        END_BEFORE_START_MESSAGE,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import (
        MeetingValidationError,
        meeting_service,
    )
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage


class Meetings1aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.organizer = person_service.create_person(
            first_name="Jan",
            last_name="Organizátor",
        )
        self.participant_a = person_service.create_person(
            first_name="Anna",
            last_name="Účastnice",
        )
        self.participant_b = person_service.create_person(
            first_name="Petr",
            last_name="Účastník",
        )

    def test_create_and_reload_meeting(self) -> None:
        starts = datetime(2026, 8, 10, 9, 0, 0)
        ends = datetime(2026, 8, 10, 10, 30, 0)
        meeting = meeting_service.create_meeting(
            title="Koordinační schůzka BOZP",
            starts_at=starts,
            ends_at=ends,
            location="Zasedací místnost A",
            organizer_person_id=self.organizer.id,
            participant_ids=[self.participant_a.id, self.participant_b.id],
            agenda="Kontrola plnění opatření",
            status=STATUS_PLANNED,
        )

        loaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.title, "Koordinační schůzka BOZP")
        self.assertEqual(loaded.starts_at, starts)
        self.assertEqual(loaded.ends_at, ends)
        self.assertEqual(loaded.location, "Zasedací místnost A")
        self.assertEqual(loaded.organizer_person_id, self.organizer.id)
        self.assertIn("Organizátor", loaded.organizer_name)
        self.assertEqual(
            meeting_service.parse_participant_ids(loaded),
            [self.participant_a.id, self.participant_b.id],
        )
        self.assertIn("Účastnice", loaded.participant_names)
        self.assertIn("Účastník", loaded.participant_names)
        self.assertEqual(loaded.agenda, "Kontrola plnění opatření")
        self.assertEqual(loaded.status, DEFAULT_MEETING_STATUS)

    def test_save_incomplete_meeting(self) -> None:
        meeting = meeting_service.create_meeting(title="", status=STATUS_PLANNED)
        loaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.title, "")
        self.assertIsNone(loaded.starts_at)
        self.assertIsNone(loaded.ends_at)
        self.assertIsNone(loaded.organizer_person_id)
        self.assertEqual(meeting_service.parse_participant_ids(loaded), [])

    def test_end_before_start_rejected(self) -> None:
        starts = datetime(2026, 8, 10, 12, 0, 0)
        ends = starts - timedelta(minutes=30)
        with self.assertRaises(MeetingValidationError) as ctx:
            meeting_service.create_meeting(
                title="Neplatná",
                starts_at=starts,
                ends_at=ends,
            )
        self.assertEqual(str(ctx.exception), END_BEFORE_START_MESSAGE)

    def test_dialog_end_before_start_data_invalid(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Test")
        starts = datetime(2026, 8, 10, 12, 0, 0)
        dialog.starts_at_edit.set_datetime(starts)
        dialog.ends_at_edit.set_datetime(starts - timedelta(hours=1))
        data = dialog.get_data()
        with self.assertRaises(MeetingValidationError) as ctx:
            meeting_service.validate_times(data["starts_at"], data["ends_at"])
        self.assertEqual(str(ctx.exception), END_BEFORE_START_MESSAGE)
        dialog.close()

    def test_organizer_and_multi_participants_in_dialog(self) -> None:
        from core.widgets.multi_person_selector import MultiPersonSelector
        from core.widgets.person_selector import PersonSelector

        organizer = PersonSelector(include_empty=True, allow_add_new=False)
        organizer.reload()
        organizer.set_person_id(self.organizer.id)
        # currentData je spolehlivější než textová shoda (duplicitní jména napříč testy).
        self.assertEqual(organizer.currentData(), self.organizer.id)

        participants = MultiPersonSelector()
        participants.set_person_ids([self.participant_a.id, self.participant_b.id])
        self.assertEqual(
            participants.selected_person_ids(),
            [self.participant_a.id, self.participant_b.id],
        )

        meeting = meeting_service.create_meeting(
            title="Schůzka s účastníky",
            organizer_person_id=self.organizer.id,
            participant_ids=[self.participant_a.id, self.participant_b.id],
        )
        loaded = meeting_service.get_by_id(meeting.id)
        assert loaded is not None
        self.assertEqual(loaded.organizer_person_id, self.organizer.id)
        self.assertEqual(
            meeting_service.parse_participant_ids(loaded),
            [self.participant_a.id, self.participant_b.id],
        )

    def test_list_page_shows_meeting_and_double_click_opens(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Schůzka v přehledu",
            organizer_person_id=self.organizer.id,
            location="Halová",
        )
        page = SchuzkyPage()
        page.refresh()

        found_row = None
        for row in range(page.table.rowCount()):
            if page.table.item(row, 3).text() == "Schůzka v přehledu":
                found_row = row
                break
        self.assertIsNotNone(found_row)
        assert found_row is not None
        self.assertEqual(page.table.item(found_row, 0).text(), str(meeting.id))
        self.assertEqual(page.table.item(found_row, 2).text(), "Schůzka")
        self.assertEqual(page.table.item(found_row, 4).text(), "Halová")

        page.table.selectRow(found_row)
        opened: list[int] = []
        original = page.open_meeting

        def _capture(meeting_id: int) -> None:
            opened.append(meeting_id)

        page.open_meeting = _capture  # type: ignore[method-assign]
        page.open_selected_meeting()
        self.assertEqual(opened, [meeting.id])
        page.open_meeting = original  # type: ignore[method-assign]

    def test_dashboard_has_agenda_button(self) -> None:
        opened: list[str] = []

        def _open() -> None:
            opened.append("agenda")

        widget = UpcomingTasksWidget(open_agenda_callback=_open)
        buttons = [
            btn.text()
            for btn in widget.findChildren(QPushButton)
            if btn.text() in ("Agenda", "Úkoly", "Události")
        ]
        self.assertEqual(buttons, ["Agenda"])
        widget.agenda_button.click()
        self.assertEqual(opened, ["agenda"])

    def test_module_registered(self) -> None:
        from core.modules.module_manager import ModuleManager
        from moduly.schuzky.constants import MODULE_NAME

        keys = [module.key for module in ModuleManager().get_modules()]
        self.assertIn("schuzky", keys)
        names = [module.name for module in ModuleManager().get_modules()]
        self.assertIn(MODULE_NAME, names)
        self.assertEqual(MODULE_NAME, "Události")
        page = SchuzkyPage()
        self.assertEqual(page.new_btn.text(), "Nová událost")


if __name__ == "__main__":
    unittest.main()
