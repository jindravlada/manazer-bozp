"""AGENDA-UX-1 (šablony): zjednodušení práce se šablonami událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

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

    from moduly.agenda.constants import ACTION_NEW_FROM_TEMPLATE
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import ACTION_OPEN_TEMPLATES, TEMPLATE_BTN_USE
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui import meeting_template_actions
    from moduly.schuzky.ui.meeting_template_actions import (
        MeetingTemplatesWindow,
        open_meeting_templates_window,
    )
    from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog


class AgendaUxSablonyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        window = meeting_template_actions._templates_window
        if window is not None:
            window.close()
            meeting_template_actions._templates_window = None

    def test_agenda_toolbar_without_templates_button(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.new_from_template_btn.text(), "Nová událost ze šablony")
        self.assertEqual(page.new_from_template_btn.text(), ACTION_NEW_FROM_TEMPLATE)
        self.assertFalse(page.new_from_template_btn.text().endswith("..."))
        self.assertFalse(hasattr(page, "templates_btn"))
        self.assertFalse(hasattr(page, "open_templates"))

    def test_pick_dialog_opens_from_agenda_action(self) -> None:
        page = AgendaPage()
        with patch(
            "moduly.agenda.ui.agenda_page.create_meeting_from_template",
            return_value=False,
        ) as create:
            page.new_meeting_from_template()
            create.assert_called_once_with(page)

    def test_pick_dialog_has_manage_and_standard_buttons(self) -> None:
        meeting_template_service.create_template(name="UX1 šablona")
        dialog = MeetingTemplatePickDialog()
        self.assertEqual(dialog.windowTitle(), "Nová událost ze šablony")
        self.assertEqual(dialog.manage_btn.text(), ACTION_OPEN_TEMPLATES)
        self.assertEqual(dialog.use_btn.text(), TEMPLATE_BTN_USE)
        self.assertEqual(dialog.close_btn.text(), "Zavřít")
        self.assertFalse(dialog.use_btn.icon().isNull())
        self.assertFalse(dialog.close_btn.icon().isNull())
        self.assertEqual(
            dialog.windowModality(),
            Qt.WindowModality.NonModal,
        )

    def test_manage_opens_non_blocking_templates_window(self) -> None:
        dialog = MeetingTemplatePickDialog()
        window = open_meeting_templates_window(dialog)
        self.assertIsInstance(window, MeetingTemplatesWindow)
        self.assertTrue(window.isVisible())
        self.assertEqual(
            window.windowModality(),
            Qt.WindowModality.NonModal,
        )
        self.assertFalse(window.isModal())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        window.close()

    def test_after_manage_closed_pick_can_continue(self) -> None:
        dialog = MeetingTemplatePickDialog()
        before = dialog.table.rowCount()
        meeting_template_service.create_template(name="Po správě")
        window = open_meeting_templates_window(dialog, on_closed=dialog._load)
        window.close()
        QApplication.processEvents()
        self.assertGreaterEqual(dialog.table.rowCount(), before + 1)


if __name__ == "__main__":
    unittest.main()
