"""AGENDA-UX-5: maximalizace úkolu a inicializace výběru šablony."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="agenda-ux-5-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui import meeting_template_actions
    from moduly.schuzky.ui.meeting_template_actions import (
        create_meeting_from_template,
        open_meeting_templates_window,
    )
    from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog


class AgendaUx5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        window = meeting_template_actions._templates_window
        if window is not None:
            window.close()
            meeting_template_actions._templates_window = None

    def test_new_task_opens_maximized(self) -> None:
        page = AgendaPage()
        with patch(
            "moduly.agenda.ui.agenda_page.exec_maximized",
            return_value=0,
        ) as mocked:
            page.new_task()
        mocked.assert_called_once()
        dialog = mocked.call_args.args[0]
        from moduly.ukoly.ui.task_dialog import TaskDialog

        self.assertIsInstance(dialog, TaskDialog)

    def test_use_enabled_when_template_selected_on_open(self) -> None:
        meeting_template_service.create_template(name="UX5 šablona")
        pick = MeetingTemplatePickDialog()
        self.assertIsNotNone(pick._current_table_selection_id())
        self.assertTrue(pick.use_btn.isEnabled())

    def test_use_disabled_without_selection(self) -> None:
        meeting_template_service.create_template(name="UX5 bez výběru")
        pick = MeetingTemplatePickDialog()
        pick.table.clearSelection()
        pick._refresh_action_buttons()
        self.assertIsNone(pick._current_table_selection_id())
        self.assertFalse(pick.use_btn.isEnabled())

    def test_use_enabled_after_row_selection(self) -> None:
        meeting_template_service.create_template(name="UX5 výběr")
        pick = MeetingTemplatePickDialog()
        pick.table.clearSelection()
        pick._refresh_action_buttons()
        self.assertFalse(pick.use_btn.isEnabled())

        pick.table.selectRow(0)
        pick._refresh_action_buttons()
        self.assertTrue(pick.use_btn.isEnabled())

    def test_double_click_uses_selected_template(self) -> None:
        template = meeting_template_service.create_template(name="UX5 dvojklik")
        pick = MeetingTemplatePickDialog()
        pick.reload(template.id)
        pick._on_use()
        self.assertEqual(pick.result(), pick.DialogCode.Accepted)
        self.assertEqual(pick.selected_template_id(), template.id)

    def test_return_from_templates_keeps_use_state(self) -> None:
        template = meeting_template_service.create_template(name="UX5 návrat")
        pick = MeetingTemplatePickDialog()
        pick.reload(template.id)
        self.assertTrue(pick.use_btn.isEnabled())
        self.assertEqual(pick._current_table_selection_id(), template.id)

        window = open_meeting_templates_window(
            pick,
            on_changed=pick.reload,
            on_closed=lambda *_args: pick.reload(),
        )
        window.close()
        QApplication.processEvents()

        self.assertEqual(pick._current_table_selection_id(), template.id)
        self.assertTrue(pick.use_btn.isEnabled())

    def test_create_meeting_from_template_unchanged(self) -> None:
        template = meeting_template_service.create_template(
            name="UX5 vytvoření",
            event_type="Porada",
        )
        parent = AgendaPage()
        with patch(
            "moduly.schuzky.ui.meeting_template_actions.MeetingTemplatePickDialog"
        ) as pick_cls, patch(
            "moduly.schuzky.ui.meeting_template_actions.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.schuzky.ui.meeting_template_actions.MeetingDialog"
        ) as meeting_dialog_cls, patch(
            "moduly.schuzky.ui.meeting_template_actions.meeting_service.create_meeting"
        ) as create_meeting, patch(
            "moduly.schuzky.ui.meeting_template_actions.meeting_agenda_item_service.save_items"
        ) as save_items:
            pick = pick_cls.return_value
            pick.exec.return_value = pick.DialogCode.Accepted
            pick.selected_template_id.return_value = template.id
            meeting_dialog_cls.return_value.get_data.return_value = {
                "title": "Z šablony",
                "event_type": "Porada",
                "starts_at": None,
                "ends_at": None,
                "location": "",
                "organizer_person_id": None,
                "participant_ids": [],
                "external_participants": [],
                "agenda": "",
                "status": "Plánováno",
                "proceedings": "",
                "conclusions": "",
                "notes": "",
                "priority": "Normální",
            }
            meeting_dialog_cls.return_value.get_agenda_items.return_value = []
            created = type("M", (), {"id": 99})()
            create_meeting.return_value = created

            result = create_meeting_from_template(parent)

        self.assertTrue(result)
        create_meeting.assert_called_once()
        save_items.assert_called_once_with(99, [])
        meeting_dialog_cls.assert_called_once()
        used_template = meeting_dialog_cls.call_args.kwargs["template"]
        self.assertEqual(used_template.id, template.id)


if __name__ == "__main__":
    unittest.main()
