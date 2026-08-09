"""AGENDA-PERIOD-2b: UI periodických činností v Agendě."""

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

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import (
        NEXT_FROM_PLANNED,
        PLACE_KIND_NONE,
        PLACE_KIND_ORGANIZATION,
        PLACE_KIND_OTHER,
        PLACE_KIND_WORKPLACE,
        TAB_PERIODIC,
        TAB_TASKS_MEETINGS,
        UNIT_MONTHS,
        UNIT_YEARS,
        format_place,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activities_tab import PeriodicActivitiesTab
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import PeriodicActivityDialog
    from moduly.periodicke_cinnosti.ui.periodic_performance_dialog import (
        PeriodicPerformanceDialog,
    )


class AgendaPeriod2bTestCase(unittest.TestCase):
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
        self.worker = settings_service.save_worker(
            first_name="Jana",
            last_name="Odpovědná",
            position="Technik BOZP",
        )
        self.workplace = settings_service.save_workplace(name="Provoz Alfa")

    def test_agenda_has_two_tabs(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 2)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_PERIODIC)
        self.assertIsInstance(page.periodic_tab, PeriodicActivitiesTab)
        self.assertTrue(hasattr(page, "table"))
        self.assertTrue(hasattr(page, "new_task_btn"))
        page.close()

    def test_create_edit_and_deactivate(self) -> None:
        created = periodic_activity_service.create_activity(
            title="Roční revize",
            place_kind=PLACE_KIND_WORKPLACE,
            workplace_id=self.workplace.id,
            responsible_person_id=self.worker.id,
            next_due_date=date(2026, 6, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=30,
            notify_unit=UNIT_MONTHS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        self.assertEqual(created.workplace_name, "Provoz Alfa")
        self.assertEqual(created.responsible_person_name, self.worker.display_name)

        updated = periodic_activity_service.update_activity(
            created.id,
            title="Roční revize – upraveno",
            place_kind=PLACE_KIND_ORGANIZATION,
            next_due_date=date(2026, 6, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=14,
            notify_unit="days",
            next_from=NEXT_FROM_PLANNED,
            active=False,
            responsible_person_id=self.worker.id,
        )
        self.assertEqual(updated.title, "Roční revize – upraveno")
        self.assertFalse(updated.active)
        self.assertEqual(updated.place_kind, PLACE_KIND_ORGANIZATION)

        tab = PeriodicActivitiesTab()
        tab.show_inactive.setChecked(False)
        tab.refresh()
        from PySide6.QtCore import Qt

        visible_ids = {
            tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
        }
        self.assertNotIn(created.id, visible_ids)

        tab.show_inactive.setChecked(True)
        tab.refresh()
        visible_ids = {
            tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(tab.table.rowCount())
        }
        self.assertIn(created.id, visible_ids)
        tab.close()

    def test_place_kinds_display(self) -> None:
        wp = periodic_activity_service.create_activity(
            title="WP",
            place_kind=PLACE_KIND_WORKPLACE,
            workplace_id=self.workplace.id,
            next_due_date=date(2026, 1, 1),
        )
        org = periodic_activity_service.create_activity(
            title="ORG",
            place_kind=PLACE_KIND_ORGANIZATION,
            next_due_date=date(2026, 1, 1),
        )
        other = periodic_activity_service.create_activity(
            title="OTHER",
            place_kind=PLACE_KIND_OTHER,
            place_text="Laboratoř XY",
            next_due_date=date(2026, 1, 1),
        )
        none = periodic_activity_service.create_activity(
            title="NONE",
            place_kind=PLACE_KIND_NONE,
            next_due_date=date(2026, 1, 1),
        )
        self.assertEqual(format_place(wp), "Provoz Alfa")
        self.assertEqual(format_place(org), "Celá organizace")
        self.assertEqual(format_place(other), "Laboratoř XY")
        self.assertEqual(format_place(none), "Bez určení místa")

    def test_dialog_loads_and_saves(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Editor test",
            place_kind=PLACE_KIND_OTHER,
            place_text="Venkovní areál",
            responsible_person_id=self.worker.id,
            next_due_date=date(2026, 9, 1),
            repeat_every=6,
            repeat_unit=UNIT_MONTHS,
            active=True,
        )
        dialog = PeriodicActivityDialog(activity=activity)
        self.assertEqual(dialog.title_edit.text(), "Editor test")
        self.assertEqual(dialog.place_text.text(), "Venkovní areál")
        self.assertEqual(dialog.responsible_selector.current_person_id(), self.worker.id)
        dialog.title_edit.setText("Editor test 2")
        self.assertTrue(dialog._editor._run_save())
        reloaded = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(reloaded.title, "Editor test 2")
        dialog._editor._closing = True
        dialog.close()

    def test_perform_updates_next_due_and_history(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Provedení test",
            next_due_date=date(2026, 6, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            performed_by_kind="thp",
            performed_by_id=self.worker.id,
            result_note="OK",
        )
        reloaded = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(reloaded.next_due_date, date(2027, 6, 1))
        history = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, occurrence.id)
        self.assertEqual(history[0].result_note, "OK")
        self.assertEqual(history[0].performed_by_name, self.worker.display_name)

        dialog = PeriodicActivityDialog(activity=reloaded)
        self.assertEqual(dialog.history_table.rowCount(), 1)
        self.assertIn("OK", dialog.history_table.item(0, 3).text())
        dialog._editor._closing = True
        dialog.close()

    def test_perform_button_requires_active_selection(self) -> None:
        active = periodic_activity_service.create_activity(
            title="Aktivní položka",
            next_due_date=date(2026, 6, 1),
            active=True,
        )
        inactive = periodic_activity_service.create_activity(
            title="Neaktivní položka",
            next_due_date=date(2026, 6, 1),
            active=False,
        )
        tab = PeriodicActivitiesTab()
        tab.show_inactive.setChecked(True)
        tab.refresh()
        from PySide6.QtCore import Qt

        for row in range(tab.table.rowCount()):
            if tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == active.id:
                tab.table.selectRow(row)
                break
        tab._refresh_action_buttons()
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.perform_btn.isEnabled())

        for row in range(tab.table.rowCount()):
            if tab.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == inactive.id:
                tab.table.selectRow(row)
                break
        tab._refresh_action_buttons()
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertFalse(tab.perform_btn.isEnabled())
        tab.close()

    def test_performance_dialog_get_data(self) -> None:
        dialog = PeriodicPerformanceDialog(activity_title="X")
        data = dialog.get_data()
        self.assertIsInstance(data["performed_at"], date)
        self.assertIn(data["performed_by_kind"], ("thp", "person", "external"))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
