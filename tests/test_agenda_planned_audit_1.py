"""Plánované audity ve společném přehledu Agendy, bez kopie do databáze."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_AUDIT, SOURCE_LABEL_AUDIT
    from core.dashboard.attention_service import (
        count_overdue_attention_items,
        get_attention_items,
        planned_audit_reminder_items,
    )
    from core.dashboard.widget_calendar_placeholder import build_calendar_day_data
    from core.dashboard.widget_today import TodayWidget
    from core.dashboard.widget_upcoming_tasks import (
        COL_DUE as UPCOMING_DUE,
        COL_TITLE as UPCOMING_TITLE,
        COL_TYPE as UPCOMING_TYPE,
        UpcomingTasksWidget,
    )
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import (
        COL_DUE,
        COL_TITLE,
        COL_TYPE,
        DEFAULT_PRIORITY_COLOR,
        ITEM_TYPE_AUDIT_PLAN,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        PRIORITY_LOW,
        STATUS_MODE_ACTIVE,
        STATUS_MODE_ALL,
        STATUS_MODE_CANCELLED,
        STATUS_MODE_CLOSED,
        STATUS_MODE_DONE,
        STATUS_MODE_PLANNED,
        TYPE_LABEL_PLAN,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.audity.constants import AUDIT_STATUS_PLANOVANO
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


_PLANNED = date(2026, 12, 10)
_TODAY = date(2026, 12, 1)


def _record_counts() -> dict[str, int]:
    from sqlalchemy import text

    from core.database.session import get_session

    with get_session() as session:
        names = session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ).scalars()
        return {
            name: int(session.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() or 0)
            for name in names
        }


class AgendaPlannedAudit1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._clear_records()

    def tearDown(self) -> None:
        self._clear_records()

    def _clear_records(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") == "Zrušeno":
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status="Zrušeno",
            )

    def _plans(self, items, audit_id: int):
        return [
            item
            for item in items
            if item.item_type == ITEM_TYPE_AUDIT_PLAN and int(item.source_id) == int(audit_id)
        ]

    def _running(self, items, audit_id: int):
        return [
            item
            for item in items
            if item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == int(audit_id)
        ]

    def test_one_planned_audit_is_one_agenda_row(self) -> None:
        before = _record_counts()
        first = audit_service.create_audit(
            workplace_name="Provoz A",
            year=2026,
            audit_date=_PLANNED,
        )
        second = audit_service.create_audit(
            workplace_name="Provoz B",
            year=2026,
            audit_date=_PLANNED,
        )
        after_create = _record_counts()
        items = agenda_service.get_items(today=_TODAY)
        self.assertEqual(_record_counts(), after_create)
        self.assertEqual(after_create["audits"], before["audits"] + 2)
        self.assertEqual(after_create["tasks"], before["tasks"])
        self.assertEqual(after_create["meetings"], before["meetings"])

        plans = self._plans(items, first.id)
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.type_label, TYPE_LABEL_PLAN)
        self.assertEqual(plan.title, "Audit Provoz A")
        self.assertEqual(plan.attention.type_label, TYPE_LABEL_PLAN)
        self.assertTrue(plan.attention.open_metadata.get("planned"))
        self.assertEqual(plan.due_date, _PLANNED)
        self.assertIsNone(plan.event_at)
        self.assertEqual(plan.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(plan.source, SOURCE_LABEL_AUDIT)
        self.assertEqual(plan.person, "")
        self.assertEqual(plan.priority, "")
        self.assertEqual(plan.item_type, ITEM_TYPE_AUDIT_PLAN)
        self.assertIsNotNone(plan.attention)
        self.assertEqual(plan.attention.item_type, ITEM_TYPE_AUDIT)
        self.assertEqual(plan.attention.source_id, first.id)
        self.assertEqual(len(self._plans(items, second.id)), 1)
        self.assertEqual(len(self._running(items, first.id)), 0)

        page = AgendaPage()
        page.refresh()
        payload = self._select(page, first.id)
        row = page.table.currentRow()
        self.assertEqual(page.table.item(row, COL_TYPE).text(), TYPE_LABEL_PLAN)
        self.assertEqual(page.table.item(row, COL_TITLE).text(), plan.title)
        self.assertEqual(page.table.item(row, COL_DUE).text(), "10. 12. 2026")
        self.assertEqual(
            page.table.item(row, COL_TITLE).background().color(),
            QColor(DEFAULT_PRIORITY_COLOR),
        )
        self.assertEqual(payload.due_date, _PLANNED)
        page.close()

    def test_date_change_and_removal(self) -> None:
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        self.assertEqual(self._plans(agenda_service.get_items(today=_TODAY), audit.id)[0].due_date, _PLANNED)

        moved = date(2026, 12, 20)
        audit_service.update_audit(audit.id, audit_date=moved)
        plans = self._plans(agenda_service.get_items(today=_TODAY), audit.id)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].due_date, moved)

        audit_service.update_audit(audit.id, audit_date=None)
        self.assertEqual(self._plans(agenda_service.get_items(today=_TODAY), audit.id), [])

    def test_start_hides_plan_and_keeps_running_audit(self) -> None:
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        self.assertEqual(len(self._plans(agenda_service.get_items(today=_TODAY), audit.id)), 1)

        started = date(2026, 12, 12)
        expected_end = date(2026, 12, 15)
        audit_service.update_audit(
            audit.id,
            started_at=started,
            expected_end_date=expected_end,
        )
        items = agenda_service.get_items(today=_TODAY)
        self.assertEqual(self._plans(items, audit.id), [])
        running = self._running(items, audit.id)
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].type_label, "Audit")
        self.assertEqual(running[0].due_date, expected_end)

        attention = [
            item
            for item in get_attention_items(today=_TODAY)
            if item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == audit.id
        ]
        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0].date, expected_end)
        self.assertEqual(attention[0].type_label, "Audit")

    def test_completed_audit_is_hidden(self) -> None:
        audit = audit_service.create_audit(
            year=2026,
            audit_date=_PLANNED,
            finished_at=date(2026, 12, 18),
        )
        self.assertEqual(self._plans(agenda_service.get_items(today=_TODAY), audit.id), [])
        self.assertEqual(self._running(agenda_service.get_items(today=_TODAY), audit.id), [])
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == audit.id
                for item in get_attention_items(today=_TODAY)
            )
        )

    def test_filters_keep_foreign_term_rules(self) -> None:
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        task = task_service.create_task(title="Úkol vedle plánu", due_date=date(2026, 12, 9))
        done = task_service.create_task(title="Hotový úkol", due_date=date(2026, 12, 8))
        task_service.mark_completed(done.id)
        meeting = meeting_service.create_meeting(
            title="Událost vedle plánu",
            starts_at=datetime(2026, 12, 11, 9, 0),
            status=STATUS_PLANNED,
        )
        items = agenda_service.get_items(today=_TODAY)

        def shown(mode: str, types: set[str] | None = None):
            filtered = agenda_service.filter_items(
                items,
                type_filters={ITEM_TYPE_TASK, ITEM_TYPE_MEETING} if types is None else types,
                status_mode=mode,
            )
            return {item.item_type for item in filtered if int(item.source_id) == audit.id and item.item_type == ITEM_TYPE_AUDIT_PLAN}

        self.assertEqual(shown(STATUS_MODE_ACTIVE), {ITEM_TYPE_AUDIT_PLAN})
        self.assertEqual(shown(STATUS_MODE_ALL), {ITEM_TYPE_AUDIT_PLAN})
        for mode in (
            STATUS_MODE_DONE,
            STATUS_MODE_PLANNED,
            STATUS_MODE_CLOSED,
            STATUS_MODE_CANCELLED,
        ):
            self.assertEqual(shown(mode), set(), mode)

        only_tasks = agenda_service.filter_items(
            items,
            type_filters={ITEM_TYPE_TASK},
            status_mode=STATUS_MODE_ACTIVE,
        )
        self.assertTrue(any(item.item_type == ITEM_TYPE_TASK and item.source_id == task.id for item in only_tasks))
        self.assertTrue(self._plans(only_tasks, audit.id))
        self.assertFalse(any(item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id for item in only_tasks))

        only_meetings = agenda_service.filter_items(
            items,
            type_filters={ITEM_TYPE_MEETING},
            status_mode=STATUS_MODE_PLANNED,
        )
        self.assertFalse(self._plans(only_meetings, audit.id))
        self.assertTrue(
            any(item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id for item in only_meetings)
        )
        self.assertEqual(
            agenda_service.filter_items(items, type_filters=set(), status_mode=STATUS_MODE_ACTIVE),
            [],
        )

        planned_only = agenda_service.filter_items(
            items,
            type_filters={ITEM_TYPE_TASK, ITEM_TYPE_MEETING},
            status_mode=STATUS_MODE_PLANNED,
        )
        self.assertFalse(self._plans(planned_only, audit.id))
        self.assertTrue(
            any(item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id for item in planned_only)
        )

    def test_chronological_order_puts_plan_on_its_day(self) -> None:
        early = task_service.create_task(
            title="Dřívější úkol",
            due_date=date(2026, 12, 9),
            priority=PRIORITY_LOW,
        )
        same_day = task_service.create_task(
            title="Úkol ve stejný den",
            due_date=_PLANNED,
            priority=PRIORITY_LOW,
        )
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        late = task_service.create_task(
            title="Pozdější úkol",
            due_date=date(2026, 12, 11),
            priority=PRIORITY_LOW,
        )
        wanted = {
            (ITEM_TYPE_TASK, early.id),
            (ITEM_TYPE_TASK, same_day.id),
            (ITEM_TYPE_AUDIT_PLAN, audit.id),
            (ITEM_TYPE_TASK, late.id),
        }
        ordered = [
            (item.item_type, item.source_id)
            for item in agenda_service.get_items(today=_TODAY)
            if (item.item_type, item.source_id) in wanted
        ]
        self.assertEqual(
            ordered,
            [
                (ITEM_TYPE_TASK, early.id),
                (ITEM_TYPE_TASK, same_day.id),
                (ITEM_TYPE_AUDIT_PLAN, audit.id),
                (ITEM_TYPE_TASK, late.id),
            ],
        )

    def test_edit_opens_audit_and_reloads_agenda(self) -> None:
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        opened: list = []

        def on_open(item) -> None:
            opened.append(item)
            audit_service.update_audit(audit.id, audit_date=date(2026, 12, 20))

        page = AgendaPage(open_attention_callback=on_open)
        page.refresh()
        self._select(page, audit.id)
        page.table.doubleClicked.emit(page.table.currentIndex())
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].item_type, ITEM_TYPE_AUDIT)
        self.assertEqual(opened[0].source_id, audit.id)

        window = MagicMock()
        MainWindow._open_attention_item(window, opened[0])
        window._open_audit_by_id.assert_called_once_with(audit.id)

        reloaded = self._plans(agenda_service.get_items(today=_TODAY), audit.id)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0].due_date, date(2026, 12, 20))
        self._select(page, audit.id)
        self.assertEqual(page.table.item(page.table.currentRow(), COL_DUE).text(), "20. 12. 2026")
        page.close()

    def test_dashboard_shows_plan_and_keeps_running_audit(self) -> None:
        before = _record_counts()
        planned = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=_PLANNED,
        )
        running = audit_service.create_audit(
            workplace_name="Probíhá",
            year=2026,
            audit_date=date(2026, 11, 1),
            started_at=date(2026, 11, 2),
            expected_end_date=date(2026, 11, 5),
        )
        attention = get_attention_items(today=_TODAY)
        self.assertEqual(_record_counts()["tasks"], before["tasks"])
        self.assertEqual(_record_counts()["meetings"], before["meetings"])
        self.assertFalse(any(item.item_type == ITEM_TYPE_AUDIT_PLAN for item in attention))
        planned_attention = self._attention(attention, planned.id)
        self.assertEqual(len(planned_attention), 1)
        self.assertEqual(planned_attention[0].type_label, TYPE_LABEL_PLAN)
        self.assertEqual(planned_attention[0].title, "Audit Provoz Poříčí")
        self.assertEqual(planned_attention[0].date, _PLANNED)
        self.assertEqual(planned_attention[0].status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(planned_attention[0].source_label, SOURCE_LABEL_AUDIT)
        self.assertEqual(planned_attention[0].priority, "")
        self.assertTrue(planned_attention[0].open_metadata.get("planned"))
        running_attention = self._attention(attention, running.id)
        self.assertEqual(len(running_attention), 1)
        self.assertEqual(running_attention[0].date, date(2026, 11, 5))
        self.assertEqual(running_attention[0].type_label, "Audit")
        self.assertEqual(running_attention[0].title, "Audit – Probíhá")
        self.assertFalse(running_attention[0].open_metadata.get("planned"))

        agenda = agenda_service.get_items(today=_TODAY)
        self.assertEqual(len(self._plans(agenda, planned.id)), 1)
        self.assertEqual(self._plans(agenda, running.id), [])
        self.assertEqual(self._running(agenda, running.id)[0].due_date, date(2026, 11, 5))
        self.assertEqual(self._running(agenda, running.id)[0].type_label, "Audit")

        dots, events = build_calendar_day_data(
            today=_TODAY,
            now=datetime(2026, 12, 1, 12, 0),
        )
        self.assertIn("future", dots[_PLANNED])
        self.assertIn("Plán – Audit Provoz Poříčí", "\n".join(events[_PLANNED]))
        self.assertIn("overdue", dots[date(2026, 11, 5)])

    def test_missing_workplace_uses_file_number(self) -> None:
        audit = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        plan = self._plans(agenda_service.get_items(today=_TODAY), audit.id)[0]
        self.assertEqual(plan.title, f"Audit č. {audit.number}")
        self.assertEqual(plan.title, f"Audit č. {audit.id}/2026")

    def test_same_workplace_and_day_stay_separate(self) -> None:
        first = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=_PLANNED,
        )
        second = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=_PLANNED,
        )
        items = agenda_service.get_items(today=_TODAY)
        attention = get_attention_items(today=_TODAY)
        self.assertEqual(len(self._plans(items, first.id)), 1)
        self.assertEqual(len(self._plans(items, second.id)), 1)
        self.assertEqual(len(self._attention(attention, first.id)), 1)
        self.assertEqual(len(self._attention(attention, second.id)), 1)

    def test_calendar_dot_is_blue_today_and_red_when_past(self) -> None:
        today = date(2026, 11, 10)
        past = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=date(2026, 11, 9),
        )
        current = audit_service.create_audit(
            workplace_name="Dnešní provoz",
            year=2026,
            audit_date=today,
        )
        dots, events = build_calendar_day_data(
            today=today,
            now=datetime(2026, 11, 10, 8, 0),
        )
        self.assertIn("overdue", dots[date(2026, 11, 9)])
        self.assertIn("today", dots[today])
        self.assertIn("Plán – Audit Provoz Poříčí", "\n".join(events[date(2026, 11, 9)]))
        self.assertIn("Plán – Audit Dnešní provoz", "\n".join(events[today]))
        self.assertTrue(self._plans(agenda_service.get_items(today=today), past.id))
        self.assertTrue(self._plans(agenda_service.get_items(today=today), current.id))

    def test_overdue_plan_reminder_and_summary_count(self) -> None:
        today = date.today()
        past_day = today - timedelta(days=1)
        baseline = count_overdue_attention_items(today=today)
        audit = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=past_day,
        )
        self.assertEqual(count_overdue_attention_items(today=today), baseline)
        attention = self._attention(get_attention_items(today=today), audit.id)
        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0].date, past_day)

        reminders = [
            item
            for item in planned_audit_reminder_items(today=today)
            if int(item.source_id) == audit.id
        ]
        self.assertEqual(len(reminders), 1)
        self.assertEqual(
            reminders[0].title,
            "Nezahájený plánovaný audit – Audit Provoz Poříčí",
        )
        self.assertEqual(reminders[0].source_label, SOURCE_LABEL_AUDIT)
        self.assertNotIn(past_day.strftime("%d.%m.%Y"), reminders[0].title)

        widget = TodayWidget()
        widget.refresh(today=today)
        html = widget.content.text()
        sentence = "Nezahájený plánovaný audit – Audit Provoz Poříčí"
        self.assertEqual(html.count(sentence), 1)
        self.assertIn(f"<b>{past_day.strftime('%d.%m.%Y')}</b>", html)
        self.assertIn("🔴", html)
        self.assertIn(SOURCE_LABEL_AUDIT, html)
        widget.close()

        upcoming = UpcomingTasksWidget()
        row = self._upcoming_row(upcoming, audit.id)
        self.assertEqual(upcoming.table.item(row, UPCOMING_TYPE).text(), TYPE_LABEL_PLAN)
        self.assertEqual(upcoming.table.item(row, UPCOMING_TITLE).text(), "Audit Provoz Poříčí")
        self.assertIn("(Po termínu)", upcoming.table.item(row, UPCOMING_DUE).text())
        upcoming.close()

        task = task_service.create_task(
            title="Prošlý úkol vedle plánu",
            due_date=today - timedelta(days=9),
        )
        self.assertEqual(count_overdue_attention_items(today=today), baseline + 1)
        self.assertIsNotNone(task.id)

        current = audit_service.create_audit(
            workplace_name="Dnešek",
            year=2026,
            audit_date=today,
        )
        future = audit_service.create_audit(
            workplace_name="Budoucí",
            year=today.year,
            audit_date=today + timedelta(days=10),
        )
        reminder_ids = {int(item.source_id) for item in planned_audit_reminder_items(today=today)}
        self.assertIn(audit.id, reminder_ids)
        self.assertNotIn(current.id, reminder_ids)
        self.assertNotIn(future.id, reminder_ids)

    def test_plan_date_change_updates_views_and_drops_reminder(self) -> None:
        today = date(2026, 11, 10)
        audit = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=date(2026, 11, 9),
        )
        self.assertEqual(len(planned_audit_reminder_items(today=today)), 1)

        audit_service.update_audit(audit.id, audit_date=today)
        self.assertEqual(planned_audit_reminder_items(today=today), [])
        self.assertEqual(
            self._plans(agenda_service.get_items(today=today), audit.id)[0].due_date,
            today,
        )
        self.assertEqual(self._attention(get_attention_items(today=today), audit.id)[0].date, today)
        dots, _events = build_calendar_day_data(
            today=today,
            now=datetime(2026, 11, 10, 8, 0),
        )
        self.assertNotIn(date(2026, 11, 9), dots)
        self.assertIn("today", dots[today])

        audit_service.update_audit(audit.id, audit_date=None)
        self.assertEqual(self._plans(agenda_service.get_items(today=today), audit.id), [])
        self.assertEqual(self._attention(get_attention_items(today=today), audit.id), [])
        self.assertEqual(planned_audit_reminder_items(today=today), [])

    def test_start_and_finish_remove_plan_and_reminder(self) -> None:
        today = date(2026, 11, 10)
        audit = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=date(2026, 11, 9),
        )
        audit_service.update_audit(
            audit.id,
            started_at=date(2026, 11, 10),
            expected_end_date=date(2026, 11, 12),
        )
        items = agenda_service.get_items(today=today)
        self.assertEqual(self._plans(items, audit.id), [])
        self.assertEqual(planned_audit_reminder_items(today=today), [])
        running = self._running(items, audit.id)
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].type_label, "Audit")
        self.assertEqual(running[0].due_date, date(2026, 11, 12))
        attention = self._attention(get_attention_items(today=today), audit.id)
        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0].type_label, "Audit")
        self.assertFalse(attention[0].open_metadata.get("planned"))

        finished = audit_service.create_audit(
            workplace_name="Hotovo",
            year=2026,
            audit_date=date(2026, 11, 8),
            started_at=date(2026, 11, 8),
            finished_at=date(2026, 11, 9),
        )
        self.assertEqual(self._plans(agenda_service.get_items(today=today), finished.id), [])
        self.assertEqual(self._running(agenda_service.get_items(today=today), finished.id), [])
        self.assertEqual(self._attention(get_attention_items(today=today), finished.id), [])
        self.assertFalse(
            any(int(item.source_id) == finished.id for item in planned_audit_reminder_items(today=today))
        )

    def test_open_plan_from_upcoming_and_reminder(self) -> None:
        today = date(2026, 11, 10)
        audit = audit_service.create_audit(
            workplace_name="Provoz Poříčí",
            year=2026,
            audit_date=date(2026, 11, 9),
        )
        opened: list = []
        upcoming = UpcomingTasksWidget(open_attention_callback=opened.append)
        upcoming.table.selectRow(self._upcoming_row(upcoming, audit.id))
        upcoming._open_selected()
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].item_type, ITEM_TYPE_AUDIT)
        self.assertEqual(opened[0].source_id, audit.id)
        upcoming.close()

        reminder_widget = TodayWidget(open_attention_callback=opened.append)
        reminder_widget.refresh(today=today)
        reminder_widget._on_link_clicked(f"attention:audit:{audit.id}")
        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[1].source_id, audit.id)
        self.assertIn("Nezahájený plánovaný audit", opened[1].title)
        reminder_widget.close()

        window = MagicMock()
        MainWindow._open_attention_item(window, opened[0])
        MainWindow._open_attention_item(window, opened[1])
        self.assertEqual(window._open_audit_by_id.call_count, 2)
        window._open_audit_by_id.assert_called_with(audit.id)

    def _attention(self, items, audit_id: int):
        return [
            item
            for item in items
            if item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == int(audit_id)
        ]

    def _upcoming_row(self, widget: UpcomingTasksWidget, audit_id: int) -> int:
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, UPCOMING_TYPE).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and int(payload.source_id) == int(audit_id)
                and (payload.open_metadata or {}).get("planned")
            ):
                return row
        self.fail(f"Plán auditu {audit_id} v Nadcházejících není")

    def _select(self, page: AgendaPage, audit_id: int):
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and payload.item_type == ITEM_TYPE_AUDIT_PLAN
                and int(payload.source_id) == int(audit_id)
            ):
                page.table.selectRow(row)
                return payload
        self.fail(f"Plán auditu {audit_id} v tabulce není")


if __name__ == "__main__":
    unittest.main()
