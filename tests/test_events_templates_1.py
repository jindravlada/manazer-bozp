"""EVENTS-TEMPLATES-1: založení události ze šablony (základní evidence)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import (
        ACTION_NEW_FROM_TEMPLATE,
        DEFAULT_MEETING_STATUS,
        STATUS_PLANNED,
        TEMPLATE_BTN_USE,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_template_actions import create_meeting_from_template
    from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage


class EventsTemplates1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_create_template(self) -> None:
        organizer = person_service.create_person(first_name="Org", last_name="Anizátor")
        participant = person_service.create_person(first_name="Účast", last_name="Ník")
        template = meeting_template_service.create_template(
            name="Kontrola skladu",
            event_type="Kontrolní pochůzka",
            location="Sklad A",
            priority="Vysoká",
            organizer_person_id=organizer.id,
            participant_ids=[participant.id],
            external_participants=[
                {
                    "full_name": "Host Externí",
                    "organization": "Dodavatel",
                    "function": "",
                    "contact": "",
                    "note": "",
                }
            ],
            agenda_items=[
                {
                    "title": "Vstup",
                    "moje_sdeleni": "Zkontrolovat OOPP",
                    "status": "Připraveno",
                    "prubeh_jednani": "toto se neukládá",
                    "zaver": "toto se neukládá",
                }
            ],
        )
        self.assertEqual(template.name, "Kontrola skladu")
        self.assertEqual(template.title, "Kontrola skladu")
        self.assertEqual(template.event_type, "Kontrolní pochůzka")
        self.assertEqual(template.location, "Sklad A")
        self.assertEqual(template.priority, "Vysoká")
        self.assertEqual(template.organizer_person_id, organizer.id)
        self.assertEqual(
            meeting_template_service.parse_participant_ids(template),
            [participant.id],
        )
        externals = meeting_template_service.parse_external_participants(template)
        self.assertEqual(externals[0]["full_name"], "Host Externí")
        items = meeting_template_service.parse_agenda_items(template)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Vstup")
        self.assertEqual(items[0]["moje_sdeleni"], "Zkontrolovat OOPP")
        self.assertEqual(items[0]["prubeh_jednani"], "")
        self.assertEqual(items[0]["zaver"], "")

    def test_new_meeting_from_template_prefill(self) -> None:
        organizer = person_service.create_person(first_name="Šéf", last_name="Šablony")
        template = meeting_template_service.create_template(
            name="Šablona A",
            event_type="Porada",
            location="Zasedačka",
            priority="Normální",
            organizer_person_id=organizer.id,
            participant_ids=[],
            external_participants=[],
            agenda_items=[
                {"title": "Bod 1", "moje_sdeleni": "Text", "status": "Odloženo"},
                {"title": "Bod 2", "moje_sdeleni": "", "status": "Připraveno"},
            ],
        )

        dialog = MeetingDialog(template=template)
        data = dialog.get_data()
        self.assertEqual(data["title"], "Šablona A")
        self.assertEqual(data["event_type"], "Porada")
        self.assertEqual(data["location"], "Zasedačka")
        self.assertEqual(data["priority"], "Normální")
        self.assertEqual(data["organizer_person_id"], organizer.id)
        self.assertIsNone(data["starts_at"])
        self.assertIsNone(data["ends_at"])
        self.assertEqual(data["status"], DEFAULT_MEETING_STATUS)
        self.assertEqual(data["proceedings"], "")
        self.assertEqual(data["conclusions"], "")

        items = dialog.get_agenda_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Bod 1")
        self.assertEqual(items[0]["moje_sdeleni"], "Text")
        self.assertEqual(items[0]["status"], "Odloženo")
        self.assertEqual(items[0].get("prubeh_jednani", ""), "")
        self.assertNotIn("id", items[0])

        meeting = meeting_service.create_meeting(**data)
        meeting_agenda_item_service.save_items(meeting.id, items)
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.starts_at)
        self.assertEqual(reloaded.status, STATUS_PLANNED)
        saved_items = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(saved_items), 2)
        self.assertEqual(saved_items[0].title, "Bod 1")
        self.assertEqual(saved_items[0].prubeh_jednani or "", "")

    def test_pick_dialog_shows_template_meta(self) -> None:
        meeting_template_service.create_template(
            name="Meta šablona",
            event_type="Školení",
            title="Školení",
            agenda_items=[
                {"title": "A", "moje_sdeleni": "", "status": "Připraveno"},
                {"title": "B", "moje_sdeleni": "", "status": "Připraveno"},
            ],
        )
        dialog = MeetingTemplatePickDialog()
        self.assertEqual(dialog.windowTitle(), "Šablona události")
        self.assertEqual(dialog.use_btn.text(), TEMPLATE_BTN_USE)
        self.assertGreaterEqual(dialog.table.rowCount(), 1)
        found = False
        for row in range(dialog.table.rowCount()):
            if dialog.table.item(row, 0).text() == "Meta šablona":
                self.assertEqual(dialog.table.item(row, 1).text(), "Školení")
                self.assertEqual(dialog.table.item(row, 2).text(), "2")
                found = True
                break
        self.assertTrue(found)

    def test_pages_have_new_from_template_action(self) -> None:
        page = SchuzkyPage()
        self.assertEqual(page.new_from_template_btn.text(), ACTION_NEW_FROM_TEMPLATE)
        agenda = AgendaPage()
        self.assertEqual(agenda.new_from_template_btn.text(), ACTION_NEW_FROM_TEMPLATE)

    def test_create_from_template_action_flow(self) -> None:
        template = meeting_template_service.create_template(
            name="Flow",
            event_type="Schůzka",
            location="Online",
        )
        with patch(
            "moduly.schuzky.ui.meeting_template_actions.MeetingTemplatePickDialog"
        ) as pick_cls, patch(
            "moduly.schuzky.ui.meeting_template_actions.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.schuzky.ui.meeting_template_actions.MeetingDialog"
        ) as dialog_cls:
            pick = pick_cls.return_value
            pick.exec.return_value = pick.DialogCode.Accepted
            pick.selected_template_id.return_value = template.id
            dialog = dialog_cls.return_value
            dialog.get_data.return_value = meeting_template_service.meeting_data_from_template(
                template
            )
            dialog.get_agenda_items.return_value = []
            self.assertTrue(create_meeting_from_template(None))

        created = [
            m for m in meeting_service.get_all() if (m.title or "") == "Flow"
        ]
        self.assertTrue(created)
        self.assertIsNone(created[0].starts_at)
        self.assertEqual(created[0].location, "Online")
        self.assertEqual(created[0].status, STATUS_PLANNED)

    def test_no_save_as_template_button(self) -> None:
        dialog = MeetingDialog()
        texts = [btn.text() for btn in dialog.findChildren(QPushButton)]
        self.assertNotIn("Uložit jako šablonu...", texts)


if __name__ == "__main__":
    unittest.main()
