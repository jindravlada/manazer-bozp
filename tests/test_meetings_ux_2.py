"""MEETINGS-UX-2: přejmenování na Události a typ události."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFormLayout

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

    from core.dashboard.attention_item import ITEM_TYPE_MEETING
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.modules.module_manager import ModuleManager
    from moduly.schuzky.constants import (
        COL_TITLE,
        COL_TYPE,
        COLUMN_HEADERS,
        DEFAULT_EVENT_TYPE,
        DEFAULT_EVENT_TYPES,
        EVENT_TYPE_TRAINING,
        MODULE_KEY,
        MODULE_NAME,
    )
    from moduly.schuzky.sluzby.meeting_event_type_service import (
        meeting_event_type_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage


class MeetingsUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_module_renamed_to_udalosti(self) -> None:
        self.assertEqual(MODULE_NAME, "Události")
        modules = ModuleManager().get_modules()
        schuzky = next(m for m in modules if m.key == MODULE_KEY)
        self.assertEqual(schuzky.name, "Události")
        page = SchuzkyPage()
        self.assertEqual(page.new_btn.text(), "Nová událost")
        self.assertIn("událost", page.text_filter.search_edit.placeholderText().casefold())

    def test_event_type_codebook_defaults(self) -> None:
        names = meeting_event_type_service.get_active_names()
        for expected in DEFAULT_EVENT_TYPES:
            self.assertIn(expected, names)
        self.assertEqual(names[0], DEFAULT_EVENT_TYPE)

    def test_dialog_has_event_type_and_title_label(self) -> None:
        dialog = MeetingDialog()
        self.assertEqual(dialog.windowTitle(), "Událost")
        self.assertEqual(dialog.event_type_combo.currentText(), DEFAULT_EVENT_TYPE)
        for name in DEFAULT_EVENT_TYPES:
            self.assertGreaterEqual(dialog.event_type_combo.findText(name), 0)

        form = dialog.tabs.widget(0).layout()
        assert isinstance(form, QFormLayout)
        labels = [
            form.labelForField(form.itemAt(i, QFormLayout.ItemRole.FieldRole).widget()).text()
            for i in range(form.rowCount())
            if form.itemAt(i, QFormLayout.ItemRole.FieldRole) is not None
            and form.labelForField(form.itemAt(i, QFormLayout.ItemRole.FieldRole).widget())
            is not None
        ]
        self.assertIn("Typ události:", labels)
        self.assertIn("Název události:", labels)
        self.assertNotIn("Název:", labels)

    def test_save_and_reload_event_type(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Bezpečnostní školení",
            event_type=EVENT_TYPE_TRAINING,
            starts_at=datetime.now() + timedelta(days=1),
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.event_type, EVENT_TYPE_TRAINING)

        meeting_service.update_meeting(
            meeting.id,
            title=reloaded.title,
            event_type="Porada",
            starts_at=reloaded.starts_at,
            ends_at=reloaded.ends_at,
            location=reloaded.location,
            organizer_person_id=reloaded.organizer_person_id,
            participant_ids=[],
            agenda=reloaded.agenda,
            status=reloaded.status,
        )
        again = meeting_service.get_by_id(meeting.id)
        assert again is not None
        self.assertEqual(again.event_type, "Porada")

        dialog = MeetingDialog(meeting=again)
        self.assertEqual(dialog.event_type_combo.currentText(), "Porada")
        self.assertEqual(dialog.title_edit.text(), "Bezpečnostní školení")

    def test_list_shows_type_column(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Kontrola skladu",
            event_type="Kontrolní pochůzka",
            location="Sklad",
        )
        page = SchuzkyPage()
        page.refresh()
        self.assertEqual(COLUMN_HEADERS[COL_TYPE], "Typ")
        self.assertEqual(COLUMN_HEADERS[COL_TITLE], "Název události")

        found = None
        for row in range(page.table.rowCount()):
            if page.table.item(row, COL_TITLE).text() == "Kontrola skladu":
                found = row
                break
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(page.table.item(found, COL_TYPE).text(), "Kontrolní pochůzka")
        self.assertEqual(page.table.item(found, 0).text(), str(meeting.id))

    def test_workplace_shows_type_before_title(self) -> None:
        starts = datetime.now() + timedelta(days=3)
        meeting = meeting_service.create_meeting(
            title="Online stand-up",
            event_type="Online schůzka",
            starts_at=starts,
        )
        items = [
            item
            for item in get_attention_items()
            if item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Online schůzka – Online stand-up")

        widget = UpcomingTasksWidget()
        found = False
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                found = True
                self.assertEqual(widget.table.item(row, 0).text(), "Událost")
                self.assertEqual(
                    widget.table.item(row, 2).text(),
                    "Online schůzka – Online stand-up",
                )
                break
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
