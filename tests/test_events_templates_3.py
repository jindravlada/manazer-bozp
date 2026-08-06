"""EVENTS-TEMPLATES-3: zjednodušení správy šablon."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

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

    from core.windows.main_window import MainWindow
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.sablony_udalosti.constants import MODULE_NAME
    from moduly.schuzky.constants import ACTION_OPEN_TEMPLATES
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_template_dialog import MeetingTemplateDialog
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage


def _sidebar_texts(window: MainWindow) -> list[str]:
    scroll = window.findChild(QScrollArea, "SidebarScroll")
    assert scroll is not None
    frame = scroll.widget()
    assert frame is not None
    return [btn.text() for btn in frame.findChildren(QPushButton)]


class EventsTemplates3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_templates_not_in_sidebar(self) -> None:
        window = MainWindow()
        texts = _sidebar_texts(window)
        self.assertNotIn(MODULE_NAME, texts)
        self.assertNotIn("Šablony událostí", texts)

    def test_templates_button_on_events_not_agenda(self) -> None:
        agenda = AgendaPage()
        schuzky = SchuzkyPage()
        self.assertFalse(hasattr(agenda, "templates_btn"))
        self.assertEqual(schuzky.templates_btn.text(), ACTION_OPEN_TEMPLATES)
        self.assertEqual(ACTION_OPEN_TEMPLATES, "Šablony...")

    def test_template_editor_has_single_name_field(self) -> None:
        dialog = MeetingTemplateDialog()
        self.assertTrue(hasattr(dialog, "name_edit"))
        self.assertFalse(hasattr(dialog, "title_edit"))
        dialog.name_edit.setText("Týdenní porada BOZP")
        data = dialog.get_data()
        self.assertEqual(data["name"], "Týdenní porada BOZP")
        self.assertEqual(data["title"], "Týdenní porada BOZP")

        template = meeting_template_service.create_template(**data)
        self.assertEqual(template.name, "Týdenní porada BOZP")
        self.assertEqual(template.title, "Týdenní porada BOZP")

    def test_new_event_title_prefilled_from_template_name(self) -> None:
        template = meeting_template_service.create_template(
            name="Kontrola skladu",
            event_type="Kontrolní pochůzka",
            location="Sklad",
        )
        dialog = MeetingDialog(template=template)
        self.assertEqual(dialog.title_edit.text(), "Kontrola skladu")

        dialog.title_edit.setText("Kontrola skladu – upraveno")
        data = dialog.get_data()
        self.assertEqual(data["title"], "Kontrola skladu – upraveno")

        meeting = meeting_service.create_meeting(**data)
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Kontrola skladu – upraveno")
        # Šablona zůstává beze změny.
        unchanged = meeting_template_service.get_by_id(template.id)
        assert unchanged is not None
        self.assertEqual(unchanged.name, "Kontrola skladu")


if __name__ == "__main__":
    unittest.main()
