"""EVENTS-BUG-1: všechny naplánované události v agendě."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
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

    from core.dashboard.attention_item import ITEM_TYPE_MEETING
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.widgets.typed_table_sort import (
        compare_typed_sort_values,
        typed_date,
        typed_datetime,
    )
    from moduly.schuzky.constants import DEFAULT_MEETING_STATUS, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage
    from moduly.ukoly.sluzby.task_service import task_service


def _meeting_items():
    return [item for item in get_attention_items() if item.item_type == ITEM_TYPE_MEETING]


def _payloads(widget: UpcomingTasksWidget):
    rows = []
    for row in range(widget.table.rowCount()):
        payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if payload is not None:
            rows.append(payload)
    return rows


class EventsBug1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from moduly.schuzky.constants import STATUS_CANCELLED

        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") != STATUS_PLANNED:
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
                status=STATUS_CANCELLED,
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)

    def test_two_same_type_both_appear(self) -> None:
        day = datetime(2026, 8, 10, 7, 0)
        a = meeting_service.create_meeting(
            title="Ráno",
            event_type="Schůzka",
            starts_at=day,
            status=STATUS_PLANNED,
        )
        b = meeting_service.create_meeting(
            title="Dopoledne",
            event_type="Schůzka",
            starts_at=day.replace(hour=8),
            status=STATUS_PLANNED,
        )
        items = _meeting_items()
        ids = {item.source_id for item in items}
        self.assertEqual(ids, {a.id, b.id})
        self.assertEqual(len(ids), 2)

    def test_two_same_day_both_appear(self) -> None:
        a = meeting_service.create_meeting(
            title="A",
            starts_at=datetime(2026, 8, 10, 7, 0),
            status=DEFAULT_MEETING_STATUS,
        )
        b = meeting_service.create_meeting(
            title="B",
            starts_at=datetime(2026, 8, 10, 8, 0),
            status=DEFAULT_MEETING_STATUS,
        )
        items = _meeting_items()
        self.assertEqual({i.source_id for i in items}, {a.id, b.id})

    def test_untitled_shows_as_bez_nazvu(self) -> None:
        meeting = meeting_service.create_meeting(
            title="",
            event_type="Schůzka",
            starts_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        items = [i for i in _meeting_items() if i.source_id == meeting.id]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Schůzka – Bez názvu")

        widget = UpcomingTasksWidget()
        widget.refresh()
        titles = [
            p.title
            for p in _payloads(widget)
            if p.item_type == ITEM_TYPE_MEETING and p.source_id == meeting.id
        ]
        self.assertEqual(titles, ["Schůzka – Bez názvu"])

    def test_date_change_visible_after_refresh(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Přesun",
            starts_at=datetime(2026, 8, 4, 10, 0),
            status=STATUS_PLANNED,
        )
        widget = UpcomingTasksWidget()
        widget.refresh()
        before = next(p for p in _payloads(widget) if p.source_id == meeting.id)
        self.assertEqual(before.event_at, datetime(2026, 8, 4, 10, 0))

        meeting_service.update_meeting(
            meeting.id,
            title="Přesun",
            starts_at=datetime(2026, 8, 20, 15, 30),
            status=STATUS_PLANNED,
        )
        widget.refresh()
        after = next(p for p in _payloads(widget) if p.source_id == meeting.id)
        self.assertEqual(after.event_at, datetime(2026, 8, 20, 15, 30))

    def test_source_ids_remain_distinct(self) -> None:
        starts = datetime(2026, 8, 10, 7, 0)
        ids = []
        for i in range(3):
            m = meeting_service.create_meeting(
                title=f"E{i}",
                event_type="Schůzka",
                starts_at=starts.replace(hour=7 + i),
                status=STATUS_PLANNED,
            )
            ids.append(m.id)
        items = _meeting_items()
        source_ids = [i.source_id for i in items if i.source_id in ids]
        self.assertEqual(sorted(source_ids), sorted(ids))
        self.assertEqual(len(set(source_ids)), 3)

    def test_chronological_order_with_tasks(self) -> None:
        """Událost s časem se řadí na společné ose s úkoly (DATE vs DATETIME)."""
        task = task_service.create_task(
            title="Úkol později",
            due_date=date(2026, 8, 15),
        )
        early = meeting_service.create_meeting(
            title="Brzy",
            starts_at=datetime(2026, 8, 10, 7, 0),
            status=STATUS_PLANNED,
        )
        late = meeting_service.create_meeting(
            title="Později",
            starts_at=datetime(2026, 8, 20, 8, 0),
            status=STATUS_PLANNED,
        )

        # Collector: chronologicky
        items = get_attention_items()
        relevant = [
            i
            for i in items
            if (i.item_type == ITEM_TYPE_MEETING and i.source_id in {early.id, late.id})
            or (i.item_type == "task" and i.source_id == task.id)
        ]
        self.assertEqual(
            [i.source_id for i in relevant],
            [early.id, task.id, late.id],
        )

        # Panel po sortItems: stejné pořadí (ne DATE před DATETIME)
        widget = UpcomingTasksWidget()
        widget.refresh()
        payloads = [
            p
            for p in _payloads(widget)
            if (p.item_type == ITEM_TYPE_MEETING and p.source_id in {early.id, late.id})
            or (p.item_type == "task" and p.source_id == task.id)
        ]
        self.assertEqual(
            [p.source_id for p in payloads],
            [early.id, task.id, late.id],
        )

    def test_date_and_datetime_compare_on_same_timeline(self) -> None:
        left = typed_date(date(2026, 8, 10))
        right = typed_datetime(datetime(2026, 8, 10, 7, 0))
        # půlnoc před 07:00
        self.assertEqual(compare_typed_sort_values(left, right, ascending=True), -1)
        later = typed_datetime(datetime(2026, 8, 11, 0, 0))
        self.assertEqual(compare_typed_sort_values(left, later, ascending=True), -1)
        earlier = typed_datetime(datetime(2026, 8, 9, 23, 0))
        self.assertEqual(compare_typed_sort_values(left, earlier, ascending=True), 1)

    def test_refresh_after_save_adds_event(self) -> None:
        page = SchuzkyPage()
        upcoming = UpcomingTasksWidget()
        page.set_dashboard_refresh_callback(upcoming.refresh)

        meeting = meeting_service.create_meeting(
            title="Nová",
            starts_at=datetime.now() + timedelta(days=3),
            status=DEFAULT_MEETING_STATUS,
        )
        page._refresh_dashboard()
        found = any(
            p.source_id == meeting.id and p.item_type == ITEM_TYPE_MEETING
            for p in _payloads(upcoming)
        )
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
