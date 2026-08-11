"""AGENDA-PERIODIC-REMINDER-1: Připomenout a panel Připomínky pro periodiky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
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

    from core.dashboard.attention_item import ITEM_TYPE_PERIODIC
    from core.dashboard.attention_service import (
        get_attention_items,
        get_periodic_reminder_items,
        get_yearly_plan_month_reminder_items,
    )
    from core.dashboard.widget_today import TodayWidget
    from moduly.periodicke_cinnosti.constants import (
        COLUMN_HEADERS,
        COL_NOTIFY,
        NEXT_FROM_PLANNED,
        UNIT_DAYS,
        UNIT_YEARS,
        format_notify,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        calculate_notify_date,
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )
    from moduly.rocni_plan.constants import month_planning_attention_title
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service


class AgendaPeriodicReminder1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for activity in list(periodic_activity_service.get_all()):
            periodic_activity_service.update_activity(
                activity.id,
                title=f"OLD-{activity.id}-{activity.title}",
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )
        for year in range(2025, 2032):
            for month in range(1, 13):
                yearly_plan_service.month_status_repository.delete_for_month(
                    year, month
                )

    def _create(
        self,
        *,
        title: str,
        due: date,
        notify_every: int,
        notify_unit: str = UNIT_DAYS,
        active: bool = True,
    ):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=due,
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=notify_every,
            notify_unit=notify_unit,
            next_from=NEXT_FROM_PLANNED,
            active=active,
        )

    def _ids(self, today: date) -> set[int]:
        return {item.source_id for item in get_periodic_reminder_items(today=today)}

    def test_ui_label_pripomenout(self) -> None:
        from PySide6.QtWidgets import QFormLayout, QLabel

        self.assertEqual(COLUMN_HEADERS[COL_NOTIFY], "Připomenout")
        dialog = PeriodicActivityDialog()
        form = dialog.findChild(QFormLayout)
        found = False
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label_item is None:
                continue
            widget = label_item.widget()
            if isinstance(widget, QLabel) and widget.text() == "Připomenout:":
                found = True
                break
        self.assertTrue(found)
        dialog._editor.force_close()

    def test_zero_days_means_on_due_date(self) -> None:
        self.assertEqual(format_notify(0, UNIT_DAYS), "v den termínu")
        due = date(2026, 9, 30)
        self.assertEqual(calculate_notify_date(due, 0, UNIT_DAYS), due)
        activity = self._create(title="Nula dní", due=due, notify_every=0)
        self.assertNotIn(activity.id, self._ids(date(2026, 9, 29)))
        self.assertIn(activity.id, self._ids(due))

    def test_fourteen_days_notify_window(self) -> None:
        due = date(2026, 9, 30)
        notify_on = date(2026, 9, 16)
        self.assertEqual(calculate_notify_date(due, 14, UNIT_DAYS), notify_on)
        activity = self._create(title="14 dní", due=due, notify_every=14)
        self.assertNotIn(activity.id, self._ids(date(2026, 9, 15)))
        self.assertIn(activity.id, self._ids(notify_on))
        self.assertIn(activity.id, self._ids(due))
        self.assertIn(activity.id, self._ids(date(2026, 10, 1)))

    def test_shown_in_reminders_panel(self) -> None:
        activity = self._create(
            title="Panel Připomínky",
            due=date(2026, 9, 30),
            notify_every=14,
        )
        widget = TodayWidget()
        widget.refresh(today=date(2026, 9, 16))
        self.assertIn("Panel Připomínky", widget.content.text())
        self.assertIn("30.09.2026", widget.content.text())
        widget.close()

    def test_not_in_upcoming(self) -> None:
        activity = self._create(
            title="Ne v Nadcházejících",
            due=date(2026, 9, 30),
            notify_every=14,
        )
        today = date(2026, 9, 16)
        self.assertIn(activity.id, self._ids(today))
        upcoming = get_attention_items(today=today)
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity.id
                for item in upcoming
            )
        )

    def test_inactive_hidden(self) -> None:
        activity = self._create(
            title="Neaktivní",
            due=date(2026, 9, 30),
            notify_every=14,
            active=False,
        )
        self.assertNotIn(activity.id, self._ids(date(2026, 10, 1)))

    def test_after_perform_disappears(self) -> None:
        activity = self._create(
            title="Po provedení",
            due=date(2026, 9, 30),
            notify_every=14,
        )
        today = date(2026, 9, 20)
        self.assertIn(activity.id, self._ids(today))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 9, 20),
        )
        reloaded = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(reloaded.next_due_date, date(2027, 9, 30))
        self.assertNotIn(activity.id, self._ids(today))
        new_notify = calculate_notify_date(reloaded.next_due_date, 14, UNIT_DAYS)
        self.assertEqual(new_notify, date(2027, 9, 16))
        self.assertNotIn(activity.id, self._ids(date(2027, 9, 15)))
        self.assertIn(activity.id, self._ids(new_notify))

    def test_month_planning_reminder_unchanged(self) -> None:
        today = date(2026, 9, 16)
        items = get_yearly_plan_month_reminder_items(today=today)
        self.assertTrue(
            any(
                item.title == month_planning_attention_title(2026, 9)
                for item in items
            )
        )


if __name__ == "__main__":
    unittest.main()
