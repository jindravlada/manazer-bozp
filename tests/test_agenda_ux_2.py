"""AGENDA-UX-2: automatická synchronizace dialogu výběru šablon."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

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

    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui import meeting_template_actions
    from moduly.schuzky.ui.meeting_template_actions import open_meeting_templates_window
    from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog


_TEMPLATE_DATA = {
    "event_type": "Porada",
    "location": "",
    "priority": "Normální",
    "organizer_person_id": None,
    "participant_ids": [],
    "external_participants": [],
    "agenda_items": [],
}


class AgendaUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        window = meeting_template_actions._templates_window
        if window is not None:
            window.close()
            meeting_template_actions._templates_window = None

    def _pick_selected_id(self, pick: MeetingTemplatePickDialog) -> int | None:
        return pick._current_table_selection_id()

    def _pick_row_type(self, pick: MeetingTemplatePickDialog, template_id: int) -> str:
        for row in range(pick.table.rowCount()):
            item = pick.table.item(row, 0)
            if item is None:
                continue
            if int(item.data(Qt.ItemDataRole.UserRole)) == template_id:
                return pick.table.item(row, 1).text()
        self.fail(f"Šablona {template_id} nebyla v dialogu výběru nalezena")

    def _select_in_management(self, window, template_id: int) -> None:
        page = window.page
        for row in range(page.table.rowCount()):
            item = page.table.item(row, 0)
            if item is not None and int(item.text()) == template_id:
                page.table.selectRow(row)
                page._refresh_action_buttons()
                return
        self.fail(f"Šablona {template_id} nebyla ve správě nalezena")

    def test_create_selects_new_template_in_pick_dialog(self) -> None:
        existing = meeting_template_service.create_template(name="Původní")
        pick = MeetingTemplatePickDialog()
        pick.reload(existing.id)
        self.assertEqual(self._pick_selected_id(pick), existing.id)

        window = open_meeting_templates_window(pick, on_changed=pick.reload)
        with patch(
            "moduly.schuzky.ui.meeting_templates_page.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.schuzky.ui.meeting_templates_page.MeetingTemplateDialog"
        ) as dialog_cls:
            dialog_cls.return_value.get_data.return_value = {
                "name": "Nová ze správy",
                **_TEMPLATE_DATA,
            }
            window.page.new_template()

        new_id = next(
            t.id
            for t in meeting_template_service.get_all()
            if t.name == "Nová ze správy"
        )
        self.assertEqual(self._pick_selected_id(pick), new_id)
        self.assertTrue(pick.use_btn.isEnabled())

    def test_edit_keeps_selection_in_pick_dialog(self) -> None:
        template = meeting_template_service.create_template(name="K úpravě")
        pick = MeetingTemplatePickDialog()
        pick.reload(template.id)
        self.assertEqual(self._pick_selected_id(pick), template.id)

        window = open_meeting_templates_window(pick, on_changed=pick.reload)
        self._select_in_management(window, template.id)
        with patch(
            "moduly.schuzky.ui.meeting_templates_page.exec_maximized",
            return_value=True,
        ), patch(
            "moduly.schuzky.ui.meeting_templates_page.MeetingTemplateDialog"
        ) as dialog_cls:
            dialog_cls.return_value.get_data.return_value = {
                "name": "Upravená",
                **{**_TEMPLATE_DATA, "event_type": "Školení", "location": "A", "priority": "Vysoká"},
            }
            window.page.edit_selected()

        reloaded = meeting_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Upravená")
        self.assertEqual(self._pick_selected_id(pick), template.id)
        self.assertEqual(self._pick_row_type(pick, template.id), "Školení")
        self.assertTrue(pick.use_btn.isEnabled())

    def test_delete_clears_selection_and_disables_use(self) -> None:
        template = meeting_template_service.create_template(name="Ke smazání")
        other = meeting_template_service.create_template(name="Zůstane")
        pick = MeetingTemplatePickDialog()
        pick.reload(template.id)
        self.assertEqual(self._pick_selected_id(pick), template.id)

        window = open_meeting_templates_window(pick, on_changed=pick.reload)
        self._select_in_management(window, template.id)
        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.page.delete_selected()

        self.assertIsNone(meeting_template_service.get_by_id(template.id))
        self.assertIsNotNone(meeting_template_service.get_by_id(other.id))
        self.assertIsNone(self._pick_selected_id(pick))
        self.assertFalse(pick.use_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
