"""MEETINGS-2e: stavy bodů jednání."""

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

    from moduly.schuzky.constants import (
        AGENDA_ITEM_STATUS_DISCUSSED,
        AGENDA_ITEM_STATUS_ICONS,
        AGENDA_ITEM_STATUS_POSTPONED,
        AGENDA_ITEM_STATUS_READY,
        DEFAULT_AGENDA_ITEM_STATUS,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings2eTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_default_status_and_save_reload(self) -> None:
        meeting = meeting_service.create_meeting(title="Stavy bodů")
        saved = meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "Téma 1"}],
        )
        self.assertEqual(saved[0].status, DEFAULT_AGENDA_ITEM_STATUS)

        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "id": saved[0].id,
                    "title": "Téma 1",
                    "status": AGENDA_ITEM_STATUS_DISCUSSED,
                }
            ],
        )
        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(reloaded[0].status, AGENDA_ITEM_STATUS_DISCUSSED)

        dialog = MeetingDialog(meeting=meeting)
        self.assertEqual(
            dialog.agenda_items_widget.status_combo.currentText(),
            AGENDA_ITEM_STATUS_DISCUSSED,
        )
        icon = AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_DISCUSSED]
        self.assertEqual(
            dialog.agenda_items_widget.table.item(0).text(),
            f"{icon} 1. Téma 1",
        )

    def test_change_via_editor_combo(self) -> None:
        meeting = meeting_service.create_meeting(title="Editor stavu")
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {"title": "A", "status": AGENDA_ITEM_STATUS_READY},
                {"title": "B", "status": AGENDA_ITEM_STATUS_READY},
            ],
        )
        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)
        labels_before = [
            widget.table.item(row).text() for row in range(widget.table.count())
        ]

        widget.status_combo.setCurrentText(AGENDA_ITEM_STATUS_POSTPONED)
        self.assertEqual(
            widget._items[0]["status"],
            AGENDA_ITEM_STATUS_POSTPONED,
        )
        icon = AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_POSTPONED]
        self.assertEqual(widget.table.item(0).text(), f"{icon} 1. A")
        self.assertEqual(
            [widget.table.item(row).text() for row in range(2)][1],
            labels_before[1],
        )
        self.assertIn("2. B", widget.table.item(1).text())

        meeting_agenda_item_service.save_items(meeting.id, widget.get_items())
        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(reloaded[0].status, AGENDA_ITEM_STATUS_POSTPONED)
        self.assertEqual(reloaded[1].status, AGENDA_ITEM_STATUS_READY)

    def test_change_via_context_menu_action(self) -> None:
        meeting = meeting_service.create_meeting(title="Kontextové menu")
        meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "Bod", "status": AGENDA_ITEM_STATUS_READY}],
        )
        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)

        # Handler kontextového menu „Označit jako“ (bez blokujícího menu.exec).
        widget.table.selectRow(0)
        widget._set_item_status(0, AGENDA_ITEM_STATUS_DISCUSSED)
        self.assertEqual(widget._items[0]["status"], AGENDA_ITEM_STATUS_DISCUSSED)
        self.assertEqual(
            widget.status_combo.currentText(),
            AGENDA_ITEM_STATUS_DISCUSSED,
        )
        self.assertEqual(
            widget.table.contextMenuPolicy().name,
            "CustomContextMenu",
        )

        meeting_agenda_item_service.save_items(meeting.id, widget.get_items())
        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(reloaded[0].status, AGENDA_ITEM_STATUS_DISCUSSED)

    def test_list_shows_compact_status_order_title(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._items = [
            {"title": "Revize", "status": AGENDA_ITEM_STATUS_READY, "display_order": 10},
        ]
        widget._refresh_table(select_row=0)
        icon = AGENDA_ITEM_STATUS_ICONS[AGENDA_ITEM_STATUS_READY]
        self.assertEqual(widget.table.item(0).text(), f"{icon} 1. Revize")
        self.assertIn("item:selected", widget.table.styleSheet())


if __name__ == "__main__":
    unittest.main()
