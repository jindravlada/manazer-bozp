"""AG-03b: šablona z existující události nemění původní záznam."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.schuzky.constants import (
        AGENDA_ITEM_STATUS_DISCUSSED,
        AGENDA_ITEM_STATUS_READY,
        DEFAULT_MEETING_STATUS,
        STATUS_CLOSED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_item_task_service import (
        meeting_item_task_service,
    )
    from moduly.schuzky.sluzby.meeting_participant_ref import (
        MEETING_SOURCE_PERSON,
        MEETING_SOURCE_THP_WORKER,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service


class EventSaveAsTemplateAg03bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _meeting(self, *, title: str, organizer_ref: dict, participant_refs: list[dict]):
        meeting = meeting_service.create_meeting(
            title=title,
            event_type="Porada",
            starts_at=datetime(2026, 10, 5, 9, 30),
            ends_at=datetime(2026, 10, 5, 11, 0),
            remind_from=date(2026, 10, 1),
            location="Zasedačka",
            organizer_ref=organizer_ref,
            participant_refs=participant_refs,
            external_participants=[
                {
                    "full_name": "Host Externí",
                    "organization": "Dodavatel",
                    "function": "Technik",
                    "contact": "",
                    "note": "",
                }
            ],
            agenda="Program, který do šablony nepatří",
            status=STATUS_CLOSED,
            priority="Vysoká",
            proceedings="průběh události",
            conclusions="závěr události",
            notes="poznámka z průběhu",
        )
        saved = meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Kontrola OOPP",
                    "moje_sdeleni": "Přinést seznam",
                    "status": AGENDA_ITEM_STATUS_DISCUSSED,
                    "prubeh_jednani": "probráno",
                    "zaver": "bez závad",
                }
            ],
        )
        task = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=saved[0].id,
            title="Navázaný úkol",
        )
        return meeting, saved[0], task

    def _snapshot(self, meeting_id: int, item_id: int):
        meeting = meeting_service.get_by_id(meeting_id)
        assert meeting is not None
        items = meeting_agenda_item_service.get_for_meeting(meeting_id)
        tasks = meeting_item_task_service.list_for_item(meeting_id, item_id)
        return {
            "title": meeting.title,
            "event_type": meeting.event_type,
            "starts_at": meeting.starts_at,
            "ends_at": meeting.ends_at,
            "remind_from": meeting.remind_from,
            "location": meeting.location,
            "status": meeting.status,
            "priority": meeting.priority,
            "agenda": meeting.agenda,
            "proceedings": meeting.proceedings,
            "conclusions": meeting.conclusions,
            "notes": meeting.notes,
            "organizer": meeting_service.organizer_ref(meeting),
            "organizer_person_id": meeting.organizer_person_id,
            "participants": meeting_service.parse_participant_refs(meeting),
            "externals": meeting_service.parse_external_participants(meeting),
            "items": [
                (
                    item.id,
                    item.title,
                    item.moje_sdeleni,
                    item.status,
                    item.prubeh_jednani,
                    item.zaver,
                )
                for item in items
            ],
            "task_ids": [task.id for task in tasks],
        }

    def _save(self, dialog: MeetingDialog, *, rename: str | None = None, accept: bool = True):
        def _exec(template_dialog):
            if rename is not None:
                template_dialog.name_edit.setText(rename)
            self._opened = template_dialog.get_data()
            return accept

        with patch(
            "moduly.schuzky.ui.meeting_dialog.exec_maximized",
            side_effect=_exec,
        ):
            dialog.save_as_template_btn.click()

    def test_person_organizer_template_and_new_event(self) -> None:
        organizer = person_service.create_person(first_name="Eva", last_name="Organizátor")
        guest = person_service.create_person(first_name="Jan", last_name="Účastník")
        person_ref = {"source_type": MEETING_SOURCE_PERSON, "source_id": organizer.id}
        guest_ref = {"source_type": MEETING_SOURCE_PERSON, "source_id": guest.id}
        meeting, item, task = self._meeting(
            title="Porada skladu",
            organizer_ref=person_ref,
            participant_refs=[guest_ref],
        )
        before = self._snapshot(meeting.id, item.id)
        before_count = len(meeting_template_service.get_all())

        dialog = MeetingDialog(meeting=meeting)
        draft = dialog._template_draft()
        self.assertEqual(draft["name"], "Porada skladu")
        self.assertEqual(draft["event_type"], "Porada")
        self.assertEqual(draft["priority"], "Vysoká")
        self.assertEqual(draft["location"], "Zasedačka")
        self.assertEqual(draft["organizer_ref"], person_ref)
        self.assertEqual(draft["participant_refs"], [guest_ref])
        self.assertEqual(draft["external_participants"][0]["full_name"], "Host Externí")
        self.assertNotIn("starts_at", draft)
        self.assertNotIn("remind_from", draft)
        self.assertNotIn("status", draft)
        self.assertNotIn("agenda", draft)
        self.assertEqual(len(draft["agenda_items"]), 1)
        self.assertEqual(draft["agenda_items"][0]["title"], "Kontrola OOPP")
        self.assertEqual(draft["agenda_items"][0]["moje_sdeleni"], "Přinést seznam")
        self.assertEqual(draft["agenda_items"][0]["status"], AGENDA_ITEM_STATUS_READY)
        self.assertNotIn("id", draft["agenda_items"][0])
        self.assertNotIn("prubeh_jednani", draft["agenda_items"][0])
        self.assertNotIn("zaver", draft["agenda_items"][0])

        self._save(dialog, rename="Šablona skladu")
        dialog._editor.force_close()

        self.assertEqual(self._snapshot(meeting.id, item.id), before)
        self.assertEqual(len(meeting_template_service.get_all()), before_count + 1)
        stored = next(
            row
            for row in meeting_template_service.get_all()
            if row.name == "Šablona skladu"
        )
        self.assertEqual(meeting_template_service.organizer_ref(stored), person_ref)
        self.assertEqual(stored.organizer_person_id, organizer.id)
        self.assertEqual(
            meeting_template_service.parse_participant_refs(stored),
            [guest_ref],
        )
        externals = meeting_template_service.parse_external_participants(stored)
        self.assertEqual(externals[0]["full_name"], "Host Externí")
        items = meeting_template_service.parse_agenda_items(stored)
        self.assertEqual(items[0]["title"], "Kontrola OOPP")
        self.assertEqual(items[0]["moje_sdeleni"], "Přinést seznam")
        self.assertEqual(items[0]["status"], AGENDA_ITEM_STATUS_READY)
        self.assertEqual(items[0]["prubeh_jednani"], "")
        self.assertEqual(items[0]["zaver"], "")
        self.assertEqual(
            [row.id for row in meeting_item_task_service.list_for_item(meeting.id, item.id)],
            [task.id],
        )
        self.assertEqual(task_service.get_task_by_id(task.id).source_record_id, meeting.id)

        created = MeetingDialog(template=stored)
        data = created.get_data()
        self.assertEqual(data["title"], "Šablona skladu")
        self.assertEqual(data["organizer_ref"], person_ref)
        self.assertEqual(data["participant_refs"], [guest_ref])
        self.assertEqual(data["external_participants"][0]["full_name"], "Host Externí")
        self.assertIsNone(data["starts_at"])
        self.assertIsNone(data["ends_at"])
        self.assertIsNone(data["remind_from"])
        self.assertEqual(data["agenda"], "")
        self.assertEqual(data["status"], DEFAULT_MEETING_STATUS)
        self.assertEqual(data["proceedings"], "")
        self.assertEqual(data["conclusions"], "")
        new_items = created.get_agenda_items()
        self.assertEqual(new_items[0]["status"], AGENDA_ITEM_STATUS_READY)
        self.assertNotIn("id", new_items[0])
        self.assertEqual(new_items[0].get("prubeh_jednani", ""), "")
        fresh = meeting_service.create_meeting(**data)
        meeting_agenda_item_service.save_items(fresh.id, new_items)
        reloaded = meeting_service.get_by_id(fresh.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, STATUS_PLANNED)
        self.assertIsNone(reloaded.starts_at)
        self.assertEqual(reloaded.organizer_person_id, organizer.id)
        self.assertEqual(meeting_service.organizer_ref(reloaded), person_ref)
        created._editor.force_close()

    def test_thp_organizer_keeps_ref_without_person_id(self) -> None:
        worker = settings_service.save_worker(
            first_name="Technik",
            last_name="Šablona",
            position="BOZP",
        )
        thp_ref = {"source_type": MEETING_SOURCE_THP_WORKER, "source_id": worker.id}
        meeting, item, _task = self._meeting(
            title="Pochůzka THP",
            organizer_ref=thp_ref,
            participant_refs=[],
        )
        before = self._snapshot(meeting.id, item.id)
        dialog = MeetingDialog(meeting=meeting)
        self.assertEqual(dialog._template_draft()["organizer_ref"], thp_ref)
        self._save(dialog)
        dialog._editor.force_close()

        self.assertEqual(self._snapshot(meeting.id, item.id), before)
        stored = next(
            row
            for row in meeting_template_service.get_all()
            if row.name == "Pochůzka THP"
        )
        self.assertEqual(meeting_template_service.organizer_ref(stored), thp_ref)
        self.assertIsNone(stored.organizer_person_id)
        self.assertEqual(stored.organizer_source_type, MEETING_SOURCE_THP_WORKER)
        self.assertEqual(stored.organizer_source_id, worker.id)

        created = MeetingDialog(template=stored)
        meeting_from_template = meeting_service.create_meeting(**created.get_data())
        reloaded = meeting_service.get_by_id(meeting_from_template.id)
        assert reloaded is not None
        self.assertEqual(meeting_service.organizer_ref(reloaded), thp_ref)
        self.assertIsNone(reloaded.organizer_person_id)
        self.assertEqual(reloaded.organizer_source_type, MEETING_SOURCE_THP_WORKER)
        created._editor.force_close()

    def test_cancel_creates_nothing(self) -> None:
        meeting, item, _task = self._meeting(
            title="Zrušená šablona",
            organizer_ref=None,
            participant_refs=[],
        )
        before = self._snapshot(meeting.id, item.id)
        names = {row.name for row in meeting_template_service.get_all()}
        dialog = MeetingDialog(meeting=meeting)
        self._save(dialog, accept=False)
        dialog._editor.force_close()
        self.assertEqual({row.name for row in meeting_template_service.get_all()}, names)
        self.assertEqual(self._snapshot(meeting.id, item.id), before)

    def test_unsaved_form_prefills_template_without_writing_event(self) -> None:
        meeting, item, _task = self._meeting(
            title="Původní název",
            organizer_ref=None,
            participant_refs=[],
        )
        before = self._snapshot(meeting.id, item.id)
        dialog = MeetingDialog(meeting=meeting)
        dialog.title_edit.setText("Jen ve formuláři")
        dialog.location_edit.set_location_text("Jiné místo")
        dialog.agenda_edit.setPlainText("Rozepsaná poznámka")
        dialog.agenda_items_widget.selectRow(0)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Upravené sdělení")
        self.assertTrue(dialog._editor.is_dirty())

        self._save(dialog)
        self.assertEqual(self._opened["name"], "Jen ve formuláři")
        self.assertEqual(self._opened["location"], "Jiné místo")
        self.assertEqual(self._opened["agenda_items"][0]["moje_sdeleni"], "Upravené sdělení")
        self.assertEqual(self._opened["agenda_items"][0]["status"], AGENDA_ITEM_STATUS_READY)
        self.assertNotIn("agenda", self._opened)

        self.assertEqual(self._snapshot(meeting.id, item.id), before)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertFalse(dialog.was_saved)
        dialog._editor.force_close()


if __name__ == "__main__":
    unittest.main()
