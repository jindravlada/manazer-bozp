"""RP-07: editor periodické činnosti bez starého termínu."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

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
    )
    from core.services.attachment_service import attachment_service
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.periodicke_cinnosti.constants import (
        CALENDAR_REQUIRED_MESSAGE,
        COL_NEXT_DUE,
        COL_NOTIFY,
        COL_PERIOD,
        COL_TITLE,
        ENTITY_PERIODIC_OCCURRENCE,
        UNIT_DAYS,
        UNIT_WEEKS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        PeriodicActivityValidationError,
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar import (
        list_calendar_occurrences,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_table import (
        PeriodicActivityTable,
    )
    from moduly.rocni_plan.constants import SOURCE_MODULE_YEARLY_PLAN
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.ukoly.sluzby.task_service import task_service


class PeriodicEditorRp07TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _close(self, dialog: PeriodicActivityDialog) -> None:
        dialog._editor.force_close()
        dialog.deleteLater()

    def _labels(self, dialog: PeriodicActivityDialog) -> list[str]:
        return [label.text() for label in dialog.findChildren(QLabel)]

    def _set_calendar(self, dialog: PeriodicActivityDialog, *, month: int, year: int, interval: int) -> None:
        dialog.calendar_month.setCurrentIndex(dialog.calendar_month.findData(month))
        dialog.calendar_year.setValue(year)
        dialog.calendar_interval.setValue(interval)

    def test_new_activity_does_not_need_next_due_date(self) -> None:
        dialog = PeriodicActivityDialog()
        try:
            labels = self._labels(dialog)
            self.assertNotIn("Nejbližší termín:", labels)
            self.assertNotIn("Opakovat každých:", labels)
            self.assertNotIn("Další termín počítat od:", labels)
            self.assertIn("Opakování v Ročním plánu", labels)
            dialog.title_edit.setText("Měření hluku")
            dialog.note_edit.setPlainText("U vstupu do haly.")
            self._set_calendar(dialog, month=3, year=2027, interval=60)
            self.assertIsNone(dialog.get_data()["next_due_date"])
            self.assertTrue(dialog._save())
        finally:
            self._close(dialog)

        stored = periodic_activity_service.get_by_id(dialog.activity.id)
        self.assertEqual(stored.title, "Měření hluku")
        self.assertIsNone(stored.next_due_date)
        self.assertEqual(stored.calendar_start_month, 3)
        self.assertEqual(stored.calendar_start_year, 2027)
        self.assertEqual(stored.calendar_interval_months, 60)
        self.assertFalse(stored.calendar_setup_required)

    def test_interval_minimum_sixty_and_no_upper_cap(self) -> None:
        dialog = PeriodicActivityDialog()
        dialog2 = None
        try:
            self.assertGreater(dialog.calendar_interval.maximum(), 1200)
            dialog.title_edit.setText("Každý měsíc")
            self._set_calendar(dialog, month=1, year=2027, interval=1)
            self.assertTrue(dialog._save())
            monthly = periodic_activity_service.get_by_id(dialog.activity.id)
            self.assertEqual(monthly.calendar_interval_months, 1)

            dialog2 = PeriodicActivityDialog()
            dialog2.title_edit.setText("Dlouhý interval")
            self._set_calendar(dialog2, month=3, year=2027, interval=1201)
            self.assertTrue(dialog2._save())
            long = periodic_activity_service.get_by_id(dialog2.activity.id)
            self.assertEqual(long.calendar_interval_months, 1201)
        finally:
            self._close(dialog)
            if dialog2 is not None:
                self._close(dialog2)

        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(
                title="Nulový interval",
                calendar_start_year=2027,
                calendar_start_month=3,
                calendar_interval_months=0,
            )
        huge = periodic_activity_service.create_activity(
            title="Sto tisíc měsíců",
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=100000,
        )
        self.assertEqual(huge.calendar_interval_months, 100000)
        self.assertEqual(
            list_calendar_occurrences(
                start_year=2027,
                start_month=3,
                interval_months=100000,
                until_year=2027,
                until_month=3,
            ),
            [(2027, 3)],
        )

    def test_edit_keeps_calendar_and_legacy_fields(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Původní",
            note="původní",
            next_due_date=date(2024, 5, 8),
            repeat_every=14,
            repeat_unit=UNIT_DAYS,
            notify_every=3,
            notify_unit=UNIT_WEEKS,
            next_from="actual",
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=60,
        )
        dialog = PeriodicActivityDialog(activity=activity)
        try:
            dialog.title_edit.setText("Přejmenováno")
            dialog.note_edit.setPlainText("nová poznámka")
            self.assertTrue(dialog._save())
        finally:
            self._close(dialog)
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.calendar_start_year, 2027)
        self.assertEqual(stored.calendar_start_month, 3)
        self.assertEqual(stored.calendar_interval_months, 60)
        self.assertEqual(stored.next_due_date, date(2024, 5, 8))
        self.assertEqual(stored.repeat_every, 14)
        self.assertEqual(stored.repeat_unit, UNIT_DAYS)
        self.assertEqual(stored.notify_every, 3)
        self.assertEqual(stored.notify_unit, UNIT_WEEKS)
        self.assertEqual(stored.next_from, "actual")
        self.assertEqual(stored.note, "nová poznámka")

    def test_legacy_record_can_be_converted_without_losing_history(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Ke převodu",
            next_due_date=date(2026, 7, 8),
            repeat_every=14,
            repeat_unit=UNIT_DAYS,
            notify_every=2,
            notify_unit=UNIT_DAYS,
            next_from="planned",
            calendar_setup_required=True,
        )
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 7, 9),
            result_note="protokol",
        )
        protocol = _TMP / "protokol.txt"
        protocol.write_text("měření", encoding="utf-8")
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
            str(protocol),
        )
        activity = periodic_activity_service.get_by_id(activity.id)
        due_after_performance = activity.next_due_date

        dialog = PeriodicActivityDialog(activity=activity)
        try:
            self.assertFalse(dialog.calendar_setup_warning.isHidden())
            dialog.title_edit.setText("Pořád ke převodu")
            self.assertTrue(dialog._save())
            untouched = periodic_activity_service.get_by_id(activity.id)
            self.assertEqual(untouched.next_due_date, due_after_performance)
            self.assertEqual(untouched.repeat_every, 14)
            self.assertEqual(untouched.repeat_unit, UNIT_DAYS)
            self.assertIsNone(untouched.calendar_start_year)
            self.assertTrue(untouched.calendar_setup_required)

            reopened = PeriodicActivityDialog(activity=untouched)
            self._set_calendar(reopened, month=3, year=2027, interval=60)
            self.assertTrue(reopened._save())
            self.assertEqual(reopened.history_table.rowCount(), 1)
            reopened.history_table.selectRow(0)
            self.assertEqual(reopened.history_attachments.entity_id, occurrence.id)
            self.assertEqual(reopened.history_attachments.list.count(), 1)
        finally:
            self._close(dialog)
            if "reopened" in locals():
                self._close(reopened)

        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.calendar_start_month, 3)
        self.assertEqual(stored.calendar_start_year, 2027)
        self.assertEqual(stored.calendar_interval_months, 60)
        self.assertFalse(stored.calendar_setup_required)
        self.assertEqual(stored.next_due_date, due_after_performance)
        self.assertEqual(stored.repeat_every, 14)
        history = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(history[0].result_note, "protokol")
        files = attachment_service.get_for_entity(ENTITY_PERIODIC_OCCURRENCE, occurrence.id)
        self.assertEqual([item.filename for item in files], ["protokol.txt"])

    def test_clearing_calendar_of_ready_activity_is_rejected(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Hotová řada",
            next_due_date=date(2026, 1, 4),
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=12,
        )
        dialog = PeriodicActivityDialog(activity=activity)
        try:
            dialog.calendar_interval.setValue(0)
            with patch(
                "moduly.periodicke_cinnosti.ui.periodic_activity_dialog.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Ok,
            ) as warning:
                self.assertFalse(dialog._save())
            warning.assert_called()
            self.assertIn(CALENDAR_REQUIRED_MESSAGE, warning.call_args.args)
        finally:
            self._close(dialog)
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.calendar_interval_months, 12)
        self.assertEqual(stored.next_due_date, date(2026, 1, 4))

    def test_list_shows_calendar_anchor_not_old_due_date(self) -> None:
        legacy = periodic_activity_service.create_activity(
            title="Jen starý termín",
            next_due_date=date(2026, 7, 8),
            repeat_every=14,
            repeat_unit=UNIT_DAYS,
            notify_every=3,
            calendar_setup_required=True,
        )
        ready = periodic_activity_service.create_activity(
            title="Měření hluku",
            next_due_date=date(2020, 1, 1),
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=60,
        )
        table = PeriodicActivityTable()
        table.load_activities([legacy, ready])
        self.assertTrue(table.isColumnHidden(COL_NOTIFY))
        visible = [
            table.horizontalHeaderItem(column).text()
            for column in range(table.columnCount())
            if not table.isColumnHidden(column)
        ]
        self.assertNotIn("Nejbližší termín", visible)
        self.assertNotIn("Připomenout", visible)
        self.assertIn("Počátek", visible)
        self.assertIn("Interval", visible)

        texts = {}
        for row in range(table.rowCount()):
            title = table.item(row, COL_TITLE).text()
            texts[title] = (
                table.item(row, COL_NEXT_DUE).text(),
                table.item(row, COL_PERIOD).text(),
            )
        self.assertEqual(texts["Jen starý termín"], ("—", "—"))
        self.assertNotIn("08.07.2026", texts["Jen starý termín"][0])
        self.assertEqual(texts["Měření hluku"], ("březen 2027", "60 měsíců"))
        self.assertNotIn("01.01.2020", texts["Měření hluku"][0])

    def test_yearly_plan_and_dashboard_follow_calendar_not_old_due(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Měření hluku",
            next_due_date=date(2026, 7, 8),
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=60,
        )
        march = [
            row.title
            for row in yearly_plan_service.list_month_rows(2027, 3, today=date(2027, 3, 1))
            if row.activity_id == activity.id
        ]
        next_year = [
            row.title
            for row in yearly_plan_service.list_month_rows(2028, 3, today=date(2028, 3, 1))
            if row.activity_id == activity.id
        ]
        later = [
            row.title
            for row in yearly_plan_service.list_month_rows(2032, 3, today=date(2032, 3, 1))
            if row.activity_id == activity.id
        ]
        self.assertEqual(march, ["Měření hluku"])
        self.assertEqual(next_year, [])
        self.assertEqual(later, ["Měření hluku"])

        task = task_service.create_task(
            title="Úkol z plánu",
            due_date=date(2027, 3, 4),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=activity.id,
            requires_verification=False,
        )
        agenda_titles = {
            (item.item_type, item.title)
            for item in agenda_service.get_items(
                today=date(2027, 3, 1),
                now=datetime(2027, 3, 1, 8, 0),
            )
        }
        self.assertNotIn((ITEM_TYPE_PERIODIC, "Měření hluku"), agenda_titles)
        self.assertIn(("task", "Úkol z plánu"), agenda_titles)
        self.assertFalse(
            any(item.source_id == activity.id for item in get_periodic_reminder_items(today=date(2027, 3, 1)))
        )
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity.id
                for item in get_attention_items(today=date(2027, 3, 1))
            )
        )
        self.assertEqual(task.source_module, SOURCE_MODULE_YEARLY_PLAN)


if __name__ == "__main__":
    unittest.main()
