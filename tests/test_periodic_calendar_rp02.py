"""RP-02: pevná kalendářní periodicita, migrace a zachování historie."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import select

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_periodic_calendar_columns,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from moduly.periodicke_cinnosti.constants import (
        ENTITY_PERIODIC_OCCURRENCE,
        UNIT_DAYS,
        UNIT_MONTHS,
        UNIT_WEEKS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.modely.periodic_activity_occurrence import (
        PeriodicActivityOccurrence,
    )
    from moduly.periodicke_cinnosti.repository.periodic_activity_repository import (
        PeriodicActivityOccurrenceRepository,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar import (
        apply_calendar_periodicity_migration,
        list_calendar_occurrences,
        occurs_in_calendar_month,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )


class CalendarSeriesTestCase(unittest.TestCase):
    def test_monthly_keeps_every_month(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=1,
            interval_months=1,
            until_year=2026,
            until_month=4,
        )
        self.assertEqual(series, [(2026, 1), (2026, 2), (2026, 3), (2026, 4)])
        self.assertTrue(
            occurs_in_calendar_month(
                start_year=2026,
                start_month=1,
                interval_months=1,
                year=2026,
                month=3,
            )
        )
        self.assertTrue(
            occurs_in_calendar_month(
                start_year=2026,
                start_month=1,
                interval_months=1,
                year=2026,
                month=4,
            )
        )

    def test_quarterly(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=3,
            interval_months=3,
            until_year=2026,
            until_month=12,
        )
        self.assertEqual(series, [(2026, 3), (2026, 6), (2026, 9), (2026, 12)])

    def test_semiannual(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=3,
            interval_months=6,
            until_year=2027,
            until_month=3,
        )
        self.assertEqual(series, [(2026, 3), (2026, 9), (2027, 3)])

    def test_yearly(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=4,
            interval_months=12,
            until_year=2028,
            until_month=4,
        )
        self.assertEqual(series, [(2026, 4), (2027, 4), (2028, 4)])

    def test_five_years(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=5,
            interval_months=60,
            until_year=2036,
            until_month=5,
        )
        self.assertEqual(series, [(2026, 5), (2031, 5), (2036, 5)])
        self.assertFalse(
            occurs_in_calendar_month(
                start_year=2026,
                start_month=5,
                interval_months=60,
                year=2027,
                month=5,
            )
        )

    def test_year_boundary(self) -> None:
        series = list_calendar_occurrences(
            start_year=2026,
            start_month=11,
            interval_months=3,
            until_year=2027,
            until_month=5,
        )
        self.assertEqual(series, [(2026, 11), (2027, 2), (2027, 5)])

    def test_series_ignores_performance_date(self) -> None:
        before = list_calendar_occurrences(
            start_year=2026,
            start_month=1,
            interval_months=1,
            until_year=2026,
            until_month=6,
        )
        activity = periodic_activity_service.create_activity(
            title="Kontrola pracoviště",
            next_due_date=date(2026, 1, 15),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            calendar_start_year=2026,
            calendar_start_month=1,
            calendar_interval_months=1,
        )
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 3, 28),
        )
        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        after = list_calendar_occurrences(
            start_year=stored.calendar_start_year,
            start_month=stored.calendar_start_month,
            interval_months=stored.calendar_interval_months,
            until_year=2026,
            until_month=6,
        )
        self.assertEqual(after, before)
        self.assertEqual(stored.calendar_start_month, 1)
        self.assertNotEqual(stored.next_due_date, date(2026, 1, 15))


class CalendarMigrationTestCase(unittest.TestCase):
    def _reload(self, activity_id: int):
        stored = periodic_activity_service.get_by_id(activity_id)
        assert stored is not None
        return stored

    def test_migrates_months_and_years_from_next_due(self) -> None:
        quarterly = periodic_activity_service.create_activity(
            title="Čtvrtletí",
            next_due_date=date(2026, 3, 15),
            repeat_every=3,
            repeat_unit=UNIT_MONTHS,
        )
        five_years = periodic_activity_service.create_activity(
            title="Pětileté měření",
            next_due_date=date(2026, 5, 18),
            repeat_every=5,
            repeat_unit=UNIT_YEARS,
        )
        changed = apply_calendar_periodicity_migration()
        self.assertGreaterEqual(changed, 2)

        quarterly = self._reload(quarterly.id)
        self.assertEqual(quarterly.calendar_start_year, 2026)
        self.assertEqual(quarterly.calendar_start_month, 3)
        self.assertEqual(quarterly.calendar_interval_months, 3)
        self.assertFalse(quarterly.calendar_setup_required)
        self.assertEqual(quarterly.next_due_date, date(2026, 3, 15))
        self.assertEqual(quarterly.repeat_every, 3)
        self.assertEqual(quarterly.repeat_unit, UNIT_MONTHS)

        five_years = self._reload(five_years.id)
        self.assertEqual(five_years.calendar_start_year, 2026)
        self.assertEqual(five_years.calendar_start_month, 5)
        self.assertEqual(five_years.calendar_interval_months, 60)
        self.assertEqual(five_years.next_due_date, date(2026, 5, 18))
        self.assertEqual(five_years.repeat_every, 5)
        self.assertEqual(five_years.repeat_unit, UNIT_YEARS)

    def test_days_and_weeks_stay_unchanged_and_need_setup(self) -> None:
        daily = periodic_activity_service.create_activity(
            title="Denní",
            next_due_date=date(2026, 4, 2),
            repeat_every=10,
            repeat_unit=UNIT_DAYS,
            next_from="actual",
        )
        weekly = periodic_activity_service.create_activity(
            title="Týdenní",
            next_due_date=date(2026, 4, 6),
            repeat_every=2,
            repeat_unit=UNIT_WEEKS,
        )
        apply_calendar_periodicity_migration()

        daily = self._reload(daily.id)
        self.assertIsNone(daily.calendar_start_year)
        self.assertIsNone(daily.calendar_start_month)
        self.assertIsNone(daily.calendar_interval_months)
        self.assertTrue(daily.calendar_setup_required)
        self.assertEqual(daily.next_due_date, date(2026, 4, 2))
        self.assertEqual(daily.repeat_every, 10)
        self.assertEqual(daily.repeat_unit, UNIT_DAYS)
        self.assertEqual(daily.next_from, "actual")

        weekly = self._reload(weekly.id)
        self.assertTrue(weekly.calendar_setup_required)
        self.assertIsNone(weekly.calendar_start_year)
        self.assertEqual(weekly.repeat_every, 2)
        self.assertEqual(weekly.repeat_unit, UNIT_WEEKS)
        self.assertEqual(weekly.next_due_date, date(2026, 4, 6))

    def test_history_and_attachment_survive_migration(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="S historií",
            next_due_date=date(2026, 6, 1),
            repeat_every=6,
            repeat_unit=UNIT_MONTHS,
        )
        occurrence = PeriodicActivityOccurrenceRepository().add(
            PeriodicActivityOccurrence(
                activity_id=activity.id,
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2026, 6, 20),
                performed_by_name="Eva Malá",
                result_note="protokol uložen",
            )
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

        apply_calendar_periodicity_migration()
        apply_calendar_periodicity_migration()

        kept = PeriodicActivityOccurrenceRepository().get_by_id(occurrence.id)
        assert kept is not None
        self.assertEqual(kept.planned_due_date, date(2026, 6, 1))
        self.assertEqual(kept.performed_at, date(2026, 6, 20))
        self.assertEqual(kept.performed_by_name, "Eva Malá")
        self.assertEqual(kept.result_note, "protokol uložen")
        with get_session() as session:
            attachments = list(session.scalars(select(Attachment)))
            matched = [
                (item.filename, item.stored_path)
                for item in attachments
                if item.entity_type == ENTITY_PERIODIC_OCCURRENCE
                and item.entity_id == occurrence.id
            ]
        self.assertEqual(matched, [("protokol.pdf", "/tmp/stored/protokol.pdf")])

    def test_second_migration_keeps_manual_start_month(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Upravit počátek",
            next_due_date=date(2026, 3, 10),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            next_from="planned",
        )
        occurrence = PeriodicActivityOccurrenceRepository().add(
            PeriodicActivityOccurrence(
                activity_id=activity.id,
                planned_due_date=date(2026, 3, 10),
                performed_at=date(2026, 3, 11),
                result_note="původní termín",
            )
        )
        apply_calendar_periodicity_migration()
        stored = self._reload(activity.id)
        periodic_activity_service.update_activity(
            stored.id,
            title=stored.title,
            place_kind=stored.place_kind,
            workplace_id=stored.workplace_id,
            workplace_name=stored.workplace_name,
            place_text=stored.place_text,
            responsible_person_id=stored.responsible_person_id,
            responsible_person_name=stored.responsible_person_name,
            next_due_date=stored.next_due_date,
            repeat_every=stored.repeat_every,
            repeat_unit=stored.repeat_unit,
            notify_every=stored.notify_every,
            notify_unit=stored.notify_unit,
            next_from=stored.next_from,
            note=stored.note,
            active=stored.active,
            calendar_start_year=2026,
            calendar_start_month=4,
            calendar_interval_months=1,
            calendar_setup_required=False,
        )
        again = apply_calendar_periodicity_migration()
        self.assertEqual(again, 0)
        stored = self._reload(activity.id)
        self.assertEqual(stored.calendar_start_month, 4)
        self.assertEqual(stored.calendar_start_year, 2026)
        self.assertEqual(stored.next_due_date, date(2026, 3, 10))
        self.assertEqual(stored.repeat_unit, UNIT_MONTHS)
        series = list_calendar_occurrences(
            start_year=stored.calendar_start_year,
            start_month=stored.calendar_start_month,
            interval_months=stored.calendar_interval_months,
            until_year=2026,
            until_month=6,
        )
        self.assertEqual(series[0], (2026, 4))
        self.assertNotIn((2026, 3), series)
        kept = PeriodicActivityOccurrenceRepository().get_by_id(occurrence.id)
        assert kept is not None
        self.assertEqual(kept.planned_due_date, date(2026, 3, 10))
        self.assertEqual(kept.result_note, "původní termín")

    def test_ensure_columns_is_repeatable(self) -> None:
        _ensure_periodic_calendar_columns()
        _ensure_periodic_calendar_columns()


class CalendarDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_days_warning_does_not_rewrite_original_fields(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Stále denní",
            next_due_date=date(2026, 7, 8),
            repeat_every=14,
            repeat_unit=UNIT_DAYS,
            next_from="planned",
        )
        apply_calendar_periodicity_migration()
        activity = periodic_activity_service.get_by_id(activity.id)
        dialog = PeriodicActivityDialog(activity=activity)
        try:
            self.assertFalse(dialog.calendar_setup_warning.isHidden())
            self.assertIsNone(dialog.get_data()["calendar_start_year"])
            self.assertIsNone(dialog.get_data()["calendar_start_month"])
            self.assertIsNone(dialog.get_data()["calendar_interval_months"])
            self.assertTrue(dialog._save())
        finally:
            dialog.deleteLater()
            self.app.processEvents()

        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.next_due_date, date(2026, 7, 8))
        self.assertEqual(stored.repeat_every, 14)
        self.assertEqual(stored.repeat_unit, UNIT_DAYS)
        self.assertEqual(stored.next_from, "planned")
        self.assertIsNone(stored.calendar_start_year)
        self.assertTrue(stored.calendar_setup_required)

    def test_editor_changes_start_month_without_touching_history(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Březen v editoru",
            next_due_date=date(2026, 3, 5),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            calendar_start_year=2026,
            calendar_start_month=3,
            calendar_interval_months=1,
        )
        occurrence = PeriodicActivityOccurrenceRepository().add(
            PeriodicActivityOccurrence(
                activity_id=activity.id,
                planned_due_date=date(2026, 3, 5),
                performed_at=date(2026, 3, 9),
                result_note="beze změny",
            )
        )
        dialog = PeriodicActivityDialog(activity=activity)
        try:
            self.assertTrue(dialog.calendar_setup_warning.isHidden())
            month_index = dialog.calendar_month.findData(4)
            dialog.calendar_month.setCurrentIndex(month_index)
            self.assertTrue(dialog._save())
        finally:
            dialog.deleteLater()
            self.app.processEvents()

        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.calendar_start_month, 4)
        self.assertEqual(stored.calendar_start_year, 2026)
        self.assertEqual(stored.calendar_interval_months, 1)
        self.assertEqual(stored.next_due_date, date(2026, 3, 5))
        self.assertFalse(stored.calendar_setup_required)
        kept = PeriodicActivityOccurrenceRepository().get_by_id(occurrence.id)
        assert kept is not None
        self.assertEqual(kept.planned_due_date, date(2026, 3, 5))
        self.assertEqual(kept.performed_at, date(2026, 3, 9))
        self.assertEqual(kept.result_note, "beze změny")
