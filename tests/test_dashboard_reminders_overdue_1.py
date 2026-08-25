"""DASHBOARD-REMINDERS-OVERDUE-1: rolování Připomínek a společný počet Po termínu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="dashboard-reminders-overdue-1-"))

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
        ITEM_TYPE_EXTERNAL_AUDIT,
        ITEM_TYPE_INSPECTION,
        ITEM_TYPE_TASK,
        AttentionItem,
        attention_item_identity,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import (
        count_overdue_attention_items,
        get_attention_items,
        overdue_attention_items,
    )
    from core.dashboard.widget_summary import OVERDUE_CARD_SUBTITLE, SummaryWidget
    from core.dashboard.widget_today import TodayWidget
    from core.dashboard.widget_upcoming_tasks import COL_DUE, COL_TITLE, UpcomingTasksWidget
    from core.widgets.persistent_tooltips import (
        install_persistent_tooltips,
        persistent_tooltips_installed,
        uninstall_persistent_tooltips,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


def _send_wheel(widget, *, delta_y: int = -240) -> None:
    center = widget.rect().center()
    event = QWheelEvent(
        QPointF(center),
        widget.mapToGlobal(QPointF(center)),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def _attention(
    *,
    item_type: str = ITEM_TYPE_TASK,
    source_id: int = 1,
    title: str = "Položka",
    due: date | None = None,
    identity_key: str = "",
    visit_date: str = "",
    event_at=None,
) -> AttentionItem:
    metadata = {}
    if visit_date:
        metadata["visit_date"] = visit_date
    return AttentionItem(
        item_type=item_type,
        source_id=source_id,
        title=title,
        date=due,
        subtitle="",
        status="",
        event_at=event_at,
        open_metadata=metadata,
        identity_key=identity_key,
    )


class DashboardRemindersOverdue1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") != STATUS_PLANNED:
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
                status=STATUS_CANCELLED,
            )
        today = date.today()
        if not yearly_plan_service.is_month_processed(today.year, today.month):
            yearly_plan_service.mark_month_processed(today.year, today.month)

    def _show_reminders(self, widget: TodayWidget, *, width: int = 440) -> None:
        widget.setFixedHeight(170)
        widget.resize(width, 170)
        widget.show()
        QApplication.processEvents()
        widget.content._update_min_height()
        QApplication.processEvents()

    def _labeled_overdue_count(self, widget: UpcomingTasksWidget) -> int:
        return sum(
            1
            for row in range(widget.table.rowCount())
            if "Po termínu" in (widget.table.item(row, COL_DUE).text() or "")
        )

    def test_few_reminders_have_no_vertical_scrollbar(self) -> None:
        today = date.today()
        task_service.create_task(
            title="Jedna připomínka",
            due_date=today,
            remind_from=today,
        )
        widget = TodayWidget()
        self._show_reminders(widget)
        self.assertEqual(
            widget._scroll.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertEqual(widget._scroll.verticalScrollBar().maximum(), 0)
        widget.close()

    def test_many_reminders_scroll_to_last_row(self) -> None:
        today = date.today()
        last_title = "Poslední připomínka 11"
        for index in range(12):
            task_service.create_task(
                title=f"Poslední připomínka {index:02d}" if index < 11 else last_title,
                due_date=today - timedelta(days=1),
            )
        widget = TodayWidget()
        self._show_reminders(widget)
        self.assertIn(last_title, widget.content.text())
        bar = widget._scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        QApplication.processEvents()
        self.assertEqual(bar.value(), bar.maximum())
        self.assertGreater(widget.content.minimumHeight(), widget._scroll.viewport().height())
        widget.close()

    def test_horizontal_scrollbar_is_disabled(self) -> None:
        today = date.today()
        task_service.create_task(
            title="Velmi dlouhý název připomínky " * 8,
            due_date=today,
            remind_from=today,
        )
        widget = TodayWidget()
        self._show_reminders(widget, width=360)
        self.assertEqual(
            widget._scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertEqual(widget._scroll.horizontalScrollBar().maximum(), 0)
        widget.close()

    def test_refresh_does_not_duplicate_scroll_widgets(self) -> None:
        today = date.today()
        task_service.create_task(title="Obnovení 1", due_date=today - timedelta(days=1))
        widget = TodayWidget()
        self._show_reminders(widget)
        original_content = widget.content
        original_scroll = widget._scroll
        widget._scroll.verticalScrollBar().setValue(
            widget._scroll.verticalScrollBar().maximum()
        )
        task_service.create_task(title="Obnovení 2", due_date=today - timedelta(days=1))
        widget.refresh()
        QApplication.processEvents()
        self.assertIs(widget.content, original_content)
        self.assertIs(widget._scroll, original_scroll)
        self.assertEqual(len(widget.findChildren(QScrollArea)), 1)
        self.assertIn("Obnovení 1", widget.content.text())
        self.assertIn("Obnovení 2", widget.content.text())
        bar = widget._scroll.verticalScrollBar()
        self.assertLessEqual(bar.value(), bar.maximum())
        widget.close()

    def test_empty_state_stays_readable_without_scrollbar(self) -> None:
        widget = TodayWidget()
        self._show_reminders(widget)
        self.assertIn("Nic k připomenutí.", widget.content.text())
        self.assertEqual(widget._scroll.verticalScrollBar().maximum(), 0)
        widget.close()

    def test_reminder_open_action_and_wheel_stay_functional(self) -> None:
        today = date.today()
        opened: list[int] = []
        last_title = "Otevřít poslední"
        for index in range(10):
            title = last_title if index == 9 else f"Rolovat {index}"
            task_service.create_task(title=title, due_date=today - timedelta(days=1))
        task = next(
            item for item in task_service.get_all_tasks() if item.title == last_title
        )
        widget = TodayWidget(open_task_callback=opened.append)
        self._show_reminders(widget)
        bar = widget._scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        before = bar.value()
        _send_wheel(widget)
        QApplication.processEvents()
        self.assertGreater(bar.value(), before)
        widget._on_link_clicked(f"task:{task.id}")
        self.assertEqual(opened, [task.id])
        widget.close()

    def test_persistent_tooltips_remain_installed(self) -> None:
        install_persistent_tooltips(self._app)
        try:
            self.assertTrue(persistent_tooltips_installed())
            widget = UpcomingTasksWidget()
            task_service.create_task(
                title="Tooltip úkol",
                due_date=date.today() + timedelta(days=1),
            )
            widget.refresh()
            self.assertGreaterEqual(widget.table.rowCount(), 1)
            title_item = widget.table.item(0, COL_TITLE)
            self.assertIsNotNone(title_item)
            self.assertEqual(title_item.toolTip(), "")
        finally:
            uninstall_persistent_tooltips()

    def test_task_before_today_and_today_and_overdue(self) -> None:
        today = date.today()
        future = task_service.create_task(
            title="Úkol před termínem",
            due_date=today + timedelta(days=3),
        )
        due_today = task_service.create_task(
            title="Úkol dnes",
            due_date=today,
        )
        overdue = task_service.create_task(
            title="Úkol po termínu",
            due_date=today - timedelta(days=2),
        )
        items = {item.source_id: item for item in get_attention_items(today=today)}
        self.assertFalse(attention_item_is_overdue(items[future.id], today=today))
        self.assertFalse(attention_item_is_overdue(items[due_today.id], today=today))
        self.assertTrue(attention_item_is_overdue(items[overdue.id], today=today))
        counted = {item.source_id for item in overdue_attention_items(today=today)}
        self.assertNotIn(future.id, counted)
        self.assertNotIn(due_today.id, counted)
        self.assertIn(overdue.id, counted)

    def test_overdue_inspection_is_counted(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka po termínu",
            started_at=date.today() - timedelta(days=4),
        )
        items = overdue_attention_items()
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_INSPECTION and item.source_id == inspection.id
                for item in items
            )
        )
        summary = SummaryWidget()
        self.assertEqual(summary.overdue.value_label.text(), "1")
        self.assertEqual(summary.overdue.subtitle_label.text(), OVERDUE_CARD_SUBTITLE)

    def test_overdue_audit_is_counted_without_task_filter(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Audit po termínu",
            started_at=date.today() - timedelta(days=3),
        )
        items = overdue_attention_items()
        types = {item.item_type for item in items}
        self.assertIn(ITEM_TYPE_AUDIT, types)
        self.assertNotEqual(types, {ITEM_TYPE_TASK})
        self.assertTrue(
            any(item.source_id == audit.id and item.item_type == ITEM_TYPE_AUDIT for item in items)
        )
        self.assertEqual(count_overdue_attention_items(), 1)

    def test_completed_or_cancelled_item_is_not_counted(self) -> None:
        today = date.today()
        done = task_service.create_task(
            title="Dokončený úkol",
            due_date=today - timedelta(days=5),
            completed=True,
            completed_date=today - timedelta(days=1),
            requires_verification=False,
        )
        canceled = task_service.create_task(
            title="Zrušený úkol",
            due_date=today - timedelta(days=5),
        )
        task_service.cancel_task(canceled.id)
        finished = bozp_inspection_service.create_inspection(
            workplace_name="Ukončená prověrka",
            started_at=today - timedelta(days=6),
        )
        bozp_inspection_service.update_inspection(
            finished.id,
            started_at=today - timedelta(days=6),
            finished_at=today - timedelta(days=1),
        )
        ids = {(item.item_type, item.source_id) for item in overdue_attention_items()}
        self.assertNotIn((ITEM_TYPE_TASK, done.id), ids)
        self.assertNotIn((ITEM_TYPE_TASK, canceled.id), ids)
        self.assertNotIn((ITEM_TYPE_INSPECTION, finished.id), ids)
        self.assertEqual(count_overdue_attention_items(), 0)

    def test_item_also_in_reminders_is_counted_once(self) -> None:
        task = task_service.create_task(
            title="Souběh připomínky",
            due_date=date.today() - timedelta(days=1),
            remind_from=date.today() - timedelta(days=2),
        )
        widget = TodayWidget()
        widget.refresh()
        self.assertIn("Souběh připomínky", widget.content.text())
        widget.close()
        overdue = overdue_attention_items()
        matches = [
            item
            for item in overdue
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(count_overdue_attention_items(), 1)

    def test_duplicate_stable_identity_is_not_double_counted(self) -> None:
        today = date.today()
        due = today - timedelta(days=1)
        first = _attention(
            item_type=ITEM_TYPE_EXTERNAL_AUDIT,
            source_id=7,
            due=due,
            identity_key="external-audit:7:2026-01-01",
            visit_date="2026-01-01",
        )
        duplicate = _attention(
            item_type=ITEM_TYPE_EXTERNAL_AUDIT,
            source_id=7,
            due=due,
            identity_key="external-audit:7:2026-01-01",
            visit_date="2026-01-01",
        )
        other_day = _attention(
            item_type=ITEM_TYPE_EXTERNAL_AUDIT,
            source_id=7,
            due=due,
            identity_key="external-audit:7:2026-01-02",
            visit_date="2026-01-02",
        )
        self.assertEqual(attention_item_identity(first), attention_item_identity(duplicate))
        self.assertNotEqual(attention_item_identity(first), attention_item_identity(other_day))
        self.assertEqual(
            count_overdue_attention_items([first, duplicate, other_day], today=today),
            2,
        )

    def test_overdue_card_matches_upcoming_labels(self) -> None:
        today = date.today()
        task_service.create_task(title="Úkol shoda", due_date=today - timedelta(days=1))
        task_service.create_task(title="Úkol dnes shoda", due_date=today)
        bozp_inspection_service.create_inspection(
            workplace_name="Prověrka shoda",
            started_at=today - timedelta(days=2),
        )
        audit_service.create_audit(
            workplace_name="Audit shoda",
            started_at=today + timedelta(days=2),
        )
        upcoming = UpcomingTasksWidget()
        labeled = self._labeled_overdue_count(upcoming)
        summary = SummaryWidget()
        self.assertEqual(int(summary.overdue.value_label.text()), labeled)
        self.assertEqual(labeled, count_overdue_attention_items())
        self.assertEqual(summary.overdue.subtitle_label.text(), "položky po termínu")
        self.assertEqual(summary.overdue.title_label.text(), "🔴 Po termínu")

    def test_dashboard_refresh_updates_upcoming_reminders_and_overdue(self) -> None:
        today = date.today()
        task = task_service.create_task(
            title="Refresh položka",
            due_date=today - timedelta(days=1),
        )
        page = DashboardPage()
        page.show()
        QApplication.processEvents()
        self.assertIn("Refresh položka", page.today.content.text())
        self.assertEqual(page.summary.overdue.value_label.text(), "1")
        self.assertGreaterEqual(self._labeled_overdue_count(page.upcoming), 1)

        task_service.update_task(
            task.id,
            title=task.title,
            due_date=today + timedelta(days=5),
        )
        page.refresh()
        QApplication.processEvents()
        self.assertNotIn("Refresh položka", page.today.content.text())
        self.assertEqual(page.summary.overdue.value_label.text(), "0")
        self.assertEqual(self._labeled_overdue_count(page.upcoming), 0)

        task_service.update_task(
            task.id,
            title=task.title,
            due_date=today - timedelta(days=2),
            completed=True,
            completed_date=today,
            requires_verification=False,
        )
        page.refresh()
        QApplication.processEvents()
        self.assertEqual(page.summary.overdue.value_label.text(), "0")
        self.assertNotIn("Refresh položka", page.today.content.text())
        page.close()

    def test_reminders_card_keeps_fixed_height(self) -> None:
        page = DashboardPage()
        self.assertEqual(page.today.minimumHeight(), 170)
        self.assertEqual(page.today.maximumHeight(), 170)
        page.close()


if __name__ == "__main__":
    unittest.main()
