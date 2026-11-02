"""RP-03: samostatné výskyty periodických činností v Ročním plánu."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy import func, select

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

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from moduly.periodicke_cinnosti.constants import (
        CALENDAR_STATUS_TO_PLAN,
        CALENDAR_STATUS_WILL_NOT_PERFORM,
        ENTITY_PERIODIC_OCCURRENCE,
        UNIT_DAYS,
        UNIT_MONTHS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.modely.periodic_calendar_occurrence import (
        PeriodicCalendarOccurrence,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar_occurrence_service import (
        CalendarOccurrenceError,
        list_for_activity,
        move_occurrence,
        restore_to_planning,
        skip_occurrence,
    )
    from moduly.rocni_plan.constants import (
        COL_SOURCE,
        COL_STATUS,
        COL_TITLE,
        DISPLAY_DONE,
        DISPLAY_TO_PLAN,
        DISPLAY_WILL_NOT_PERFORM,
        SOURCE_LABEL_MANUAL,
        SOURCE_LABEL_PERIODIC,
        STATUS_PLANNED,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.periodic_skip_dialog import PeriodicSkipDialog
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab


def _rows(year: int, month: int, activity_id: int):
    return [
        row
        for row in yearly_plan_service.list_month_rows(
            year,
            month,
            today=date(2026, 1, 1),
        )
        if row.activity_id == activity_id
    ]


def _exception_count(activity_id: int | None = None) -> int:
    with get_session() as session:
        stmt = select(func.count()).select_from(PeriodicCalendarOccurrence)
        if activity_id is not None:
            stmt = stmt.where(PeriodicCalendarOccurrence.activity_id == activity_id)
        return int(session.scalar(stmt) or 0)


class CalendarYearlyPlanTestCase(unittest.TestCase):
    def _activity(self, **kwargs):
        data = {
            "title": "Kontrola pracoviště",
            "next_due_date": date(2026, 1, 15),
            "repeat_every": 1,
            "repeat_unit": UNIT_MONTHS,
            "calendar_start_year": 2026,
            "calendar_start_month": 1,
            "calendar_interval_months": 1,
            "calendar_setup_required": False,
        }
        data.update(kwargs)
        return periodic_activity_service.create_activity(**data)

    def test_monthly_quarterly_and_yearly_occurrences(self) -> None:
        monthly = self._activity(title="Měsíční")
        for month in (1, 2, 3, 4):
            rows = _rows(2026, month, monthly.id)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].calendar_managed)
            self.assertEqual(rows[0].display_status, DISPLAY_TO_PLAN)
            self.assertEqual((rows[0].slot_year, rows[0].slot_month), (2026, month))
        self.assertEqual(_exception_count(monthly.id), 0)

        quarterly = self._activity(
            title="Čtvrtletní",
            calendar_start_month=3,
            calendar_interval_months=3,
            next_due_date=date(2026, 3, 1),
        )
        present = []
        for month in range(1, 13):
            if _rows(2026, month, quarterly.id):
                present.append(month)
        self.assertEqual(present, [3, 6, 9, 12])

        yearly = self._activity(
            title="Roční",
            calendar_start_month=4,
            calendar_interval_months=12,
            next_due_date=date(2026, 4, 1),
            repeat_unit=UNIT_YEARS,
        )
        self.assertEqual(len(_rows(2026, 4, yearly.id)), 1)
        self.assertEqual(len(_rows(2027, 4, yearly.id)), 1)
        self.assertEqual(len(_rows(2028, 4, yearly.id)), 1)
        self.assertEqual(_rows(2027, 5, yearly.id), [])

    def test_move_shows_both_april_rows_and_keeps_the_series(self) -> None:
        activity = self._activity()
        anchor = (
            activity.calendar_start_year,
            activity.calendar_start_month,
            activity.calendar_interval_months,
            activity.next_due_date,
            activity.repeat_every,
            activity.repeat_unit,
        )
        moved = move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        assert moved is not None
        again = move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        assert again is not None
        self.assertEqual(moved.id, again.id)
        self.assertEqual(_exception_count(activity.id), 1)

        self.assertEqual(_rows(2026, 3, activity.id), [])
        april = _rows(2026, 4, activity.id)
        self.assertEqual(len(april), 2)
        moved_row = next(row for row in april if row.slot_month == 3)
        regular = next(row for row in april if row.slot_month == 4)
        self.assertIn("přesunuto z března 2026", moved_row.title)
        self.assertNotIn("přesunuto", regular.title)
        self.assertEqual(moved_row.display_status, DISPLAY_TO_PLAN)
        self.assertEqual(regular.display_status, DISPLAY_TO_PLAN)
        self.assertEqual((moved_row.display_year, moved_row.display_month), (2026, 4))
        may = _rows(2026, 5, activity.id)
        self.assertEqual(len(may), 1)
        self.assertEqual(may[0].slot_month, 5)
        self.assertNotIn("přesunuto", may[0].title)

        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(
            (
                stored.calendar_start_year,
                stored.calendar_start_month,
                stored.calendar_interval_months,
                stored.next_due_date,
                stored.repeat_every,
                stored.repeat_unit,
            ),
            anchor,
        )

    def test_move_back_removes_the_exception(self) -> None:
        activity = self._activity(title="Návrat")
        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        restored = move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=3,
        )
        self.assertIsNone(restored)
        self.assertEqual(_exception_count(activity.id), 0)
        self.assertEqual(len(_rows(2026, 3, activity.id)), 1)
        self.assertEqual(len(_rows(2026, 4, activity.id)), 1)
        self.assertNotIn("přesunuto", _rows(2026, 4, activity.id)[0].title)

    def test_year_boundary_move(self) -> None:
        activity = self._activity(
            title="Přes rok",
            calendar_start_month=11,
            next_due_date=date(2026, 11, 1),
        )
        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=11,
            to_year=2027,
            to_month=1,
        )
        self.assertEqual(_rows(2026, 11, activity.id), [])
        january = _rows(2027, 1, activity.id)
        self.assertEqual(len(january), 2)
        origins = sorted(row.slot_month for row in january)
        self.assertEqual(origins, [1, 11])

    def test_skip_requires_reason_and_leaves_other_months(self) -> None:
        activity = self._activity(title="Mimo provoz")
        with self.assertRaises(CalendarOccurrenceError):
            skip_occurrence(
                activity.id,
                original_year=2026,
                original_month=3,
                reason="   ",
            )
        self.assertEqual(_exception_count(activity.id), 0)
        self.assertEqual(_rows(2026, 3, activity.id)[0].display_status, DISPLAY_TO_PLAN)

        skipped = skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            reason="Pracoviště bylo v březnu mimo provoz.",
        )
        self.assertEqual(skipped.status, CALENDAR_STATUS_WILL_NOT_PERFORM)
        self.assertEqual(skipped.skip_reason, "Pracoviště bylo v březnu mimo provoz.")
        march = _rows(2026, 3, activity.id)
        self.assertEqual(len(march), 1)
        self.assertEqual(march[0].display_status, DISPLAY_WILL_NOT_PERFORM)
        self.assertIn("mimo provoz", march[0].note)
        april = _rows(2026, 4, activity.id)
        self.assertEqual(len(april), 1)
        self.assertEqual(april[0].display_status, DISPLAY_TO_PLAN)
        self.assertEqual(april[0].slot_month, 4)
        february = _rows(2026, 2, activity.id)
        self.assertEqual(february[0].display_status, DISPLAY_TO_PLAN)

    def test_restore_skip_returns_to_planning_and_keeps_a_move(self) -> None:
        activity = self._activity(title="Zpět do plánu")
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            reason="Dočasně uzavřeno.",
        )
        restored = restore_to_planning(
            activity.id,
            original_year=2026,
            original_month=3,
        )
        self.assertIsNone(restored)
        self.assertEqual(_exception_count(activity.id), 0)
        march = _rows(2026, 3, activity.id)
        self.assertEqual(march[0].display_status, DISPLAY_TO_PLAN)

        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            reason="Přesunuto a vynecháno.",
        )
        kept = restore_to_planning(
            activity.id,
            original_year=2026,
            original_month=3,
        )
        assert kept is not None
        self.assertEqual(kept.status, CALENDAR_STATUS_TO_PLAN)
        self.assertEqual(kept.skip_reason, "")
        self.assertEqual((kept.display_year, kept.display_month), (2026, 4))
        self.assertEqual(_rows(2026, 3, activity.id), [])
        april = _rows(2026, 4, activity.id)
        moved = next(row for row in april if row.slot_month == 3)
        self.assertEqual(moved.display_status, DISPLAY_TO_PLAN)

    def test_history_and_attachment_stay_and_are_not_reopened(self) -> None:
        activity = self._activity(title="S historií")
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 1, 20),
            performed_by_name="Eva Malá",
            result_note="protokol uložen",
        )
        with get_session() as session:
            session.add(
                Attachment(
                    entity_type=ENTITY_PERIODIC_OCCURRENCE,
                    entity_id=occurrence.id,
                    original_path="/tmp/protokol.pdf",
                    stored_path="/tmp/stored/protokol.pdf",
                    filename="protokol.pdf",
                )
            )
            session.commit()

        january = _rows(2026, 1, activity.id)
        self.assertEqual(len(january), 1)
        self.assertEqual(january[0].display_status, DISPLAY_DONE)
        self.assertFalse(january[0].calendar_managed)
        self.assertEqual(january[0].planned_due_date, date(2026, 1, 15))
        self.assertEqual(january[0].occurrence_id, occurrence.id)

        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        initialize_database()

        kept = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].id, occurrence.id)
        self.assertEqual(kept[0].planned_due_date, date(2026, 1, 15))
        self.assertEqual(kept[0].performed_at, date(2026, 1, 20))
        self.assertEqual(kept[0].result_note, "protokol uložen")
        with get_session() as session:
            files = [
                (item.filename, item.stored_path)
                for item in session.scalars(select(Attachment))
                if item.entity_type == ENTITY_PERIODIC_OCCURRENCE
                and item.entity_id == occurrence.id
            ]
        self.assertEqual(files, [("protokol.pdf", "/tmp/stored/protokol.pdf")])
        still = _rows(2026, 1, activity.id)
        self.assertEqual(len(still), 1)
        self.assertEqual(still[0].display_status, DISPLAY_DONE)
        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.calendar_start_month, 1)
        self.assertEqual(_exception_count(activity.id), 1)

    def test_setup_required_has_no_calendar_occurrences(self) -> None:
        activity = self._activity(
            title="Po dnech",
            repeat_every=10,
            repeat_unit=UNIT_DAYS,
            next_due_date=date(2026, 3, 10),
            calendar_start_year=None,
            calendar_start_month=None,
            calendar_interval_months=None,
            calendar_setup_required=True,
        )
        march = _rows(2026, 3, activity.id)
        self.assertGreaterEqual(len(march), 1)
        self.assertTrue(all(not row.calendar_managed for row in march))
        self.assertIn(date(2026, 3, 10), [row.planned_due_date for row in march])
        april = _rows(2026, 4, activity.id)
        self.assertTrue(all(not row.calendar_managed for row in april))
        self.assertTrue(all(row.display_status == DISPLAY_TO_PLAN for row in march + april))
        with self.assertRaises(CalendarOccurrenceError):
            move_occurrence(
                activity.id,
                original_year=2026,
                original_month=3,
                to_year=2026,
                to_month=4,
            )
        self.assertEqual(_exception_count(activity.id), 0)

    def test_manual_yearly_plan_item_is_unchanged(self) -> None:
        activity = self._activity(title="Vedle ruční")
        manual = yearly_plan_service.create(
            year=2026,
            month=5,
            title="Ruční školení",
        )
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=5,
            reason="Periodická se vynechá, ruční zůstává.",
        )
        stored = yearly_plan_service.get_by_id(manual.id)
        assert stored is not None
        self.assertEqual(stored.title, "Ruční školení")
        self.assertEqual(stored.status, STATUS_PLANNED)
        self.assertEqual(stored.month, 5)
        mixed = yearly_plan_service.list_month_rows(2026, 5, today=date(2026, 1, 1))
        manual_rows = [row for row in mixed if row.plan_item_id == manual.id]
        periodic_rows = [row for row in mixed if row.activity_id == activity.id]
        self.assertEqual(len(manual_rows), 1)
        self.assertEqual(manual_rows[0].source_label, SOURCE_LABEL_MANUAL)
        self.assertEqual(periodic_rows[0].display_status, DISPLAY_WILL_NOT_PERFORM)

    def test_second_database_init_does_not_duplicate(self) -> None:
        activity = self._activity(title="Jedna výjimka")
        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=2,
            to_year=2026,
            to_month=6,
        )
        before = [
            (item.original_year, item.original_month, item.display_year, item.display_month, item.status)
            for item in list_for_activity(activity.id)
        ]
        initialize_database()
        initialize_database()
        after = [
            (item.original_year, item.original_month, item.display_year, item.display_month, item.status)
            for item in list_for_activity(activity.id)
        ]
        self.assertEqual(before, after)
        self.assertEqual(len(after), 1)


class CalendarYearlyPlanUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_buttons_follow_the_selected_occurrence(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Tlačítka výskytu",
            next_due_date=date(2026, 3, 1),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            calendar_start_year=2026,
            calendar_start_month=3,
            calendar_interval_months=1,
        )
        tab = YearlyPlanTab()
        try:
            tab.set_year_month(2026, 3)
            row = self._row_with_title(tab, "Tlačítka výskytu")
            tab.table.selectRow(row)
            tab._refresh_action_buttons()
            self.assertTrue(tab.move_btn.isEnabled())
            self.assertTrue(tab.skip_btn.isEnabled())
            self.assertFalse(tab.restore_plan_btn.isEnabled())
            self.assertTrue(tab.create_task_btn.isEnabled())
            self.assertTrue(tab.create_meeting_btn.isEnabled())
            self.assertFalse(tab.cancel_btn.isEnabled())
            self.assertEqual(tab.table.item(row, COL_SOURCE).text(), SOURCE_LABEL_PERIODIC)
            self.assertEqual(tab.table.item(row, COL_STATUS).text(), "K naplánování")

            skip_occurrence(
                activity.id,
                original_year=2026,
                original_month=3,
                reason="Uzavřený provoz.",
            )
            tab.refresh()
            row = self._row_with_title(tab, "Tlačítka výskytu")
            tab.table.selectRow(row)
            tab._refresh_action_buttons()
            self.assertEqual(tab.table.item(row, COL_STATUS).text(), "Nevykoná se")
            self.assertFalse(tab.skip_btn.isEnabled())
            self.assertTrue(tab.restore_plan_btn.isEnabled())
            self.assertTrue(tab.move_btn.isEnabled())
            self.assertFalse(tab.create_task_btn.isEnabled())
        finally:
            tab.deleteLater()
            self.app.processEvents()

    def test_empty_skip_dialog_does_not_accept(self) -> None:
        dialog = PeriodicSkipDialog()
        try:
            dialog.reason_edit.setPlainText("  ")
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
                dialog._accept_reason()
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            dialog.deleteLater()
            self.app.processEvents()

    def _row_with_title(self, tab: YearlyPlanTab, title: str) -> int:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, COL_TITLE)
            if item is not None and item.text() == title:
                return row
        self.fail(f"Řádek {title!r} nebyl nalezen.")
        return -1
