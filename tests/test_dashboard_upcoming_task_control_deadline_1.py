"""DASHBOARD-UPCOMING-TASK-CONTROL-DEADLINE-1: termín čekající kontroly v Nadcházejících."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="dashboard-upcoming-task-control-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_AUDIT,
        ITEM_TYPE_INSPECTION,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        TYPE_LABEL_TASK_CONTROL,
        TYPE_LABELS,
        AttentionItem,
        attention_item_identity,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import (
        count_overdue_attention_items,
        get_attention_items,
    )
    from core.dashboard.widget_summary import SummaryWidget
    from core.dashboard.widget_today import (
        STATUS_WAITING_CHECK,
        TodayWidget,
        classify_burning_tasks,
        task_should_appear_in_reminders,
        task_urgency_due_date,
    )
    from core.dashboard.widget_upcoming_tasks import (
        COL_DUE,
        COL_TYPE,
        UpcomingTasksWidget,
    )
    from core.shared.constants import ENTITY_PROVERKY
    from core.windows.main_window import MainWindow
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.constants import TASK_STATUS_WAITING_CHECK
    from moduly.ukoly.sluzby.task_deadline import (
        task_urgency_due_date as shared_task_urgency_due_date,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service


_COLOR_OVERDUE = QColor("#d93025")
_COLOR_APPROACHING = QColor("#f0a000")
_COLOR_FUTURE = QColor("#1a73e8")


def _task_items(items=None):
    items = items if items is not None else get_attention_items()
    return [item for item in items if item.item_type == ITEM_TYPE_TASK]


def _item_for_task(task_id: int, items=None):
    matches = [item for item in _task_items(items) if item.source_id == task_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(f"Očekáván 1 řádek úkolu {task_id}, je {len(matches)}")
    return matches[0]


class DashboardUpcomingTaskControlDeadline1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation

        with get_session() as session:
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        today = date.today()
        for year, month in ((today.year, today.month), (2026, 8), (2026, 9)):
            if not yearly_plan_service.is_month_processed(year, month):
                yearly_plan_service.mark_month_processed(year, month)

    def _waiting_check_task(
        self,
        *,
        title: str = "Opatření k ověření",
        due_date: date = date(2026, 8, 28),
        completed_date: date = date(2026, 8, 27),
        check_due_date: date | None = date(2026, 9, 11),
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

    def test_shared_helper_is_same_as_reminders_export(self) -> None:
        self.assertIs(task_urgency_due_date, shared_task_urgency_due_date)
        self.assertEqual(STATUS_WAITING_CHECK, TASK_STATUS_WAITING_CHECK)

    def test_active_task_keeps_due_date_and_type_task(self) -> None:
        due = date(2026, 8, 28)
        task = task_service.create_task(
            title="Aktivní opatření",
            due_date=due,
            requires_verification=False,
            priority="Normální",
        )
        item = _item_for_task(task.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_id, task.id)
        self.assertEqual(item.type_label, "Úkol")
        self.assertIsNone(item.type_label_override)
        self.assertEqual(item.date, due)
        self.assertEqual(item.title, "Aktivní opatření")
        self.assertEqual(item.priority, "Normální")

    def test_completed_without_verification_is_hidden(self) -> None:
        task = task_service.create_task(
            title="Splněno bez kontroly",
            due_date=date(2026, 8, 28),
            completed=True,
            completed_date=date(2026, 8, 27),
            requires_verification=False,
        )
        self.assertEqual(task.computed_status, "Ukončeno")
        self.assertIsNone(_item_for_task(task.id))

    def test_waiting_check_uses_check_due_date_and_control_type(self) -> None:
        task = self._waiting_check_task()
        self.assertEqual(task.computed_status, TASK_STATUS_WAITING_CHECK)
        item = _item_for_task(task.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_id, task.id)
        self.assertEqual(item.open_metadata, {"source_type": ITEM_TYPE_TASK, "source_id": task.id})
        self.assertEqual(item.type_label, TYPE_LABEL_TASK_CONTROL)
        self.assertEqual(item.type_label, "Kontrola úkolu")
        self.assertEqual(item.date, date(2026, 9, 11))
        self.assertNotEqual(item.date, task.due_date)
        self.assertEqual(item.title, "Opatření k ověření")
        self.assertEqual(item.priority, "Vysoká")

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
        self.assertIsNone(_item_for_task(task.id))

    def test_canceled_task_is_hidden(self) -> None:
        task = task_service.create_task(
            title="Zrušené opatření",
            due_date=date(2026, 8, 28),
        )
        task_service.cancel_task(task.id)
        self.assertIsNone(_item_for_task(task.id))

    def test_waiting_check_has_single_row(self) -> None:
        task = self._waiting_check_task(title="Jediný řádek")
        matches = [
            item
            for item in get_attention_items()
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
        self.assertEqual(manual_item.date, date(2026, 9, 11))
        self.assertEqual(inspection_item.date, date(2026, 9, 11))
        self.assertEqual(manual_item.type_label, "Kontrola úkolu")
        self.assertEqual(inspection_item.type_label, "Kontrola úkolu")
        self.assertEqual(manual_item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(inspection_item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(manual_item.subtitle, "Ručně")
        self.assertEqual(inspection_item.subtitle, "Prověrka")

    def test_missing_check_due_date_does_not_fall_back_to_due_date(self) -> None:
        task = self._waiting_check_task(
            title="Bez termínu kontroly",
            check_due_date=date(2026, 9, 11),
        )
        task.check_due_date = None
        task_service.repository.update(task)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertIsNone(reloaded.check_due_date)
        item = _item_for_task(reloaded.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.type_label, "Kontrola úkolu")
        self.assertIsNone(item.date)
        self.assertNotEqual(item.date, reloaded.due_date)

    def test_past_due_date_future_check_is_not_overdue(self) -> None:
        task = self._waiting_check_task()
        item = _item_for_task(task.id)
        self.assertFalse(attention_item_is_overdue(item, today=date(2026, 8, 29)))
        self.assertFalse(attention_item_is_overdue(item, today=date(2026, 9, 11)))
        ids = {
            row.source_id
            for row in get_attention_items()
            if row.item_type == ITEM_TYPE_TASK
            and attention_item_is_overdue(row, today=date(2026, 8, 29))
        }
        self.assertNotIn(task.id, ids)
        self.assertEqual(count_overdue_attention_items(today=date(2026, 8, 29)), 0)

    def test_past_check_due_date_is_overdue(self) -> None:
        task = self._waiting_check_task()
        item = _item_for_task(task.id)
        self.assertTrue(attention_item_is_overdue(item, today=date(2026, 9, 12)))
        overdue_ids = {
            row.source_id
            for row in get_attention_items()
            if row.item_type == ITEM_TYPE_TASK
            and attention_item_is_overdue(row, today=date(2026, 9, 12))
        }
        self.assertIn(task.id, overdue_ids)
        self.assertEqual(count_overdue_attention_items(today=date(2026, 9, 12)), 1)

    def test_overdue_card_uses_check_due_date(self) -> None:
        self._waiting_check_task(title="Karta po termínu")
        with patch("core.dashboard.widget_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 8, 29)
            widget = SummaryWidget()
            self.assertEqual(widget.overdue.value_label.text(), "0")
            widget.close()
        with patch("core.dashboard.widget_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 9, 12)
            widget = SummaryWidget()
            self.assertEqual(widget.overdue.value_label.text(), "1")
            widget.close()

    def test_due_color_uses_check_due_date(self) -> None:
        task = self._waiting_check_task()
        item = _item_for_task(task.id)
        widget = UpcomingTasksWidget()
        self.assertEqual(
            widget._due_color(item, datetime(2026, 8, 29)),
            _COLOR_FUTURE,
        )
        self.assertEqual(
            widget._due_color(item, datetime(2026, 9, 5)),
            _COLOR_APPROACHING,
        )
        self.assertEqual(
            widget._due_color(item, datetime(2026, 9, 12)),
            _COLOR_OVERDUE,
        )
        widget.close()

    def test_sorting_uses_check_due_date(self) -> None:
        waiting = self._waiting_check_task(title="Kontrola později", priority="Normální")
        earlier = task_service.create_task(
            title="Aktivní dříve",
            due_date=date(2026, 9, 5),
            requires_verification=False,
        )
        items = get_attention_items()
        task_rows = [
            item
            for item in items
            if item.source_id in {waiting.id, earlier.id} and item.item_type == ITEM_TYPE_TASK
        ]
        self.assertEqual([item.source_id for item in task_rows], [earlier.id, waiting.id])
        self.assertEqual(task_rows[0].date, date(2026, 9, 5))
        self.assertEqual(task_rows[1].date, date(2026, 9, 11))

    def test_widget_shows_control_label_and_check_date(self) -> None:
        task = self._waiting_check_task(title="Viditelná kontrola")
        widget = UpcomingTasksWidget()
        found = None
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, COL_TYPE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == task.id:
                found = row
                break
        self.assertIsNotNone(found)
        self.assertEqual(widget.table.item(found, COL_TYPE).text(), "Kontrola úkolu")
        self.assertIn("11. 9. 2026", widget.table.item(found, COL_DUE).text())
        self.assertNotIn("28. 8. 2026", widget.table.item(found, COL_DUE).text())
        self.assertGreaterEqual(widget.table.columnWidth(COL_TYPE), 130)
        widget.close()

    def test_opening_keeps_task_identity_and_opens_original_task(self) -> None:
        task = self._waiting_check_task(title="Otevřít původní úkol")
        opened: list = []

        def on_open(item):
            opened.append(item)

        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        target_row = next(
            row
            for row in range(widget.table.rowCount())
            if widget.table.item(row, COL_TYPE).data(Qt.ItemDataRole.UserRole).source_id
            == task.id
        )
        widget.table.selectRow(target_row)
        widget._open_selected()
        self.assertEqual(len(opened), 1)
        item = opened[0]
        self.assertEqual(item.item_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_type, ITEM_TYPE_TASK)
        self.assertEqual(item.source_id, task.id)
        self.assertEqual(item.type_label, "Kontrola úkolu")
        widget.close()

        dummy = SimpleNamespace()
        dummy._open_task_by_id = MagicMock()
        MainWindow._open_attention_item(dummy, item)
        dummy._open_task_by_id.assert_called_once_with(task.id)

    def test_reminders_still_wait_until_check_due_date(self) -> None:
        task = self._waiting_check_task(title="Připomínka až v den kontroly")
        today_before = date(2026, 8, 29)
        self.assertFalse(task_should_appear_in_reminders(task, today_before))
        burning, due_today, waiting = classify_burning_tasks([task], today_before)
        self.assertEqual(burning, [])
        self.assertEqual(due_today, [])
        self.assertEqual(waiting, [])
        self.assertIsNotNone(_item_for_task(task.id))

        widget = TodayWidget()
        widget.refresh(today=today_before)
        self.assertNotIn("Připomínka až v den kontroly", widget.content.text())
        widget.refresh(today=date(2026, 9, 11))
        self.assertIn("Připomínka až v den kontroly", widget.content.text())
        self.assertIn("11.09.2026", widget.content.text())
        self.assertNotIn("28.08.2026", widget.content.text())
        widget.close()

    def test_type_label_override_does_not_change_identity(self) -> None:
        plain = AttentionItem(
            item_type=ITEM_TYPE_TASK,
            source_id=7,
            title="Bez override",
            date=date(2026, 8, 28),
            subtitle="Ručně",
            status="Aktivní",
            source_type=ITEM_TYPE_TASK,
        )
        overridden = AttentionItem(
            item_type=ITEM_TYPE_TASK,
            source_id=7,
            title="S override",
            date=date(2026, 9, 11),
            subtitle="Ručně",
            status=TASK_STATUS_WAITING_CHECK,
            source_type=ITEM_TYPE_TASK,
            type_label_override=TYPE_LABEL_TASK_CONTROL,
        )
        self.assertEqual(plain.type_label, TYPE_LABELS[ITEM_TYPE_TASK])
        self.assertEqual(overridden.type_label, "Kontrola úkolu")
        self.assertEqual(plain.item_type, overridden.item_type)
        self.assertEqual(
            attention_item_identity(plain),
            attention_item_identity(overridden),
        )

    def test_other_type_labels_unchanged_without_override(self) -> None:
        expected = {
            ITEM_TYPE_TASK: "Úkol",
            ITEM_TYPE_AUDIT: "Audit",
            ITEM_TYPE_INSPECTION: "Prověrka",
            ITEM_TYPE_MEETING: "Událost",
        }
        for item_type, label in expected.items():
            item = AttentionItem(
                item_type=item_type,
                source_id=1,
                title="Položka",
                date=date(2026, 9, 1),
                subtitle="",
                status="",
            )
            self.assertEqual(item.type_label, label)
            self.assertEqual(TYPE_LABELS[item_type], label)

    def test_other_upcoming_item_types_keep_own_dates(self) -> None:
        audit_date = date.today() + timedelta(days=4)
        inspection_date = date.today() + timedelta(days=5)
        audit = audit_service.create_audit(
            workplace_name="Audit termín beze změny",
            started_at=audit_date,
        )
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka termín beze změny",
            started_at=inspection_date,
        )
        self._waiting_check_task(title="Kontrola vedle auditu")
        items = {(item.item_type, item.source_id): item for item in get_attention_items()}
        self.assertEqual(items[(ITEM_TYPE_AUDIT, audit.id)].date, audit_date)
        self.assertEqual(items[(ITEM_TYPE_AUDIT, audit.id)].type_label, "Audit")
        self.assertEqual(items[(ITEM_TYPE_INSPECTION, inspection.id)].date, inspection_date)
        self.assertEqual(items[(ITEM_TYPE_INSPECTION, inspection.id)].type_label, "Prověrka")


if __name__ == "__main__":
    unittest.main()
