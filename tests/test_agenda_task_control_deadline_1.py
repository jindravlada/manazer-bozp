"""AGENDA-TASK-CONTROL-DEADLINE-1: termín čekající kontroly v Agendě a kalendáři."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="agenda-task-control-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.widget_calendar_placeholder import build_calendar_day_data
    from core.shared.constants import ENTITY_PROVERKY
    from moduly.agenda.constants import (
        COL_DUE,
        COL_TITLE,
        COL_TYPE,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        ROW_STATE_OVERDUE,
        ROW_STATE_WAITING,
        TYPE_LABEL_TASK,
        TYPE_LABEL_TASK_CONTROL,
    )
    from moduly.agenda.sluzby import agenda_service as agenda_service_module
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.constants import TASK_STATUS_WAITING_CHECK, TASK_TYPE_LABELS
    from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date
    from moduly.ukoly.sluzby.task_service import task_service


_DUE = date(2026, 8, 28)
_CHECK_DUE = date(2026, 9, 11)
_TODAY_BETWEEN = date(2026, 8, 29)


def _task_items(items=None):
    items = items if items is not None else agenda_service.get_items()
    return [item for item in items if item.item_type == ITEM_TYPE_TASK]


def _item_for_task(task_id: int, items=None):
    matches = [item for item in _task_items(items) if item.source_id == task_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(f"Očekáván 1 řádek úkolu {task_id}, je {len(matches)}")
    return matches[0]


def _calendar_data(*, today: date):
    return build_calendar_day_data(
        today=today,
        now=datetime.combine(today, datetime.min.time().replace(hour=12)),
    )


class AgendaTaskControlDeadline1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") == STATUS_CANCELLED:
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
            if task.computed_status != "Zrušeno":
                task_service.cancel_task(task.id)

    def _waiting_check_task(
        self,
        *,
        title: str = "Opatření k ověření",
        due_date: date = _DUE,
        completed_date: date = date(2026, 8, 27),
        check_due_date: date | None = _CHECK_DUE,
        source_module: str = "manual",
        source_record_id: int | None = None,
        priority: str = "Vysoká",
    ):
        return task_service.create_task(
            title=title,
            due_date=due_date,
            completed=True,
            completed_date=completed_date,
            requires_verification=True,
            check_due_date=check_due_date,
            source_module=source_module,
            source_record_id=source_record_id,
            priority=priority,
        )

    def test_uses_shared_task_urgency_due_date(self) -> None:
        self.assertIs(
            agenda_service_module.task_urgency_due_date,
            task_urgency_due_date,
        )

    def test_active_task_keeps_due_date_and_type_task(self) -> None:
        task = task_service.create_task(
            title="Aktivní opatření",
            due_date=_DUE,
            requires_verification=False,
            priority="Normální",
        )
        item = _item_for_task(task.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_id, task.id)
        self.assertEqual(item.type_label, TYPE_LABEL_TASK)
        self.assertEqual(item.type_label, "Úkol")
        self.assertEqual(item.due_date, _DUE)
        self.assertEqual(item.due_date, task_urgency_due_date(task))
        self.assertEqual(item.title, "Aktivní opatření")
        self.assertEqual(item.priority, "Normální")

    def test_completed_without_verification_is_hidden(self) -> None:
        task = task_service.create_task(
            title="Splněno bez kontroly",
            due_date=_DUE,
            completed=True,
            completed_date=date(2026, 8, 27),
            requires_verification=False,
        )
        self.assertEqual(task.computed_status, "Ukončeno")
        self.assertIsNone(_item_for_task(task.id))
        dots, events = _calendar_data(today=_TODAY_BETWEEN)
        self.assertNotIn(_DUE, dots)
        self.assertNotIn(_DUE, events)

    def test_waiting_check_uses_check_due_date_and_control_type(self) -> None:
        task = self._waiting_check_task()
        self.assertEqual(task.computed_status, TASK_STATUS_WAITING_CHECK)
        item = _item_for_task(task.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_id, task.id)
        self.assertEqual(item.type_label, TYPE_LABEL_TASK_CONTROL)
        self.assertEqual(item.type_label, "Kontrola úkolu")
        self.assertNotEqual(item.type_label, TASK_TYPE_LABELS["control"])
        self.assertEqual(item.due_date, _CHECK_DUE)
        self.assertNotEqual(item.due_date, task.due_date)
        self.assertEqual(item.due_date, task_urgency_due_date(task))
        self.assertEqual(item.title, "Opatření k ověření")
        self.assertEqual(item.priority, "Vysoká")

    def test_concrete_dates_are_on_check_not_due(self) -> None:
        task = self._waiting_check_task()
        items = agenda_service.get_items(
            today=_TODAY_BETWEEN,
            now=datetime(2026, 8, 29, 12, 0),
        )
        item = _item_for_task(task.id, items)
        self.assertEqual(item.due_date, date(2026, 9, 11))
        self.assertNotEqual(item.due_date, date(2026, 8, 28))
        on_due = [
            row
            for row in items
            if row.item_type == ITEM_TYPE_TASK
            and row.source_id == task.id
            and row.due_date == date(2026, 8, 28)
        ]
        self.assertEqual(on_due, [])

    def test_checked_task_disappears(self) -> None:
        task = self._waiting_check_task(title="Po kontrole zmizí")
        self.assertIsNotNone(_item_for_task(task.id))
        task_service.update_task(
            task.id,
            title=task.title,
            due_date=task.due_date,
            completed=True,
            completed_date=task.completed_date,
            requires_verification=True,
            check_due_date=task.check_due_date,
            checked_date=date(2026, 9, 10),
        )
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.computed_status, "Ukončeno")
        self.assertIsNone(_item_for_task(reloaded.id))
        dots, events = _calendar_data(today=date(2026, 9, 10))
        joined = "\n".join(
            block for blocks in events.values() for block in blocks
        )
        self.assertNotIn("Po kontrole zmizí", joined)
        self.assertNotIn(_DUE, dots)
        self.assertNotIn(_CHECK_DUE, dots)

    def test_canceled_task_is_hidden(self) -> None:
        task = task_service.create_task(
            title="Zrušené opatření",
            due_date=_DUE,
        )
        task_service.cancel_task(task.id)
        self.assertIsNone(_item_for_task(task.id))
        dots, events = _calendar_data(today=_TODAY_BETWEEN)
        self.assertNotIn(_DUE, dots)
        self.assertNotIn(_DUE, events)

    def test_missing_check_due_date_does_not_fall_back_to_due_date(self) -> None:
        task = self._waiting_check_task(
            title="Bez termínu kontroly",
            check_due_date=_CHECK_DUE,
        )
        task.check_due_date = None
        task_service.repository.update(task)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertIsNone(reloaded.check_due_date)
        self.assertIsNone(task_urgency_due_date(reloaded))
        item = _item_for_task(reloaded.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.type_label, "Kontrola úkolu")
        self.assertIsNone(item.due_date)
        self.assertNotEqual(item.due_date, reloaded.due_date)
        dots, events = _calendar_data(today=_TODAY_BETWEEN)
        self.assertNotIn(_DUE, dots)
        self.assertNotIn(_DUE, events)
        self.assertNotIn(_CHECK_DUE, dots)

        page = AgendaPage()
        page.refresh()
        found_row = None
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == reloaded.id:
                found_row = row
                break
        self.assertIsNotNone(found_row)
        self.assertEqual(page.table.item(found_row, COL_DUE).text(), "—")

    def test_waiting_check_has_single_row(self) -> None:
        task = self._waiting_check_task(title="Jediný řádek")
        matches = [
            item
            for item in agenda_service.get_items()
            if item.source_id == task.id and item.item_type == ITEM_TYPE_TASK
        ]
        self.assertEqual(len(matches), 1)

    def test_manual_and_inspection_sources_share_deadline_logic(self) -> None:
        manual = self._waiting_check_task(title="Ruční kontrola", source_module="manual")
        from_inspection = self._waiting_check_task(
            title="Kontrola z prověrky",
            source_module=ENTITY_PROVERKY,
            source_record_id=42,
        )
        manual_item = _item_for_task(manual.id)
        inspection_item = _item_for_task(from_inspection.id)
        self.assertEqual(manual_item.due_date, _CHECK_DUE)
        self.assertEqual(inspection_item.due_date, _CHECK_DUE)
        self.assertEqual(manual_item.type_label, "Kontrola úkolu")
        self.assertEqual(inspection_item.type_label, "Kontrola úkolu")
        self.assertEqual(manual_item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(inspection_item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(manual_item.source, "Ručně")
        self.assertEqual(inspection_item.source, "Prověrka")

    def test_past_due_date_future_check_is_not_overdue(self) -> None:
        task = self._waiting_check_task()
        items = agenda_service.get_items(
            today=_TODAY_BETWEEN,
            now=datetime(2026, 8, 29, 12, 0),
        )
        item = _item_for_task(task.id, items)
        self.assertEqual(item.row_state, ROW_STATE_WAITING)
        self.assertNotEqual(item.row_state, ROW_STATE_OVERDUE)

    def test_past_check_due_date_is_overdue(self) -> None:
        task = self._waiting_check_task()
        items = agenda_service.get_items(
            today=date(2026, 9, 12),
            now=datetime(2026, 9, 12, 12, 0),
        )
        item = _item_for_task(task.id, items)
        self.assertEqual(item.row_state, ROW_STATE_OVERDUE)

    def test_sorting_uses_check_due_date(self) -> None:
        waiting = self._waiting_check_task(title="Kontrola později")
        earlier = task_service.create_task(
            title="Aktivní dříve",
            due_date=date(2026, 9, 5),
            requires_verification=False,
        )
        items = agenda_service.get_items()
        task_rows = [
            item
            for item in items
            if item.source_id in {waiting.id, earlier.id} and item.item_type == ITEM_TYPE_TASK
        ]
        self.assertEqual([item.source_id for item in task_rows], [earlier.id, waiting.id])
        self.assertEqual(task_rows[0].due_date, date(2026, 9, 5))
        self.assertEqual(task_rows[1].due_date, _CHECK_DUE)

    def test_agenda_table_shows_control_label_and_check_date(self) -> None:
        task = self._waiting_check_task(title="Viditelná kontrola")
        page = AgendaPage()
        page.refresh()
        found = None
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == task.id:
                found = row
                break
        self.assertIsNotNone(found)
        self.assertEqual(page.table.item(found, COL_TYPE).text(), "Kontrola úkolu")
        due_text = page.table.item(found, COL_DUE).text()
        self.assertIn("11. 9. 2026", due_text)
        self.assertNotIn("28. 8. 2026", due_text)

    def test_opening_keeps_task_identity_and_opens_original_task(self) -> None:
        task = self._waiting_check_task(title="Otevřít původní úkol")
        page = AgendaPage()
        page.refresh()
        opened: list[int] = []

        def _open_task(task_id: int) -> None:
            opened.append(task_id)

        page._open_task = _open_task  # type: ignore[method-assign]
        target_row = next(
            row
            for row in range(page.table.rowCount())
            if page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole).source_id
            == task.id
        )
        payload = page.table.item(target_row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(payload.item_type, ITEM_TYPE_TASK)
        self.assertEqual(payload.source_id, task.id)
        self.assertEqual(payload.type_label, "Kontrola úkolu")
        page.table.selectRow(target_row)
        page.edit_selected()
        self.assertEqual(opened, [task.id])

    def test_calendar_marker_moves_to_check_due_date(self) -> None:
        task = self._waiting_check_task(title="Značka na kontrole")
        dots, events = _calendar_data(today=_TODAY_BETWEEN)
        self.assertNotIn(_DUE, dots)
        self.assertNotIn(_DUE, events)
        self.assertIn(_CHECK_DUE, dots)
        self.assertIn("waiting", dots[_CHECK_DUE])
        self.assertNotIn("overdue", dots[_CHECK_DUE])
        joined = "\n".join(events[_CHECK_DUE])
        self.assertIn("Značka na kontrole", joined)
        self.assertIn("Kontrola úkolu", joined)
        self.assertNotIn("Kontrolní úkon", joined)
        matches = [
            block
            for block in events[_CHECK_DUE]
            if "Značka na kontrole" in block
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(_item_for_task(task.id).due_date, _CHECK_DUE)

    def test_other_agenda_item_types_keep_own_dates(self) -> None:
        meeting_at = datetime(2026, 8, 28, 9, 0)
        meeting = meeting_service.create_meeting(
            title="Událost termín beze změny",
            starts_at=meeting_at,
            status=STATUS_PLANNED,
        )
        self._waiting_check_task(title="Kontrola vedle události")
        items = agenda_service.get_items(
            today=_TODAY_BETWEEN,
            now=datetime(2026, 8, 29, 12, 0),
        )
        by_key = {(item.item_type, item.source_id): item for item in items}
        meeting_item = by_key[(ITEM_TYPE_MEETING, meeting.id)]
        self.assertEqual(meeting_item.due_date, date(2026, 8, 28))
        self.assertEqual(meeting_item.event_at, meeting_at)
        self.assertEqual(meeting_item.type_label, "Událost")

        dots, events = _calendar_data(today=_TODAY_BETWEEN)
        self.assertIn(date(2026, 8, 28), dots)
        meeting_text = "\n".join(events[date(2026, 8, 28)])
        self.assertIn("Událost termín beze změny", meeting_text)
        self.assertNotIn("Kontrola vedle události", meeting_text)
        self.assertIn("Kontrola vedle události", "\n".join(events[_CHECK_DUE]))

    def test_load_does_not_write_missing_check_due_date(self) -> None:
        task = self._waiting_check_task(check_due_date=_CHECK_DUE)
        task.check_due_date = None
        task_service.repository.update(task)
        agenda_service.get_items(today=_TODAY_BETWEEN)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertIsNone(reloaded.check_due_date)
        self.assertEqual(reloaded.due_date, _DUE)
        self.assertEqual(reloaded.computed_status, TASK_STATUS_WAITING_CHECK)


if __name__ == "__main__":
    unittest.main()
