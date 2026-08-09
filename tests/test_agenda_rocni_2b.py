"""AGENDA-ROCNI-2b: UI Ročního plánu v Agendě."""

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

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import (
        SOURCE_MODULE_YEARLY_PLAN,
        STATUS_CANCELLED,
        STATUS_PLANNED,
        STATUS_VIA_MEETING,
        STATUS_VIA_TASK,
        TAB_YEARLY_PLAN,
        status_label,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        YearlyPlanValidationError,
        yearly_plan_service,
    )
    from moduly.rocni_plan.ui.yearly_plan_item_dialog import YearlyPlanItemDialog
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaRocni2bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for year in (2026, 2027):
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != STATUS_CANCELLED:
                    yearly_plan_service.cancel(item.id)

    def test_agenda_has_three_tabs(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 3)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(2), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.yearly_plan_tab, YearlyPlanTab)
        page.close()

    def test_create_edit_move_cancel(self) -> None:
        created = yearly_plan_service.create(
            year=2026,
            month=9,
            title="Aktualizovat dokumentaci",
            note="Směrnice",
        )
        self.assertEqual(created.status, STATUS_PLANNED)

        dialog = YearlyPlanItemDialog(item=created)
        self.assertEqual(dialog.title_edit.text(), "Aktualizovat dokumentaci")
        dialog.title_edit.setText("Aktualizovat dokumentaci – upraveno")
        self.assertTrue(dialog._editor._run_save())
        reloaded = yearly_plan_service.get_by_id(created.id)
        self.assertEqual(reloaded.title, "Aktualizovat dokumentaci – upraveno")
        dialog._editor._closing = True
        dialog.close()

        moved = yearly_plan_service.move_to_month(created.id, to_year=2026, to_month=11)
        self.assertEqual(moved.id, created.id)
        self.assertEqual(moved.month, 11)
        history = yearly_plan_service.get_move_history(created.id)
        self.assertEqual(len(history), 1)

        cancelled = yearly_plan_service.cancel(created.id)
        self.assertEqual(cancelled.status, STATUS_CANCELLED)
        self.assertEqual(status_label(cancelled.status), "Zrušeno")

        tab = YearlyPlanTab()
        tab.set_year_month(2026, 11)
        visible_ids = {
            tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
        }
        self.assertIn(created.id, visible_ids)
        tab.close()

    def test_create_task_link(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=5,
            title="Připravit školení",
        )
        task = task_service.create_task(
            title=item.title,
            due_date=date(2026, 5, 31),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=item.id,
            requires_verification=False,
        )
        linked = yearly_plan_service.link_task(item.id, task.id)
        self.assertEqual(linked.status, STATUS_VIA_TASK)
        self.assertEqual(linked.task_id, task.id)
        self.assertIsNone(linked.meeting_id)
        self.assertFalse(task.requires_verification)
        self.assertEqual(task.source_module, SOURCE_MODULE_YEARLY_PLAN)
        self.assertEqual(task.source_record_id, item.id)

        tab = YearlyPlanTab()
        tab.set_year_month(2026, 5)
        for row in range(tab.table.rowCount()):
            if tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == item.id:
                tab.table.selectRow(row)
                break
        tab._refresh_action_buttons()
        self.assertFalse(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        tab.close()

    def test_create_meeting_link(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=6,
            title="Kontrola skladu",
        )
        starts = datetime.now().replace(microsecond=0) + timedelta(days=7)
        meeting = meeting_service.create_meeting(
            title=item.title,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
        )
        linked = yearly_plan_service.link_meeting(item.id, meeting.id)
        self.assertEqual(linked.status, STATUS_VIA_MEETING)
        self.assertEqual(linked.meeting_id, meeting.id)
        self.assertIsNone(linked.task_id)

        tab = YearlyPlanTab()
        tab.set_year_month(2026, 6)
        for row in range(tab.table.rowCount()):
            if tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == item.id:
                tab.table.selectRow(row)
                break
        tab._refresh_action_buttons()
        self.assertFalse(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        tab.close()

    def test_second_link_rejected(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=7,
            title="Jedna vazba",
        )
        task = task_service.create_task(
            title="Úkol",
            due_date=date(2026, 7, 15),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=item.id,
            requires_verification=False,
        )
        yearly_plan_service.link_task(item.id, task.id)
        meeting = meeting_service.create_meeting(
            title="Událost",
            starts_at=datetime.now() + timedelta(days=3),
            ends_at=datetime.now() + timedelta(days=3, hours=1),
        )
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.link_meeting(item.id, meeting.id)

    def test_move_history_in_dialog(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=1,
            title="Historie UI",
        )
        yearly_plan_service.move_to_month(item.id, to_year=2026, to_month=3)
        yearly_plan_service.move_to_month(item.id, to_year=2027, to_month=1)
        dialog = YearlyPlanItemDialog(item=yearly_plan_service.get_by_id(item.id))
        self.assertEqual(dialog.history_table.rowCount(), 2)
        self.assertIn("leden 2026", dialog.history_table.item(0, 0).text())
        self.assertIn("březen 2026", dialog.history_table.item(0, 1).text())
        dialog._editor._closing = True
        dialog.close()


if __name__ == "__main__":
    unittest.main()
