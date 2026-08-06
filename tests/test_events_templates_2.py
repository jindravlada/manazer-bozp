"""EVENTS-TEMPLATES-2: samostatná správa šablon událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea

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

    from core.modules.module_manager import ModuleManager
    from core.windows.main_window import MainWindow
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.sablony_udalosti.constants import MODULE_KEY, MODULE_NAME
    from moduly.schuzky.constants import (
        ACTION_NEW_FROM_TEMPLATE,
        DEFAULT_MEETING_STATUS,
        STATUS_PLANNED,
        TEMPLATE_ACTION_DELETE,
        TEMPLATE_ACTION_NEW,
        TEMPLATE_DIALOG_TITLE,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import (
        MeetingTemplateValidationError,
        meeting_template_service,
    )
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_template_dialog import MeetingTemplateDialog
    from moduly.schuzky.ui.meeting_templates_page import MeetingTemplatesPage


def _sidebar_texts(window: MainWindow) -> list[str]:
    scroll = window.findChild(QScrollArea, "SidebarScroll")
    assert scroll is not None
    frame = scroll.widget()
    assert frame is not None
    return [btn.text() for btn in frame.findChildren(QPushButton)]


class EventsTemplates2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_module_registered_near_agenda(self) -> None:
        modules = {m.key: m for m in ModuleManager().get_modules()}
        self.assertIn(MODULE_KEY, modules)
        self.assertEqual(modules[MODULE_KEY].name, MODULE_NAME)

        window = MainWindow()
        texts = _sidebar_texts(window)
        self.assertNotIn(MODULE_NAME, texts)
        self.assertIn(MODULE_KEY, window._page_widgets)
        self.assertIsInstance(window._page_widgets[MODULE_KEY], MeetingTemplatesPage)

    def test_create_and_save_draft_template(self) -> None:
        template = meeting_template_service.create_template(
            name="Rozpracovaná",
            title="",
            location="",
            agenda_items=[],
        )
        self.assertEqual(template.name, "Rozpracovaná")
        self.assertEqual(template.title, "Rozpracovaná")
        reloaded = meeting_template_service.get_by_id(template.id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Rozpracovaná")

        with self.assertRaises(MeetingTemplateValidationError):
            meeting_template_service.create_template(name="  ")

    def test_update_existing_template(self) -> None:
        template = meeting_template_service.create_template(
            name="Původní",
            event_type="Porada",
            title="Starý název",
            priority="Nízká",
        )
        updated = meeting_template_service.update_template(
            template.id,
            name="Upravená",
            event_type="Školení",
            location="Halová",
            priority="Vysoká",
            agenda_items=[
                {"title": "Bod", "moje_sdeleni": "Text", "status": "Připraveno"},
            ],
        )
        self.assertEqual(updated.name, "Upravená")
        self.assertEqual(updated.event_type, "Školení")
        self.assertEqual(updated.title, "Upravená")
        self.assertEqual(updated.location, "Halová")
        self.assertEqual(updated.priority, "Vysoká")
        items = meeting_template_service.parse_agenda_items(updated)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Bod")

    def test_remove_requires_confirmation(self) -> None:
        template = meeting_template_service.create_template(name="Ke smazání")
        page = MeetingTemplatesPage()
        page.refresh()
        # Select row with template
        target_row = None
        for row in range(page.table.rowCount()):
            if page.table.item(row, 1).text() == "Ke smazání":
                target_row = row
                break
        self.assertIsNotNone(target_row)
        page.table.selectRow(target_row)
        page._refresh_action_buttons()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            page.delete_selected()
        self.assertIsNotNone(meeting_template_service.get_by_id(template.id))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            page.delete_selected()
        self.assertIsNone(meeting_template_service.get_by_id(template.id))

    def test_templates_from_templates_1_visible(self) -> None:
        meeting_template_service.create_template(
            name="Z TEMPLATES-1",
            event_type="Schůzka",
            title="Legacy",
            agenda_items=[{"title": "A", "moje_sdeleni": "", "status": "Připraveno"}],
        )
        page = MeetingTemplatesPage()
        names = [
            page.table.item(row, 1).text() for row in range(page.table.rowCount())
        ]
        self.assertIn("Z TEMPLATES-1", names)

    def test_agenda_items_add_reorder_and_participants(self) -> None:
        organizer = person_service.create_person(first_name="Org", last_name="Šablon")
        participant = person_service.create_person(first_name="Účast", last_name="ník")
        dialog = MeetingTemplateDialog()
        self.assertEqual(dialog.windowTitle(), TEMPLATE_DIALOG_TITLE)
        self.assertFalse(dialog.agenda_items_widget.prubeh_jednani_edit.isVisible())
        self.assertFalse(dialog.agenda_items_widget.zaver_edit.isVisible())
        self.assertFalse(dialog.agenda_items_widget.tasks_table.isVisible())

        dialog.name_edit.setText("S účastníky")
        dialog.organizer_selector.set_person_id(organizer.id)
        dialog.participants_selector.set_participants(
            person_ids=[participant.id],
            external_participants=[
                {
                    "full_name": "Host",
                    "organization": "Firma",
                    "function": "",
                    "contact": "",
                    "note": "",
                }
            ],
        )
        dialog.agenda_items_widget.add_item()
        dialog.agenda_items_widget.title_edit.setText("První")
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Sdělení 1")
        dialog.agenda_items_widget.add_item()
        dialog.agenda_items_widget.title_edit.setText("Druhý")
        dialog.agenda_items_widget.selectRow(0)
        dialog.agenda_items_widget.move_item(1)
        items = dialog.agenda_items_widget.get_items()
        self.assertEqual([i["title"] for i in items], ["Druhý", "První"])
        self.assertEqual(items[1]["moje_sdeleni"], "Sdělení 1")
        for item in items:
            self.assertEqual(item.get("prubeh_jednani", ""), "")
            self.assertEqual(item.get("zaver", ""), "")

        data = dialog.get_data()
        template = meeting_template_service.create_template(**data)
        self.assertEqual(
            meeting_template_service.parse_participant_ids(template),
            [participant.id],
        )
        externals = meeting_template_service.parse_external_participants(template)
        self.assertEqual(externals[0]["full_name"], "Host")
        saved_items = meeting_template_service.parse_agenda_items(template)
        self.assertEqual([i["title"] for i in saved_items], ["Druhý", "První"])

    def test_create_meeting_from_template_independent(self) -> None:
        template = meeting_template_service.create_template(
            name="Nezávislost",
            event_type="Kontrolní pochůzka",
            location="Sklad",
            priority="Kritická",
            agenda_items=[
                {
                    "title": "Vstup",
                    "moje_sdeleni": "OOPP",
                    "status": "Odloženo",
                    "prubeh_jednani": "nesmí",
                    "zaver": "nesmí",
                }
            ],
        )
        data = meeting_template_service.meeting_data_from_template(template)
        self.assertEqual(data["title"], "Nezávislost")
        self.assertIsNone(data["starts_at"])
        self.assertIsNone(data["ends_at"])
        self.assertEqual(data["status"], DEFAULT_MEETING_STATUS)
        self.assertEqual(data["proceedings"], "")
        self.assertEqual(data["conclusions"], "")

        meeting = meeting_service.create_meeting(**data)
        items = meeting_template_service.parse_agenda_items(template)
        meeting_agenda_item_service.save_items(meeting.id, items)

        self.assertNotEqual(meeting.id, template.id)
        self.assertIsNone(meeting.starts_at)
        self.assertEqual(meeting.status, STATUS_PLANNED)
        self.assertEqual(meeting.location, "Sklad")
        saved = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(saved), 1)
        self.assertNotEqual(saved[0].id, template.id)
        self.assertEqual(saved[0].title, "Vstup")
        self.assertEqual(saved[0].moje_sdeleni, "OOPP")
        self.assertEqual(saved[0].status, "Odloženo")
        self.assertEqual(saved[0].prubeh_jednani or "", "")
        self.assertEqual(saved[0].zaver or "", "")

        meeting_service.update_meeting(
            meeting.id,
            title="Změněná událost",
            event_type=meeting.event_type,
            starts_at=None,
            ends_at=None,
            location="Jinde",
            organizer_person_id=None,
            participant_ids=[],
            external_participants=[],
            agenda="",
            status=STATUS_PLANNED,
            priority="Nízká",
            proceedings="Průběh události",
            conclusions="Závěr události",
            notes="",
        )
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Jiný bod",
                    "moje_sdeleni": "x",
                    "status": "Projednáno",
                    "prubeh_jednani": "ano",
                    "zaver": "ano",
                }
            ],
        )

        reloaded_template = meeting_template_service.get_by_id(template.id)
        assert reloaded_template is not None
        self.assertEqual(reloaded_template.name, "Nezávislost")
        self.assertEqual(reloaded_template.location, "Sklad")
        tmpl_items = meeting_template_service.parse_agenda_items(reloaded_template)
        self.assertEqual(tmpl_items[0]["title"], "Vstup")

        meeting_template_service.update_template(
            template.id,
            name="Nezávislost",
            event_type="Kontrolní pochůzka",
            location="Nové místo",
            priority="Kritická",
            agenda_items=[{"title": "Nový bod šablony", "moje_sdeleni": "", "status": "Připraveno"}],
        )
        reloaded_meeting = meeting_service.get_by_id(meeting.id)
        assert reloaded_meeting is not None
        self.assertEqual(reloaded_meeting.title, "Změněná událost")
        self.assertEqual(reloaded_meeting.location, "Jinde")
        meeting_items = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(meeting_items[0].title, "Jiný bod")

    def test_meeting_dialog_has_no_save_as_template(self) -> None:
        dialog = MeetingDialog()
        texts = [btn.text() for btn in dialog.findChildren(QPushButton)]
        self.assertNotIn("Uložit jako šablonu...", texts)
        self.assertFalse(hasattr(dialog, "save_as_template_btn"))

    def test_pages_actions(self) -> None:
        page = MeetingTemplatesPage()
        self.assertEqual(page.new_btn.text(), TEMPLATE_ACTION_NEW)
        self.assertEqual(page.delete_btn.text(), TEMPLATE_ACTION_DELETE)
        self.assertFalse(hasattr(page, "open_btn"))
        self.assertFalse(hasattr(page, "remove_btn"))

        from moduly.schuzky.constants import ACTION_OPEN_TEMPLATES
        from moduly.schuzky.ui.schuzky_page import SchuzkyPage

        agenda = AgendaPage()
        self.assertEqual(agenda.new_from_template_btn.text(), ACTION_NEW_FROM_TEMPLATE)
        self.assertEqual(agenda.templates_btn.text(), ACTION_OPEN_TEMPLATES)

        schuzky = SchuzkyPage()
        self.assertEqual(schuzky.templates_btn.text(), ACTION_OPEN_TEMPLATES)


if __name__ == "__main__":
    unittest.main()
