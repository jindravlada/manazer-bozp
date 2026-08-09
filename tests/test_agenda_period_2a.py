"""AGENDA-PERIOD-2a: datový základ periodických činností."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.periodicke_cinnosti.constants import (
        NEXT_FROM_ACTUAL,
        NEXT_FROM_PLANNED,
        PLACE_KIND_WORKPLACE,
        UNIT_DAYS,
        UNIT_MONTHS,
        UNIT_WEEKS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        PeriodicActivityValidationError,
        add_period,
        calculate_next_due_date,
        periodic_activity_service,
    )


class AgendaPeriod2aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for activity in list(periodic_activity_service.get_all()):
            # Soft cleanup: deactivate; occurrences remain for immutability tests
            # but we create unique titles per test.
            periodic_activity_service.update_activity(
                activity.id,
                title=activity.title,
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )

    def test_add_period_days_weeks(self) -> None:
        self.assertEqual(add_period(date(2026, 6, 1), 10, UNIT_DAYS), date(2026, 6, 11))
        self.assertEqual(add_period(date(2026, 6, 1), 2, UNIT_WEEKS), date(2026, 6, 15))

    def test_add_period_months_end_of_month(self) -> None:
        self.assertEqual(add_period(date(2026, 1, 31), 1, UNIT_MONTHS), date(2026, 2, 28))
        self.assertEqual(add_period(date(2024, 1, 31), 1, UNIT_MONTHS), date(2024, 2, 29))
        self.assertEqual(add_period(date(2026, 3, 31), 1, UNIT_MONTHS), date(2026, 4, 30))

    def test_add_period_years_leap_day(self) -> None:
        self.assertEqual(add_period(date(2024, 2, 29), 1, UNIT_YEARS), date(2025, 2, 28))
        self.assertEqual(add_period(date(2024, 2, 29), 4, UNIT_YEARS), date(2028, 2, 29))

    def test_add_period_five_years(self) -> None:
        self.assertEqual(add_period(date(2026, 6, 1), 5, UNIT_YEARS), date(2031, 6, 1))

    def test_planned_early_performance_example(self) -> None:
        # plán 1. 6. 2026, 1 rok, provedeno 15. 5. 2026 → 1. 6. 2027
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2026, 5, 15),
                repeat_every=1,
                repeat_unit=UNIT_YEARS,
                next_from=NEXT_FROM_PLANNED,
            ),
            date(2027, 6, 1),
        )

    def test_planned_late_performance_same_cycle(self) -> None:
        # plán 1. 6. 2026, provedeno 10. 7. 2026 → 1. 6. 2027
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2026, 7, 10),
                repeat_every=1,
                repeat_unit=UNIT_YEARS,
                next_from=NEXT_FROM_PLANNED,
            ),
            date(2027, 6, 1),
        )

    def test_planned_several_missed_periods(self) -> None:
        # plán 1. 6. 2024, provedeno 10. 7. 2026 → 1. 6. 2027
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2024, 6, 1),
                performed_at=date(2026, 7, 10),
                repeat_every=1,
                repeat_unit=UNIT_YEARS,
                next_from=NEXT_FROM_PLANNED,
            ),
            date(2027, 6, 1),
        )

    def test_planned_performance_on_due_date_advances(self) -> None:
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2027, 6, 1),
                repeat_every=1,
                repeat_unit=UNIT_YEARS,
                next_from=NEXT_FROM_PLANNED,
            ),
            date(2028, 6, 1),
        )

    def test_actual_next_from(self) -> None:
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2026, 5, 15),
                repeat_every=1,
                repeat_unit=UNIT_YEARS,
                next_from=NEXT_FROM_ACTUAL,
            ),
            date(2027, 5, 15),
        )
        self.assertEqual(
            calculate_next_due_date(
                planned_due_date=date(2026, 6, 1),
                performed_at=date(2026, 7, 10),
                repeat_every=3,
                repeat_unit=UNIT_MONTHS,
                next_from=NEXT_FROM_ACTUAL,
            ),
            date(2026, 10, 10),
        )

    def test_validation_rejects_invalid_fields(self) -> None:
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="  ")
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="X", repeat_every=0)
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="X", notify_every=-1)
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="X", repeat_unit="hours")
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="X", next_from="random")
        with self.assertRaises(PeriodicActivityValidationError):
            periodic_activity_service.create_activity(title="X", place_kind="garage")

    def test_create_and_record_performance_updates_next_due(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Roční školení",
            place_kind=PLACE_KIND_WORKPLACE,
            workplace_id=1,
            workplace_name="Hala A",
            responsible_person_name="Jan Novák",
            next_due_date=date(2026, 6, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=14,
            notify_unit=UNIT_DAYS,
            next_from=NEXT_FROM_PLANNED,
        )
        self.assertTrue(activity.id)
        self.assertEqual(activity.next_due_date, date(2026, 6, 1))

        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            performed_by_name="Petr Technik",
            result_note="Provedeno v pořádku",
        )
        self.assertEqual(occurrence.planned_due_date, date(2026, 6, 1))
        self.assertEqual(occurrence.performed_at, date(2026, 5, 15))
        self.assertEqual(occurrence.result_note, "Provedeno v pořádku")

        reloaded = periodic_activity_service.get_by_id(activity.id)
        assert reloaded is not None
        self.assertEqual(reloaded.next_due_date, date(2027, 6, 1))

    def test_occurrence_is_immutable_after_activity_update(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Kontrola hasicích přístrojů",
            next_due_date=date(2026, 3, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
        )
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 3, 5),
            performed_by_id=7,
            performed_by_name="Eva Kontrolorka",
            result_note="Bez závad",
        )
        occurrence_id = occurrence.id
        original_snapshot = (
            occurrence.planned_due_date,
            occurrence.performed_at,
            occurrence.performed_by_id,
            occurrence.performed_by_name,
            occurrence.result_note,
        )

        periodic_activity_service.update_activity(
            activity.id,
            title="Kontrola HP – upraveno",
            next_due_date=date(2027, 3, 1),
            repeat_every=2,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_ACTUAL,
            note="změna definice",
        )

        stored = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].id, occurrence_id)
        self.assertEqual(
            (
                stored[0].planned_due_date,
                stored[0].performed_at,
                stored[0].performed_by_id,
                stored[0].performed_by_name,
                stored[0].result_note,
            ),
            original_snapshot,
        )

    def test_days_and_weeks_via_record(self) -> None:
        daily = periodic_activity_service.create_activity(
            title="Denní obchůzka",
            next_due_date=date(2026, 8, 1),
            repeat_every=3,
            repeat_unit=UNIT_DAYS,
            next_from=NEXT_FROM_ACTUAL,
        )
        periodic_activity_service.record_performance(
            daily.id,
            performed_at=date(2026, 8, 2),
        )
        self.assertEqual(
            periodic_activity_service.get_by_id(daily.id).next_due_date,
            date(2026, 8, 5),
        )

        weekly = periodic_activity_service.create_activity(
            title="Týdenní kontrola",
            next_due_date=date(2026, 8, 3),
            repeat_every=2,
            repeat_unit=UNIT_WEEKS,
            next_from=NEXT_FROM_PLANNED,
        )
        periodic_activity_service.record_performance(
            weekly.id,
            performed_at=date(2026, 8, 20),
        )
        # plán 3.8. + 2t = 17.8. (<=20) → +2t = 31.8.
        self.assertEqual(
            periodic_activity_service.get_by_id(weekly.id).next_due_date,
            date(2026, 8, 31),
        )


if __name__ == "__main__":
    unittest.main()
