"""AGENDA-TASK-HISTORY-2: ukončené úkoly ve filtrech Splněné a Vše."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="agenda-task-history-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import ENTITY_PROVERKY
    from moduly.agenda.constants import (
        COL_TITLE,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        STATUS_MODE_ACTIVE,
        STATUS_MODE_ALL,
        STATUS_MODE_CANCELLED,
        STATUS_MODE_DONE,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import STATUS_CANCELLED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.constants import (
        TASK_STATUS_ACTIVE,
        TASK_STATUS_CANCELED,
        TASK_STATUS_CLOSED,
        TASK_STATUS_WAITING_CHECK,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _task_ids(page: AgendaPage) -> set[int]:
    ids: set[int] = set()
    for row in range(page.table.rowCount()):
        payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
        if payload is not None and payload.item_type == ITEM_TYPE_TASK:
            ids.add(int(payload.source_id))
    return ids


def _select_task_row(page: AgendaPage, task_id: int) -> None:
    for row in range(page.table.rowCount()):
        payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
        if (
            payload is not None
            and payload.item_type == ITEM_TYPE_TASK
            and int(payload.source_id) == int(task_id)
        ):
            page.table.selectRow(row)
            page.table.setCurrentCell(row, COL_TITLE)
            return
    raise AssertionError(f"Úkol {task_id} není v tabulce Agendy")


class AgendaTaskHistory2TestCase(unittest.TestCase):
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
            if task.computed_status != TASK_STATUS_CANCELED:
                task_service.cancel_task(task.id)

    def _page_tasks_only(self, status_mode: str) -> AgendaPage:
        page = AgendaPage()
        page.type_checks[ITEM_TYPE_MEETING].setChecked(False)
        page.status_filter.setCurrentText(status_mode)
        page.refresh()
        return page

    def test_a_to_e_manual_task_filters_after_completion(self) -> None:
        due = date.today() + timedelta(days=5)
        task = task_service.create_task(
            title="Ruční úkol historie 2",
            due_date=due,
            note="Poznámka před splněním",
            source_module="manual",
        )
        task_id = int(task.id)

        page = self._page_tasks_only(STATUS_MODE_ACTIVE)
        self.assertIn(task_id, _task_ids(page))

        self.assertTrue(task_service.mark_completed(task_id))
        reloaded = task_service.get_task_by_id(task_id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(int(reloaded.id), task_id)
        self.assertTrue(reloaded.completed)
        self.assertEqual(reloaded.status, TASK_STATUS_CLOSED)
        self.assertEqual(reloaded.computed_status, TASK_STATUS_CLOSED)
        self.assertEqual(reloaded.completed_date, date.today())
        self.assertEqual(reloaded.source_module, "manual")

        page.status_filter.setCurrentText(STATUS_MODE_ACTIVE)
        page.refresh()
        self.assertNotIn(task_id, _task_ids(page))

        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.refresh()
        self.assertIn(task_id, _task_ids(page))

        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        self.assertIn(task_id, _task_ids(page))

    def test_c_to_e_and_g_active_and_completed_together(self) -> None:
        active = task_service.create_task(
            title="Aktivní ruční",
            due_date=date.today() + timedelta(days=3),
            source_module="manual",
        )
        done = task_service.create_task(
            title="Ukončený ruční",
            due_date=date.today() + timedelta(days=2),
            source_module="manual",
        )
        task_service.mark_completed(done.id)

        page = self._page_tasks_only(STATUS_MODE_ACTIVE)
        ids = _task_ids(page)
        self.assertIn(active.id, ids)
        self.assertNotIn(done.id, ids)

        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.refresh()
        ids = _task_ids(page)
        self.assertIn(done.id, ids)
        self.assertNotIn(active.id, ids)

        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        ids = _task_ids(page)
        self.assertIn(active.id, ids)
        self.assertIn(done.id, ids)

    def test_f_completed_task_opens_with_historical_data(self) -> None:
        due = date.today() + timedelta(days=7)
        task = task_service.create_task(
            title="Historický ruční úkol",
            due_date=due,
            note="Doklad textově",
            source_module="manual",
        )
        task_service.mark_completed(task.id)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertIsNotNone(reloaded)

        page = self._page_tasks_only(STATUS_MODE_DONE)
        _select_task_row(page, task.id)
        selected = page.table.selected_item()
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.source_id, task.id)
        self.assertEqual(selected.status, TASK_STATUS_CLOSED)
        self.assertEqual(selected.due_date, due)

        dialog = TaskDialog(page, task=reloaded)
        self.assertEqual(dialog.title_edit.toPlainText(), "Historický ruční úkol")
        self.assertTrue(dialog.completed_checkbox.isChecked())
        self.assertEqual(dialog.completed_date_edit.get_date(), date.today())
        self.assertEqual(dialog.due_date_edit.get_date_iso(), due.isoformat())
        self.assertEqual(dialog.status_label.text(), TASK_STATUS_CLOSED)
        self.assertEqual(dialog.note_edit.toPlainText(), "Doklad textově")
        dialog.close()

    def test_h_waiting_check_stays_in_active(self) -> None:
        waiting = task_service.create_task(
            title="Čeká na kontrolu",
            due_date=date.today() + timedelta(days=4),
            completed=True,
            completed_date=date.today(),
            requires_verification=True,
            check_due_date=date.today() + timedelta(days=15),
            source_module="manual",
        )
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)

        page = self._page_tasks_only(STATUS_MODE_ACTIVE)
        self.assertIn(waiting.id, _task_ids(page))

        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.refresh()
        self.assertNotIn(waiting.id, _task_ids(page))

        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        self.assertIn(waiting.id, _task_ids(page))

    def test_i_canceled_tasks_remain_hidden(self) -> None:
        task = task_service.create_task(
            title="Zrušený ruční",
            due_date=date.today() + timedelta(days=1),
            source_module="manual",
        )
        task_service.cancel_task(task.id)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.computed_status, TASK_STATUS_CANCELED)
        self.assertFalse(reloaded.completed)

        raw_ids = {
            item.source_id
            for item in agenda_service.get_items()
            if item.item_type == ITEM_TYPE_TASK
        }
        self.assertNotIn(task.id, raw_ids)

        for mode in (
            STATUS_MODE_ACTIVE,
            STATUS_MODE_DONE,
            STATUS_MODE_CANCELLED,
            STATUS_MODE_ALL,
        ):
            page = self._page_tasks_only(mode)
            self.assertNotIn(task.id, _task_ids(page), msg=mode)

    def test_j_other_module_task_lifecycle_unchanged(self) -> None:
        due = date.today() + timedelta(days=9)
        task = task_service.create_task(
            title="Opatření z prověrky",
            due_date=due,
            source_module=ENTITY_PROVERKY,
            source_record_id=42,
            note="Zjištění z prověrky",
        )
        before = task_service.get_task_by_id(task.id)
        self.assertIsNotNone(before)
        assert before is not None
        snapshot = (
            before.title,
            before.source_module,
            before.source_record_id,
            before.task_type,
            before.due_date,
            before.note,
            before.requires_verification,
            before.computed_status,
        )
        self.assertEqual(before.computed_status, TASK_STATUS_ACTIVE)
        self.assertTrue(before.requires_verification)

        page = self._page_tasks_only(STATUS_MODE_ACTIVE)
        self.assertIn(task.id, _task_ids(page))

        task_service.mark_completed(task.id)
        after = task_service.get_task_by_id(task.id)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after.id, task.id)
        self.assertEqual(after.title, snapshot[0])
        self.assertEqual(after.source_module, ENTITY_PROVERKY)
        self.assertEqual(after.source_record_id, 42)
        self.assertEqual(after.task_type, snapshot[3])
        self.assertEqual(after.due_date, due)
        self.assertEqual(after.note, snapshot[5])
        self.assertEqual(after.requires_verification, True)
        self.assertEqual(after.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertTrue(after.completed)
        self.assertEqual(after.completed_date, date.today())

        page.status_filter.setCurrentText(STATUS_MODE_ACTIVE)
        page.refresh()
        self.assertIn(task.id, _task_ids(page))
        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.refresh()
        self.assertNotIn(task.id, _task_ids(page))


if __name__ == "__main__":
    unittest.main()
