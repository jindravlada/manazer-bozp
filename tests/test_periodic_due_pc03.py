"""PC-03: výpočet dalšího termínu a opakované provedení v jednom období."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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

    from moduly.periodicke_cinnosti.constants import (
        NEXT_FROM_ACTUAL,
        NEXT_FROM_PLANNED,
        UNIT_MONTHS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )
    from moduly.rocni_plan.constants import DISPLAY_DONE, DISPLAY_TO_PLAN
    from moduly.rocni_plan.sluzby.yearly_plan_service import list_periodic_rows_for_month


class PeriodicDuePc03TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        dialog = getattr(self, "dialog", None)
        if dialog is not None:
            dialog._editor._closing = True
            dialog.close()

    def _activity(self, *, due: date, next_from: str = NEXT_FROM_PLANNED):
        return periodic_activity_service.create_activity(
            title="Kontrola pracoviště",
            next_due_date=due,
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            next_from=next_from,
        )

    def _history(self, activity_id: int):
        rows = periodic_activity_service.list_occurrences(activity_id)
        return sorted(
            (row.id, row.planned_due_date, row.performed_at, row.result_note)
            for row in rows
        )

    def _plan(self, activity_id: int, month: int):
        return [
            (row.planned_due_date, row.display_status, row.occurrence_id)
            for row in list_periodic_rows_for_month(2026, month, today=date(2026, 11, 1))
            if row.activity_id == activity_id
        ]

    def test_early_performance_advances_one_period(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 10, 6),
            result_note="první",
        )
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(occurrence.planned_due_date, date(2026, 11, 5))
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(len(self._history(activity.id)), 1)

    def test_repeated_performances_stay_in_one_period(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        notes = []
        for performed, note in (
            (date(2026, 10, 6), "6. 10."),
            (date(2026, 10, 29), "29. 10."),
            (date(2026, 11, 2), "2. 11."),
        ):
            periodic_activity_service.record_performance(
                activity.id,
                performed_at=performed,
                result_note=note,
            )
            notes.append(note)
        stored = periodic_activity_service.get_by_id(activity.id)
        history = self._history(activity.id)
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(len(history), 3)
        self.assertEqual([item[1] for item in history], [date(2026, 11, 5)] * 3)
        self.assertEqual([item[2] for item in history], [
            date(2026, 10, 6),
            date(2026, 10, 29),
            date(2026, 11, 2),
        ])
        self.assertEqual([item[3] for item in history], notes)
        november = self._plan(activity.id, 11)
        self.assertEqual(
            [(item[0], item[1]) for item in november],
            [(date(2026, 11, 5), DISPLAY_DONE)],
        )
        self.assertIn(november[0][2], {item[0] for item in history})
        self.assertEqual(
            self._plan(activity.id, 12),
            [(date(2026, 12, 5), DISPLAY_TO_PLAN, None)],
        )
        january = [
            (row.planned_due_date, row.display_status)
            for row in list_periodic_rows_for_month(2027, 1, today=date(2026, 11, 1))
            if row.activity_id == activity.id
        ]
        self.assertEqual(january, [(date(2027, 1, 5), DISPLAY_TO_PLAN)])

    def test_performance_on_due_date(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 11, 5),
        )
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(self._history(activity.id)[0][1], date(2026, 11, 5))

    def test_late_performance_skips_passed_deadline(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 12, 10),
        )
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(occurrence.planned_due_date, date(2026, 11, 5))
        self.assertEqual(stored.next_due_date, date(2027, 1, 5))
        self.assertEqual(len(self._history(activity.id)), 1)
        self.assertEqual(
            self._plan(activity.id, 11),
            [(date(2026, 11, 5), DISPLAY_DONE, occurrence.id)],
        )
        self.assertEqual(self._plan(activity.id, 12), [])

    def test_later_period_advances_only_once(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        first = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 10, 6),
            result_note="v období",
        )
        second = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 11, 6),
            result_note="další období",
        )
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.next_due_date, date(2027, 1, 5))
        history = self._history(activity.id)
        self.assertEqual(history[0][0], first.id)
        self.assertEqual(history[0][1:], (date(2026, 11, 5), date(2026, 10, 6), "v období"))
        self.assertEqual(history[1][0], second.id)
        self.assertEqual(history[1][1:], (date(2026, 12, 5), date(2026, 11, 6), "další období"))

    def test_actual_mode_follows_each_performance_date(self) -> None:
        activity = self._activity(due=date(2026, 11, 5), next_from=NEXT_FROM_ACTUAL)
        expected = []
        for performed, due in (
            (date(2026, 10, 6), date(2026, 11, 6)),
            (date(2026, 10, 29), date(2026, 11, 29)),
            (date(2026, 11, 2), date(2026, 12, 2)),
        ):
            periodic_activity_service.record_performance(
                activity.id,
                performed_at=performed,
            )
            stored = periodic_activity_service.get_by_id(activity.id)
            self.assertEqual(stored.next_due_date, due)
            expected.append(performed)
        history = self._history(activity.id)
        self.assertEqual([item[2] for item in history], expected)
        self.assertEqual(len({item[0] for item in history}), 3)
        november = self._plan(activity.id, 11)
        self.assertEqual(
            {item[0] for item in november},
            {date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 29)},
        )
        self.assertTrue(all(item[1] == DISPLAY_DONE for item in november))
        self.assertEqual(
            self._plan(activity.id, 12),
            [(date(2026, 12, 2), DISPLAY_TO_PLAN, None)],
        )

    def test_mode_change_confirms_new_due_and_keeps_history(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 10, 6),
            result_note="původní",
        )
        before = self._history(activity.id)
        activity = periodic_activity_service.get_by_id(activity.id)
        self.dialog = PeriodicActivityDialog(activity=activity)
        index = self.dialog.next_from.findData(NEXT_FROM_ACTUAL)
        self.dialog.next_from.setCurrentIndex(index)
        seen: dict[str, str] = {}

        def confirm(message: str) -> bool:
            seen["message"] = message
            return True

        self.dialog._ask_next_from_change = confirm
        self.assertTrue(self.dialog._save())
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.next_from, NEXT_FROM_ACTUAL)
        self.assertEqual(stored.next_due_date, date(2026, 11, 6))
        self.assertEqual(self._history(activity.id), before)
        self.assertIn("Původní způsob výpočtu: plánovaného termínu", seen["message"])
        self.assertIn("Nový způsob výpočtu: skutečného data provedení", seen["message"])
        self.assertIn("Původní další termín: 05.12.2026", seen["message"])
        self.assertIn("Nový další termín: 06.11.2026", seen["message"])

    def test_rejected_mode_change_keeps_stored_values(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 10, 6),
        )
        before = self._history(activity.id)
        activity = periodic_activity_service.get_by_id(activity.id)
        self.dialog = PeriodicActivityDialog(activity=activity)
        self.dialog.title_edit.setText("Přejmenováno")
        index = self.dialog.next_from.findData(NEXT_FROM_ACTUAL)
        self.dialog.next_from.setCurrentIndex(index)
        self.dialog._ask_next_from_change = lambda _message: False
        self.assertFalse(self.dialog._save())
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.title, "Kontrola pracoviště")
        self.assertEqual(stored.next_from, NEXT_FROM_PLANNED)
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(self._history(activity.id), before)

    def test_title_and_note_do_not_change_due_or_ask(self) -> None:
        activity = self._activity(due=date(2026, 11, 5))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 10, 6),
            result_note="beze změny",
        )
        before = self._history(activity.id)
        activity = periodic_activity_service.get_by_id(activity.id)
        self.dialog = PeriodicActivityDialog(activity=activity)
        self.dialog.title_edit.setText("Nový název")
        self.dialog.note_edit.setPlainText("Nová poznámka")

        def forbidden(_message: str) -> bool:
            raise AssertionError("změna názvu nemá otevírat přepočet")

        self.dialog._ask_next_from_change = forbidden
        self.assertTrue(self.dialog._save())
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.title, "Nový název")
        self.assertEqual(stored.note, "Nová poznámka")
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(stored.next_from, NEXT_FROM_PLANNED)
        self.assertEqual(self._history(activity.id), before)
