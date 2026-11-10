"""Plánované audity ve společném přehledu Agendy, bez kopie do databáze."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime
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
    from core.dashboard.attention_service import get_attention_items
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
        self.assertEqual(plan.title, f"Audit č. {first.number}")
        self.assertEqual(plan.title, "Audit č. {0}/2026".format(first.id))
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

    def test_dashboard_ignores_plan_and_keeps_running_audit(self) -> None:
        planned = audit_service.create_audit(year=2026, audit_date=_PLANNED)
        running = audit_service.create_audit(
            workplace_name="Probíhá",
            year=2026,
            audit_date=date(2026, 11, 1),
            started_at=date(2026, 11, 2),
            expected_end_date=date(2026, 11, 5),
        )
        attention = get_attention_items(today=_TODAY)
        self.assertFalse(any(item.item_type == ITEM_TYPE_AUDIT_PLAN for item in attention))
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == planned.id
                for item in attention
            )
        )
        running_attention = [
            item
            for item in attention
            if item.item_type == ITEM_TYPE_AUDIT and int(item.source_id) == running.id
        ]
        self.assertEqual(len(running_attention), 1)
        self.assertEqual(running_attention[0].date, date(2026, 11, 5))
        self.assertEqual(running_attention[0].type_label, "Audit")

        agenda = agenda_service.get_items(today=_TODAY)
        self.assertEqual(len(self._plans(agenda, planned.id)), 1)
        self.assertEqual(self._plans(agenda, running.id), [])
        self.assertEqual(self._running(agenda, running.id)[0].due_date, date(2026, 11, 5))
        self.assertEqual(self._running(agenda, running.id)[0].type_label, "Audit")

        from core.dashboard.widget_calendar_placeholder import build_calendar_day_data

        dots, events = build_calendar_day_data(
            today=_TODAY,
            now=datetime(2026, 12, 1, 12, 0),
        )
        self.assertNotIn(_PLANNED, dots)
        tooltip = "\n".join(block for blocks in events.values() for block in blocks)
        self.assertNotIn(f"Audit č. {planned.number}", tooltip)
        self.assertIn(date(2026, 11, 5), dots)

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
