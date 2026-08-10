"""AGENDA-2: sjednocení vstupu k úkolům a událostem."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

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

    from core.dashboard.attention_item import ITEM_TYPE_MEETING, ITEM_TYPE_TASK
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import (
        MODULE_NAME,
        STATUS_MODE_ACTIVE,
    )
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


def _sidebar_button_texts(window: MainWindow) -> list[str]:
    scroll = window.findChild(QScrollArea, "SidebarScroll")
    assert scroll is not None
    frame = scroll.widget()
    assert frame is not None
    return [btn.text() for btn in frame.findChildren(QPushButton)]


class Agenda2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def test_dashboard_has_agenda_button(self) -> None:
        dashboard = self.window._page_widgets["dashboard"]
        upcoming = dashboard.upcoming
        self.assertEqual(upcoming.agenda_button.text(), "Agenda")
        self.assertEqual(upcoming.title_label.text(), "Nadcházející události a úkoly")

    def test_agenda_opens_from_dashboard(self) -> None:
        self.window._show("dashboard")
        dashboard = self.window._page_widgets["dashboard"]
        dashboard.upcoming.agenda_button.click()
        current = self.window.current_page_widget()
        self.assertIsInstance(current, AgendaPage)

        page = self.window._page_widgets["agenda"]
        for check in page.type_checks.values():
            self.assertTrue(check.isChecked())
        self.assertEqual(page.status_filter.currentText(), STATUS_MODE_ACTIVE)

    def test_no_tasks_or_events_buttons_on_panel(self) -> None:
        dashboard = self.window._page_widgets["dashboard"]
        texts = [
            btn.text()
            for btn in dashboard.upcoming.findChildren(QPushButton)
        ]
        self.assertIn("Agenda", texts)
        self.assertNotIn("Úkoly", texts)
        self.assertNotIn("Události", texts)

    def test_sidebar_has_agenda_without_tasks_and_events(self) -> None:
        texts = _sidebar_button_texts(self.window)
        self.assertIn(MODULE_NAME, texts)
        self.assertNotIn("Úkoly", texts)
        self.assertNotIn("Události", texts)
        # moduly zůstávají načtené
        self.assertIn("ukoly", self.window._page_widgets)
        self.assertIn("schuzky", self.window._page_widgets)

    def test_quick_create_task(self) -> None:
        created: list[int] = []
        original = task_service.create_task

        def _create(**kwargs):
            task = original(**kwargs)
            created.append(task.id)
            return task

        class _FakeTaskDialog:
            def __init__(self, parent=None, task=None, **kwargs):
                self.task = task

            def exec(self):
                self.task = task_service.create_task(
                    title="Rychlý úkol AGENDA-2",
                    description="",
                    priority="Normální",
                    due_date=date.today() + timedelta(days=2),
                )
                return True

        with patch.object(task_service, "create_task", side_effect=_create):
            with patch(
                "moduly.ukoly.ui.task_dialog.TaskDialog",
                _FakeTaskDialog,
            ):
                self.window._open_new_task()

        self.assertEqual(len(created), 1)
        agenda = self.window._page_widgets["agenda"]
        agenda.apply_workspace_filters()
        found = any(
            agenda.table.item(row, 0).data(Qt.ItemDataRole.UserRole).source_id
            == created[0]
            for row in range(agenda.table.rowCount())
        )
        self.assertTrue(found)

    def test_quick_create_meeting(self) -> None:
        created: list[int] = []
        original = meeting_service.create_meeting

        def _create(**kwargs):
            meeting = original(**kwargs)
            created.append(meeting.id)
            return meeting

        with patch.object(meeting_service, "create_meeting", side_effect=_create):
            with patch(
                "core.widgets.dialog_utils.exec_maximized",
                return_value=True,
            ):
                with patch(
                    "moduly.schuzky.ui.meeting_dialog.MeetingDialog.get_data",
                    return_value={
                        "title": "Rychlá událost AGENDA-2",
                        "event_type": "Schůzka",
                        "starts_at": datetime.now() + timedelta(days=3),
                        "ends_at": None,
                        "location": "",
                        "organizer_person_id": None,
                        "participant_ids": [],
                        "agenda": "",
                        "status": STATUS_PLANNED,
                        "proceedings": "",
                        "conclusions": "",
                        "notes": "",
                    },
                ):
                    with patch(
                        "moduly.schuzky.ui.meeting_dialog.MeetingDialog.get_agenda_items",
                        return_value=[],
                    ):
                        self.window._open_new_meeting()

        self.assertEqual(len(created), 1)
        agenda = self.window._page_widgets["agenda"]
        agenda.apply_workspace_filters()
        found = any(
            agenda.table.item(row, 0).data(Qt.ItemDataRole.UserRole).source_id
            == created[0]
            for row in range(agenda.table.rowCount())
        )
        self.assertTrue(found)

    def test_double_click_opens_editor_by_type(self) -> None:
        task = task_service.create_task(
            title="Dvojklik úkol",
            due_date=date.today() + timedelta(days=1),
        )
        meeting = meeting_service.create_meeting(
            title="Dvojklik událost",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
        )
        opened: list[tuple[str, int]] = []

        def on_open(item) -> None:
            opened.append((item.item_type, item.source_id))

        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        widget.refresh()

        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and payload.item_type == ITEM_TYPE_TASK
                and payload.source_id == task.id
            ):
                widget.table.selectRow(row)
                widget._open_selected()
                break
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and payload.item_type == ITEM_TYPE_MEETING
                and payload.source_id == meeting.id
            ):
                widget.table.selectRow(row)
                widget._open_selected()
                break

        self.assertEqual(
            opened,
            [(ITEM_TYPE_TASK, task.id), (ITEM_TYPE_MEETING, meeting.id)],
        )

    def test_refresh_after_save(self) -> None:
        dashboard = self.window._page_widgets["dashboard"]
        agenda = self.window._page_widgets["agenda"]
        refreshed: list[str] = []

        original_dash = dashboard.refresh
        original_agenda = agenda.refresh

        def _dash() -> None:
            refreshed.append("dashboard")
            original_dash()

        def _agenda() -> None:
            refreshed.append("agenda")
            original_agenda()

        with patch.object(dashboard, "refresh", side_effect=_dash):
            with patch.object(agenda, "refresh", side_effect=_agenda):
                with patch(
                    "moduly.ukoly.ui.task_dialog.TaskDialog.exec",
                    return_value=False,
                ):
                    self.window._open_new_task()

        self.assertIn("dashboard", refreshed)
        self.assertIn("agenda", refreshed)

    def test_quick_buttons_labels(self) -> None:
        dashboard = DashboardPage()
        texts = [
            btn.text()
            for btn in dashboard.findChildren(QPushButton)
            if btn.objectName() == "QuickButton"
        ]
        self.assertIn("Nový úkol", texts)
        self.assertIn("Nová událost", texts)


if __name__ == "__main__":
    unittest.main()
