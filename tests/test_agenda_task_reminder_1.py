"""AGENDA-TASK-REMINDER-1: remind_from a panel Připomínky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
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

    from core.dashboard.widget_today import (
        PANEL_TITLE_REMINDERS,
        TodayWidget,
        classify_burning_tasks,
        task_should_appear_in_reminders,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


class AgendaTaskReminder1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)

    def _ids_in(self, groups) -> set[int]:
        burning, due_today, waiting = groups
        return {t.id for t in burning} | {t.id for t in due_today} | {t.id for t in waiting}

    def test_a_future_due_without_remind_not_shown(self) -> None:
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="A budoucí termín",
            due_date=today + timedelta(days=30),
            remind_from=None,
            requires_verification=False,
        )
        self.assertFalse(task_should_appear_in_reminders(task, today))
        self.assertNotIn(task.id, self._ids_in(classify_burning_tasks([task], today)))

    def test_b_remind_from_today_shown(self) -> None:
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="B připomenout dnes",
            due_date=today + timedelta(days=30),
            remind_from=today,
            requires_verification=False,
        )
        self.assertTrue(task_should_appear_in_reminders(task, today))
        self.assertIn(task.id, self._ids_in(classify_burning_tasks([task], today)))

    def test_c_appears_when_remind_from_reached(self) -> None:
        remind = date(2026, 9, 1)
        due = date(2026, 9, 30)
        task = task_service.create_task(
            title="C od data",
            due_date=due,
            remind_from=remind,
            requires_verification=False,
        )
        self.assertFalse(task_should_appear_in_reminders(task, date(2026, 8, 31)))
        self.assertTrue(task_should_appear_in_reminders(task, remind))

    def test_d_due_date_today_without_remind(self) -> None:
        today = date(2026, 9, 30)
        task = task_service.create_task(
            title="D termín dnes",
            due_date=today,
            remind_from=None,
            requires_verification=False,
        )
        self.assertTrue(task_should_appear_in_reminders(task, today))

    def test_e_stays_after_due_date(self) -> None:
        due = date(2026, 9, 30)
        task = task_service.create_task(
            title="E po termínu",
            due_date=due,
            remind_from=None,
            requires_verification=False,
        )
        self.assertTrue(task_should_appear_in_reminders(task, date(2026, 10, 5)))

    def test_f_priority_alone_does_not_show_early(self) -> None:
        today = date(2026, 9, 1)
        for priority in ("Kritická", "Vysoká", "Normální", "Nízká"):
            task = task_service.create_task(
                title=f"F {priority}",
                priority=priority,
                due_date=today + timedelta(days=90),
                remind_from=None,
                requires_verification=False,
            )
            self.assertFalse(
                task_should_appear_in_reminders(task, today),
                msg=priority,
            )

    def test_g_h_i_waiting_check_uses_check_due_only(self) -> None:
        task = task_service.create_task(
            title="GHI čeká kontrolu",
            due_date=date(2026, 8, 31),
            remind_from=date(2026, 8, 1),
            completed=True,
            completed_date=date(2026, 8, 20),
            requires_verification=True,
            check_due_date=date(2026, 10, 30),
        )
        self.assertEqual(task.computed_status, "Splněno - čeká na kontrolu")
        # H: před check_due_date není (ani remind_from ani starý due_date)
        self.assertFalse(task_should_appear_in_reminders(task, date(2026, 9, 1)))
        # I: v den / po check_due_date je
        self.assertTrue(task_should_appear_in_reminders(task, date(2026, 10, 30)))
        self.assertTrue(task_should_appear_in_reminders(task, date(2026, 11, 1)))

    def test_j_closed_and_canceled_hidden(self) -> None:
        today = date(2026, 9, 1)
        closed = task_service.create_task(
            title="J ukončeno",
            due_date=date(2026, 8, 1),
            completed=True,
            completed_date=date(2026, 8, 1),
            requires_verification=False,
        )
        canceled = task_service.create_task(
            title="J zrušeno",
            due_date=date(2026, 8, 1),
            canceled=True,
            requires_verification=False,
        )
        self.assertEqual(closed.computed_status, "Ukončeno")
        self.assertEqual(canceled.computed_status, "Zrušeno")
        self.assertFalse(task_should_appear_in_reminders(closed, today))
        self.assertFalse(task_should_appear_in_reminders(canceled, today))

    def test_k_no_due_no_remind(self) -> None:
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="K bez termínů",
            due_date=None,
            remind_from=None,
            requires_verification=False,
        )
        self.assertFalse(task_should_appear_in_reminders(task, today))

    def test_l_no_due_with_remind(self) -> None:
        remind = date(2026, 9, 1)
        task = task_service.create_task(
            title="L jen připomenutí",
            due_date=None,
            remind_from=remind,
            requires_verification=False,
        )
        self.assertFalse(task_should_appear_in_reminders(task, date(2026, 8, 31)))
        self.assertTrue(task_should_appear_in_reminders(task, remind))

    def test_m_remind_after_due_rejected(self) -> None:
        with self.assertRaises(ValueError):
            task_service.create_task(
                title="M neplatné",
                due_date=date(2026, 9, 1),
                remind_from=date(2026, 9, 2),
                requires_verification=False,
            )
        self.assertIsNotNone(
            task_service.validate_remind_from(date(2026, 9, 2), date(2026, 9, 1))
        )

    def test_n_remind_can_be_cleared_to_null(self) -> None:
        task = task_service.create_task(
            title="N clear",
            due_date=date(2026, 10, 1),
            remind_from=date(2026, 9, 1),
            requires_verification=False,
        )
        updated = task_service.update_task(
            task_id=task.id,
            title=task.title,
            due_date=task.due_date,
            remind_from=None,
            requires_verification=False,
        )
        self.assertIsNotNone(updated)
        self.assertIsNone(updated.remind_from)

    def test_o_auto_task_null_remind_default(self) -> None:
        task = task_service.create_task(
            title="O automatický",
            due_date=date(2026, 12, 1),
            source_module="audit",
            source_record_id=1,
        )
        self.assertIsNone(task.remind_from)

    def test_p_panel_title_is_pripominky(self) -> None:
        self.assertEqual(PANEL_TITLE_REMINDERS, "Připomínky")
        widget = TodayWidget()
        self.assertEqual(widget.title_label.text(), "Připomínky")
        widget.close()

    def test_dialog_remind_from_save_and_dirty(self) -> None:
        dialog = TaskDialog()
        dialog.title_edit.setPlainText("Dialog remind")
        dialog.due_date_edit.set_date_iso("2026-10-30")
        dialog.remind_from_edit.set_date_value(date(2026, 9, 1))
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(dialog._persist())
        self.assertIsNotNone(dialog.task)
        self.assertEqual(dialog.task.remind_from, date(2026, 9, 1))
        self.assertFalse(dialog._is_dirty())

        dialog.remind_from_edit.clear_date()
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(dialog._persist())
        self.assertIsNone(dialog.task.remind_from)
        dialog._closing = True
        dialog.close()

    def test_dialog_rejects_remind_after_due(self) -> None:
        dialog = TaskDialog()
        dialog.title_edit.setPlainText("Neplatný remind")
        dialog.due_date_edit.set_date_iso("2026-09-01")
        dialog.remind_from_edit.set_date_value(date(2026, 9, 15))
        with patch("moduly.ukoly.ui.task_dialog.QMessageBox.warning") as warn:
            self.assertFalse(dialog._persist())
            warn.assert_called_once()
        dialog._closing = True
        dialog.close()

    def test_dialog_helper_text(self) -> None:
        dialog = TaskDialog()
        tip = dialog.remind_from_edit.toolTip()
        self.assertIn("Pracovní ploše", tip)
        self.assertIn("Připomínky", tip)
        self.assertIn("Připomínky", dialog.remind_from_hint.text())
        dialog._closing = True
        dialog.close()


if __name__ == "__main__":
    unittest.main()
