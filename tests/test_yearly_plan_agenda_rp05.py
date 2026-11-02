"""RP-05: úkol a událost z výskytu periodické činnosti v Ročním plánu."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

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

    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import (
        PLACE_KIND_WORKPLACE,
        UNIT_MONTHS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar_occurrence_service import (
        CalendarOccurrenceError,
        get_occurrence,
        link_meeting,
        link_task,
        move_occurrence,
        skip_occurrence,
    )
    from moduly.rocni_plan.constants import (
        ACTION_OPEN_TASK,
        COL_LINK,
        COL_TITLE,
        DISPLAY_DONE,
        DISPLAY_PLANNED,
        DISPLAY_TO_PLAN,
        MISSING_LINKED_TASK_MESSAGE,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


class YearlyPlanAgendaRp05TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        for activity in list(periodic_activity_service.get_all(active_only=True)):
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
                workplace_id=activity.workplace_id,
                workplace_name=activity.workplace_name or "",
                place_text=activity.place_text or "",
                responsible_person_id=activity.responsible_person_id,
                responsible_person_name=activity.responsible_person_name or "",
                note=activity.note or "",
            )

    def test_create_task_prefills_and_links_only_after_save(self) -> None:
        worker = settings_service.save_worker(first_name="Eva", last_name="Revizní")
        activity = self._activity(
            title="Revize žebříků",
            note="Vzít protokol.",
            workplace_id=15,
            workplace_name="Sklad A",
            responsible_person_id=worker.id,
        )
        tab = self._tab(2027, 3)
        self._select(tab, "Revize žebříků")
        seen: dict = {}

        class Probe(TaskDialog):
            def exec(self):  # noqa: A003
                seen["title"] = self.title_edit.toPlainText()
                seen["note"] = self.note_edit.toPlainText()
                seen["due"] = self.due_date_edit.get_date_iso()
                seen["person"] = self.person_selector.current_person_id()
                seen["workplace"] = self.workplace_selector.current_workplace_id()
                self.reject()
                return 0

        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", Probe):
            tab.create_task_for_selected()
        self.assertEqual(seen["title"], "Revize žebříků")
        self.assertEqual(seen["note"], "Vzít protokol.")
        self.assertEqual(seen["due"], "2027-03-01")
        self.assertEqual(seen["person"], worker.id)
        self.assertEqual(seen["workplace"], 15)
        self.assertEqual(self._task_ids(), before)
        self.assertIsNone(get_occurrence(activity.id, 2027, 3))
        self._select(tab, "Revize žebříků")
        self.assertEqual(tab.table.selected_display_status(), DISPLAY_TO_PLAN)
        tab.close()

    def test_save_without_close_links_the_first_task(self) -> None:
        activity = self._activity(title="Uložit úkol")
        tab = self._tab(2027, 3)
        self._select(tab, "Uložit úkol")

        class SaveOnly(TaskDialog):
            def exec(self):  # noqa: A003
                self._show_save_confirmation = lambda: None
                self._save_keep_open()
                return 0

        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", SaveOnly):
            tab.create_task_for_selected()
        created = self._new_tasks(before)
        self.assertEqual(len(created), 1)
        stored = get_occurrence(activity.id, 2027, 3)
        self.assertEqual(stored.task_id, created[0].id)
        self.assertIsNone(stored.meeting_id)
        self._select(tab, "Uložit úkol")
        self.assertEqual(tab.table.selected_display_status(), DISPLAY_PLANNED)
        self.assertEqual(tab.table.item(self._row(tab, "Uložit úkol"), COL_LINK).text(), f"Úkol #{created[0].id}")
        self.assertIn(created[0].id, {task.id for task in task_service.get_all_tasks()})
        tab.close()

    def test_save_and_close_links_once(self) -> None:
        activity = self._activity(title="Uložit a zavřít úkol")
        tab = self._tab(2027, 3)
        self._select(tab, "Uložit a zavřít úkol")

        class SaveClose(TaskDialog):
            def exec(self):  # noqa: A003
                self._save_and_close()
                return int(self.result())

        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", SaveClose):
            tab.create_task_for_selected()
        created = self._new_tasks(before)
        self.assertEqual(len(created), 1)
        self.assertEqual(get_occurrence(activity.id, 2027, 3).task_id, created[0].id)
        tab.close()

    def test_discard_after_save_keeps_the_first_task(self) -> None:
        activity = self._activity(title="První uložení")
        tab = self._tab(2027, 3)
        self._select(tab, "První uložení")

        class DiscardLater(TaskDialog):
            def exec(self):  # noqa: A003
                self._persist()
                self.title_edit.setPlainText("Zahodit později")
                with patch(
                    "moduly.ukoly.ui.task_dialog.confirm_unsaved_editor_close",
                    return_value="discard",
                ):
                    self.reject()
                return 0

        before = self._task_ids()
        with patch("moduly.ukoly.ui.task_dialog.QMessageBox.warning"):
            with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", DiscardLater):
                tab.create_task_for_selected()
        created = self._new_tasks(before)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].title, "První uložení")
        self.assertEqual(get_occurrence(activity.id, 2027, 3).task_id, created[0].id)
        tab.close()

    def test_validation_error_does_not_link(self) -> None:
        activity = self._activity(title="Neplatný úkol")
        tab = self._tab(2027, 3)
        self._select(tab, "Neplatný úkol")

        class Invalid(TaskDialog):
            def exec(self):  # noqa: A003
                self.title_edit.setPlainText("  ")
                with patch("moduly.ukoly.ui.task_dialog.QMessageBox.warning"):
                    self._persist()
                return 0

        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", Invalid):
            tab.create_task_for_selected()
        self.assertEqual(self._task_ids(), before)
        self.assertIsNone(get_occurrence(activity.id, 2027, 3))
        tab.close()

    def test_meeting_save_links_and_close_does_not_create_another(self) -> None:
        activity = self._activity(
            title="Porada skladu",
            note="Program kontroly.",
            workplace_name="Sklad A",
        )
        tab = self._tab(2027, 4)
        self._select(tab, "Porada skladu", month=4)
        seen: dict = {}

        class SaveMeeting(MeetingDialog):
            def exec(self):  # noqa: A003
                seen["title"] = self.title_edit.text()
                seen["location"] = self.location_edit.display_text()
                seen["agenda"] = self.agenda_edit.toPlainText()
                seen["start"] = self.starts_at_edit.get_datetime()
                seen["organizer"] = self.organizer_selector.current_ref()
                seen["participants"] = self.participants_selector.selected_refs()
                self.starts_at_edit.set_datetime(datetime(2027, 4, 1, 9, 17))
                self._persist()
                self.title_edit.setText("Zahodit úpravu")
                self.reject()
                return 0

        before = self._meeting_ids()
        with patch("moduly.schuzky.ui.meeting_dialog.QMessageBox.warning"):
            with patch("moduly.rocni_plan.ui.yearly_plan_tab.MeetingDialog", SaveMeeting):
                tab.create_meeting_for_selected()
        created = self._new_meetings(before)
        self.assertEqual(len(created), 1)
        self.assertEqual(seen["title"], "Porada skladu")
        self.assertEqual(seen["location"], "Sklad A")
        self.assertEqual(seen["agenda"], "Program kontroly.")
        self.assertEqual(seen["start"].date(), date(2027, 4, 1))
        self.assertIsNone(seen["organizer"])
        self.assertEqual(seen["participants"], [])
        self.assertEqual(created[0].title, "Porada skladu")
        stored = get_occurrence(activity.id, 2027, 4)
        self.assertEqual(stored.meeting_id, created[0].id)
        self.assertIsNone(stored.task_id)
        self._select(tab, "Porada skladu", month=4)
        self.assertEqual(tab.table.selected_display_status(), DISPLAY_PLANNED)
        tab.close()

    def test_meeting_save_and_close_creates_one_record(self) -> None:
        activity = self._activity(title="Jedna událost")
        tab = self._tab(2027, 5)
        self._select(tab, "Jedna událost", month=5)

        class SaveClose(MeetingDialog):
            def exec(self):  # noqa: A003
                self.starts_at_edit.set_datetime(datetime(2027, 5, 1, 11, 15))
                self._save_and_close()
                return int(self.result())

        before = self._meeting_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.MeetingDialog", SaveClose):
            tab.create_meeting_for_selected()
        created = self._new_meetings(before)
        self.assertEqual(len(created), 1)
        self.assertEqual(get_occurrence(activity.id, 2027, 5).meeting_id, created[0].id)
        tab.close()

    def test_meeting_validation_error_does_not_link(self) -> None:
        activity = self._activity(title="Špatný čas")
        tab = self._tab(2027, 6)
        self._select(tab, "Špatný čas", month=6)

        class Invalid(MeetingDialog):
            def exec(self):  # noqa: A003
                starts = self.starts_at_edit.get_datetime()
                self.ends_at_edit.set_datetime(starts - timedelta(hours=2))
                with patch("moduly.schuzky.ui.meeting_dialog.QMessageBox.warning"):
                    self._persist()
                return 0

        before = self._meeting_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.MeetingDialog", Invalid):
            tab.create_meeting_for_selected()
        self.assertEqual(self._meeting_ids(), before)
        self.assertIsNone(get_occurrence(activity.id, 2027, 6))
        tab.close()

    def test_existing_link_opens_record_and_does_not_create_another(self) -> None:
        activity = self._activity(title="Už navázáno")
        task = task_service.create_task(
            title="Už navázáno",
            due_date=date(2027, 3, 12),
        )
        link_task(activity.id, original_year=2027, original_month=3, task_id=task.id)
        with self.assertRaises(CalendarOccurrenceError):
            link_meeting(
                activity.id,
                original_year=2027,
                original_month=3,
                meeting_id=1,
            )
        tab = self._tab(2027, 3)
        self._select(tab, "Už navázáno")
        self.assertEqual(tab.create_task_btn.text(), ACTION_OPEN_TASK)
        self.assertTrue(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        opened: dict = {}

        class Probe(TaskDialog):
            def __init__(self, parent=None, task=None, **kwargs):
                opened["id"] = None if task is None else task.id
                super().__init__(parent, task=task, **kwargs)

            def exec(self):  # noqa: A003
                return 0

        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", Probe):
            tab.create_task_for_selected()
        self.assertEqual(opened["id"], task.id)
        self.assertEqual(self._task_ids(), before)
        self.assertEqual(get_occurrence(activity.id, 2027, 3).task_id, task.id)
        tab.close()

    def test_missing_linked_task_warns_and_does_not_replace_it(self) -> None:
        activity = self._activity(title="Chybějící úkol")
        link_task(activity.id, original_year=2027, original_month=3, task_id=999_999)
        tab = self._tab(2027, 3)
        self._select(tab, "Chybějící úkol")
        before = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.QMessageBox.warning") as warn:
            tab.create_task_for_selected()
        self.assertIn(MISSING_LINKED_TASK_MESSAGE, warn.call_args.args)
        self.assertEqual(self._task_ids(), before)
        self.assertEqual(get_occurrence(activity.id, 2027, 3).task_id, 999_999)
        tab.close()

    def test_move_keeps_link_and_real_due_date(self) -> None:
        activity = self._activity(title="Přesouvaná revize")
        task = task_service.create_task(title="Termín uživatele", due_date=date(2027, 3, 18))
        link_task(activity.id, original_year=2027, original_month=3, task_id=task.id)
        move_occurrence(
            activity.id,
            original_year=2027,
            original_month=3,
            to_year=2027,
            to_month=5,
        )
        stored = get_occurrence(activity.id, 2027, 3)
        self.assertEqual(stored.task_id, task.id)
        self.assertEqual(stored.display_year, 2027)
        self.assertEqual(stored.display_month, 5)
        self.assertEqual(task_service.get_task_by_id(task.id).due_date, date(2027, 3, 18))
        moved = self._rows(activity.id, 2027, 5)
        self.assertEqual(len(moved), 2)
        linked = [row for row in moved if row.task_id == task.id]
        plain = [row for row in moved if row.task_id is None]
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].display_status, DISPLAY_PLANNED)
        self.assertEqual(plain[0].display_status, DISPLAY_TO_PLAN)
        self.assertEqual(self._rows(activity.id, 2027, 3), [])
        self.assertEqual(self._rows(activity.id, 2027, 4)[0].display_status, DISPLAY_TO_PLAN)

    def test_completed_task_does_not_change_plan_status(self) -> None:
        activity = self._activity(title="Dokončený úkol")
        task = task_service.create_task(title="Hotovo", due_date=date(2027, 3, 2))
        link_task(activity.id, original_year=2027, original_month=3, task_id=task.id)
        task_service.mark_completed(task.id)
        row = self._rows(activity.id, 2027, 3)[0]
        self.assertEqual(row.display_status, DISPLAY_PLANNED)
        self.assertEqual(row.task_id, task.id)
        self.assertTrue(task_service.get_task_by_id(task.id).completed)

    def test_history_stays_done_and_other_occurrence_stays_open(self) -> None:
        activity = self._activity(title="S historií", due=date(2027, 4, 20))
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2027, 4, 21),
        )
        april = self._rows(activity.id, 2027, 4)
        self.assertEqual(len(april), 1)
        self.assertEqual(april[0].display_status, DISPLAY_DONE)
        self.assertFalse(april[0].calendar_managed)
        may = self._rows(activity.id, 2027, 5)
        self.assertEqual(may[0].display_status, DISPLAY_TO_PLAN)
        tab = self._tab(2027, 4)
        self._select(tab, "S historií", month=4)
        self.assertFalse(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        tab.close()

    def test_skipped_occurrence_cannot_be_linked(self) -> None:
        activity = self._activity(title="Vynechaná")
        skip_occurrence(
            activity.id,
            original_year=2027,
            original_month=3,
            reason="Nebude se konat.",
        )
        with self.assertRaises(CalendarOccurrenceError):
            link_task(activity.id, original_year=2027, original_month=3, task_id=1)
        self.assertIsNone(get_occurrence(activity.id, 2027, 3).task_id)

    def test_manual_task_and_meeting_still_link_without_a_second_record(self) -> None:
        item = yearly_plan_service.create(year=2027, month=8, title="Ruční položka")
        tab = self._tab(2027, 8)
        self._select(tab, "Ruční položka")

        class NoSave(TaskDialog):
            def exec(self):  # noqa: A003
                self.reject()
                return 0

        before_tasks = self._task_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", NoSave):
            tab.create_task_for_selected()
        self.assertEqual(self._task_ids(), before_tasks)
        self.assertIsNone(yearly_plan_service.get_by_id(item.id).task_id)

        class SaveTask(TaskDialog):
            def exec(self):  # noqa: A003
                self._save_and_close()
                return int(self.result())

        self._select(tab, "Ruční položka")
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.TaskDialog", SaveTask):
            tab.create_task_for_selected()
        linked = yearly_plan_service.get_by_id(item.id)
        created_tasks = self._new_tasks(before_tasks)
        self.assertEqual(len(created_tasks), 1)
        self.assertEqual(linked.task_id, created_tasks[0].id)
        self.assertEqual(
            yearly_plan_service.resolve_display_status(linked),
            DISPLAY_PLANNED,
        )

        meeting_item = yearly_plan_service.create(year=2027, month=9, title="Ruční událost")
        tab.set_year_month(2027, 9)
        self._select(tab, "Ruční událost")

        class AcceptWithoutSave(MeetingDialog):
            def exec(self):  # noqa: A003
                QDialog.accept(self)
                return int(self.result())

        before_meetings = self._meeting_ids()
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.MeetingDialog", AcceptWithoutSave):
            tab.create_meeting_for_selected()
        self.assertEqual(self._meeting_ids(), before_meetings)
        self.assertIsNone(yearly_plan_service.get_by_id(meeting_item.id).meeting_id)

        class SaveMeeting(MeetingDialog):
            def exec(self):  # noqa: A003
                self.starts_at_edit.set_datetime(datetime(2027, 9, 3, 14, 0))
                self._save_and_close()
                return int(self.result())

        self._select(tab, "Ruční událost")
        with patch("moduly.rocni_plan.ui.yearly_plan_tab.MeetingDialog", SaveMeeting):
            tab.create_meeting_for_selected()
        created = self._new_meetings(before_meetings)
        self.assertEqual(len(created), 1)
        self.assertEqual(
            yearly_plan_service.get_by_id(meeting_item.id).meeting_id,
            created[0].id,
        )
        tab.close()

    def _activity(
        self,
        *,
        title: str,
        note: str = "",
        due: date | None = None,
        workplace_id: int | None = None,
        workplace_name: str = "",
        responsible_person_id: int | None = None,
    ):
        return periodic_activity_service.create_activity(
            title=title,
            note=note,
            next_due_date=due or date(2027, 3, 1),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            place_kind=PLACE_KIND_WORKPLACE if workplace_id or workplace_name else "none",
            workplace_id=workplace_id,
            workplace_name=workplace_name,
            responsible_person_id=responsible_person_id,
            calendar_start_year=2027,
            calendar_start_month=3,
            calendar_interval_months=1,
        )

    def _tab(self, year: int, month: int) -> YearlyPlanTab:
        tab = YearlyPlanTab()
        tab.set_year_month(year, month)
        return tab

    def _row(self, tab: YearlyPlanTab, title: str) -> int:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, COL_TITLE)
            if item is not None and item.text() == title:
                return row
        self.fail(f"Řádek {title!r} nebyl nalezen.")
        return -1

    def _select(self, tab: YearlyPlanTab, title: str, *, month: int | None = None) -> None:
        current_month = None
        for row in range(tab.table.rowCount()):
            tab.table.selectRow(row)
            if tab.table.selected_is_month_header():
                current_month = tab.table.selected_header_month()
                continue
            item = tab.table.item(row, COL_TITLE)
            if item is None or item.text() != title:
                continue
            if month is not None and current_month != month:
                continue
            tab._refresh_action_buttons()
            return
        self.fail(f"Řádek {title!r} v měsíci {month} nebyl nalezen.")

    def _rows(self, activity_id: int, year: int, month: int):
        return [
            row
            for row in yearly_plan_service.list_month_rows(year, month, today=date(2027, 1, 1))
            if row.activity_id == activity_id
        ]

    def _task_ids(self) -> set[int]:
        return {task.id for task in task_service.get_all_tasks()}

    def _new_tasks(self, before: set[int]):
        return [task for task in task_service.get_all_tasks() if task.id not in before]

    def _meeting_ids(self) -> set[int]:
        return {meeting.id for meeting in meeting_service.get_all()}

    def _new_meetings(self, before: set[int]):
        return [meeting for meeting in meeting_service.get_all() if meeting.id not in before]


if __name__ == "__main__":
    unittest.main()
