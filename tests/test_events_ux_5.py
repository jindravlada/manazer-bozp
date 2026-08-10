"""EVENTS-UX-5: priorita událostí a barvy Agendy podle priority."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFormLayout

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_meeting_priority_column,
        initialize_database,
    )

    initialize_database()

    from moduly.agenda.constants import (
        COL_TITLE,
        PRIORITY_COLORS,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_LOW,
        PRIORITY_NORMAL,
        ROW_LEGEND,
        STATUS_MODE_ALL,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import (
        COL_PRIORITY,
        COL_TITLE as MEETING_COL_TITLE,
        COLUMN_HEADERS,
        DEFAULT_MEETING_PRIORITY,
        MEETING_PRIORITIES,
        MEETING_PRIORITY_RANK,
        PRIORITY_CRITICAL as MEETING_PRIORITY_CRITICAL,
        PRIORITY_HIGH as MEETING_PRIORITY_HIGH,
        PRIORITY_LOW as MEETING_PRIORITY_LOW,
        PRIORITY_NORMAL as MEETING_PRIORITY_NORMAL,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage
    from moduly.ukoly.sluzby.task_service import task_service


class EventsUx5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") == "Zrušeno":
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                event_type=getattr(meeting, "event_type", None) or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status="Zrušeno",
                priority=getattr(meeting, "priority", None) or DEFAULT_MEETING_PRIORITY,
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )
        for task in list(task_service.get_all_tasks()):
            if task.computed_status != "Zrušeno":
                task_service.cancel_task(task.id)

    def test_priority_constants_match_tasks(self) -> None:
        self.assertEqual(
            list(MEETING_PRIORITIES),
            ["Nízká", "Normální", "Vysoká", "Kritická"],
        )
        self.assertEqual(DEFAULT_MEETING_PRIORITY, "Normální")
        self.assertEqual(MEETING_PRIORITY_RANK[MEETING_PRIORITY_CRITICAL], 0)
        self.assertEqual(MEETING_PRIORITY_RANK[MEETING_PRIORITY_LOW], 3)

    def test_default_priority_on_create(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Bez priority",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.priority, DEFAULT_MEETING_PRIORITY)

    def test_edit_priority(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Editace priority",
            starts_at=datetime.now() + timedelta(days=1),
            priority=MEETING_PRIORITY_NORMAL,
        )
        meeting_service.update_meeting(
            meeting.id,
            title=meeting.title,
            event_type=getattr(meeting, "event_type", None) or "",
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            location=meeting.location or "",
            organizer_person_id=meeting.organizer_person_id,
            participant_ids=[],
            agenda=meeting.agenda or "",
            status=meeting.status,
            priority=MEETING_PRIORITY_HIGH,
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.priority, MEETING_PRIORITY_HIGH)

        dialog = MeetingDialog(meeting=reloaded)
        self.assertEqual(dialog.priority_combo.currentText(), MEETING_PRIORITY_HIGH)
        data = dialog.get_data()
        self.assertEqual(data["priority"], MEETING_PRIORITY_HIGH)

    def test_dialog_has_priority_under_type(self) -> None:
        dialog = MeetingDialog()
        self.assertEqual(dialog.priority_combo.currentText(), DEFAULT_MEETING_PRIORITY)
        for name in MEETING_PRIORITIES:
            self.assertGreaterEqual(dialog.priority_combo.findText(name), 0)

        form = dialog.tabs.widget(0).layout()
        assert isinstance(form, QFormLayout)
        labels = []
        for i in range(form.rowCount()):
            field = form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if field is None or field.widget() is None:
                continue
            label = form.labelForField(field.widget())
            if label is not None:
                labels.append(label.text())
        self.assertIn("Typ události:", labels)
        self.assertIn("Priorita:", labels)
        self.assertLess(labels.index("Typ události:"), labels.index("Priorita:"))

    def test_list_shows_priority_column_and_sort(self) -> None:
        low = meeting_service.create_meeting(
            title="Nízká priorita",
            starts_at=datetime.now() + timedelta(days=2),
            priority=MEETING_PRIORITY_LOW,
        )
        critical = meeting_service.create_meeting(
            title="Kritická priorita",
            starts_at=datetime.now() + timedelta(days=3),
            priority=MEETING_PRIORITY_CRITICAL,
        )
        self.assertEqual(COLUMN_HEADERS[COL_PRIORITY], "Priorita")

        page = SchuzkyPage()
        page.refresh()
        by_title = {}
        for row in range(page.table.rowCount()):
            title = page.table.item(row, MEETING_COL_TITLE).text()
            by_title[title] = page.table.item(row, COL_PRIORITY).text()

        self.assertEqual(by_title["Nízká priorita"], MEETING_PRIORITY_LOW)
        self.assertEqual(by_title["Kritická priorita"], MEETING_PRIORITY_CRITICAL)

        page.table.sortItems(COL_PRIORITY, Qt.SortOrder.AscendingOrder)
        priorities = [
            page.table.item(row, COL_PRIORITY).text()
            for row in range(page.table.rowCount())
            if page.table.item(row, MEETING_COL_TITLE).text()
            in {"Nízká priorita", "Kritická priorita"}
        ]
        self.assertEqual(priorities[0], MEETING_PRIORITY_CRITICAL)
        self.assertEqual(priorities[-1], MEETING_PRIORITY_LOW)
        self.assertEqual(low.priority, MEETING_PRIORITY_LOW)
        self.assertEqual(critical.priority, MEETING_PRIORITY_CRITICAL)

    def test_agenda_colors_by_priority(self) -> None:
        task = task_service.create_task(
            title="Úkol kritický",
            due_date=date.today() + timedelta(days=1),
            priority=PRIORITY_CRITICAL,
        )
        meeting = meeting_service.create_meeting(
            title="Událost vysoká",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
            priority=PRIORITY_HIGH,
        )
        normal = meeting_service.create_meeting(
            title="Událost normální",
            starts_at=datetime.now() + timedelta(days=2),
            status=STATUS_PLANNED,
            priority=PRIORITY_NORMAL,
        )

        items = {(i.item_type, i.source_id): i for i in agenda_service.get_items()}
        self.assertEqual(items[("task", task.id)].priority, PRIORITY_CRITICAL)
        self.assertEqual(items[("meeting", meeting.id)].priority, PRIORITY_HIGH)
        self.assertEqual(items[("meeting", normal.id)].priority, PRIORITY_NORMAL)

        page = AgendaPage()
        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        self.assertEqual(page.legend.text(), ROW_LEGEND)

        colors = {}
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            colors[(payload.item_type, payload.source_id)] = (
                page.table.item(row, COL_TITLE).background().color()
            )

        self.assertEqual(colors[("task", task.id)], QColor(PRIORITY_COLORS[PRIORITY_CRITICAL]))
        self.assertEqual(
            colors[("meeting", meeting.id)],
            QColor(PRIORITY_COLORS[PRIORITY_HIGH]),
        )
        self.assertEqual(
            colors[("meeting", normal.id)],
            QColor(PRIORITY_COLORS[PRIORITY_NORMAL]),
        )
        self.assertEqual(PRIORITY_COLORS[PRIORITY_LOW], "#c8e6c9")

    def test_migration_sets_normal_priority(self) -> None:
        from core.database.database_initializer import _table_columns
        from unittest.mock import patch

        self.assertIn("priority", _table_columns("meetings"))

        with patch(
            "core.database.database_initializer._table_columns",
            return_value={"id", "title", "status", "event_type"},
        ), patch(
            "core.database.database_initializer._add_column"
        ) as add_column:
            _ensure_meeting_priority_column()
            add_column.assert_called_once_with(
                "meetings",
                "priority VARCHAR(30) DEFAULT 'Normální' NOT NULL",
            )

        # Idempotentně – sloupec už existuje, nic se nepřidá.
        with patch("core.database.database_initializer._add_column") as add_column:
            _ensure_meeting_priority_column()
            add_column.assert_not_called()

        meeting = meeting_service.create_meeting(
            title="Po migraci",
            starts_at=datetime.now() + timedelta(days=4),
            status=STATUS_PLANNED,
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.priority, "Normální")


if __name__ == "__main__":
    unittest.main()
