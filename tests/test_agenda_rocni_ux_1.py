"""AGENDA-ROCNI-UX-1: dashboard Co hoří, ikony a neuložené změny Události."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
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

    from core.dashboard.attention_item import ITEM_TYPE_YEARLY_PLAN_MONTH
    from core.dashboard.attention_service import (
        get_attention_items,
        get_yearly_plan_month_reminder_items,
    )
    from core.dashboard.widget_today import (
        TodayWidget,
        overdue_yearly_plan_month_items,
    )
    from core.widgets.editor_dialog_controller import (
        EDITOR_UNSAVED_PROMPT,
        confirm_unsaved_editor_close,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activities_tab import (
        PeriodicActivitiesTab,
    )
    from moduly.rocni_plan.constants import (
        ACTION_CANCEL,
        ACTION_CREATE_MEETING,
        ACTION_CREATE_TASK,
        ACTION_EDIT,
        ACTION_MARK_MONTH_PROCESSED,
        ACTION_MOVE,
        ACTION_NEW,
        month_planning_attention_title,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.schuzky.constants import DIALOG_WINDOW_TITLE
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class AgendaRocniUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for year in range(2025, 2032):
            for month in range(1, 13):
                yearly_plan_service.month_status_repository.delete_for_month(
                    year, month
                )

    def test_overdue_month_attention_appears_in_co_hori(self) -> None:
        today = date(2026, 8, 9)  # po prvním pracovním dni 3. 8.
        items = overdue_yearly_plan_month_items(today)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_type, ITEM_TYPE_YEARLY_PLAN_MONTH)
        self.assertEqual(
            items[0].title,
            month_planning_attention_title(2026, 8),
        )

        widget = TodayWidget()
        widget.refresh(today=today)
        text = widget.content.text()
        self.assertIn("Zpracovat úkoly měsíce – srpen 2026", text)
        self.assertIn("🔴", text)
        self.assertIn("03.08.2026", text)
        widget.close()

    def test_month_processed_removes_from_co_hori_and_upcoming(self) -> None:
        today = date(2026, 8, 9)
        self.assertEqual(len(overdue_yearly_plan_month_items(today)), 1)
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
                for item in get_yearly_plan_month_reminder_items(today=today)
            )
        )

        yearly_plan_service.mark_month_processed(
            2026,
            8,
            processed_at=datetime(2026, 8, 9, 10, 0, 0),
        )

        self.assertEqual(overdue_yearly_plan_month_items(today), [])
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
                for item in get_yearly_plan_month_reminder_items(today=today)
            )
        )
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
                for item in get_attention_items(today=today)
            )
        )

        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertNotIn("Zpracovat úkoly měsíce – srpen 2026", widget.content.text())
        widget.close()

    def test_due_today_month_is_in_pripominky(self) -> None:
        today = date(2026, 8, 3)  # první pracovní den = termín
        self.assertEqual(len(overdue_yearly_plan_month_items(today)), 1)
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
                for item in get_attention_items(today=today)
            )
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        text = widget.content.text()
        self.assertIn("Zpracovat úkoly měsíce – srpen 2026", text)
        self.assertIn("🔵", text)
        widget.close()

    def test_yearly_plan_toolbar_buttons_are_text_only(self) -> None:
        tab = YearlyPlanTab()
        buttons = {
            ACTION_NEW: tab.new_btn,
            ACTION_EDIT: tab.edit_btn,
            ACTION_CREATE_TASK: tab.create_task_btn,
            ACTION_CREATE_MEETING: tab.create_meeting_btn,
            ACTION_MOVE: tab.move_btn,
            ACTION_CANCEL: tab.cancel_btn,
            ACTION_MARK_MONTH_PROCESSED: tab.mark_month_btn,
        }
        for label, button in buttons.items():
            self.assertEqual(button.text(), label)
            self.assertTrue(button.icon().isNull(), msg=f"Neočekávaná ikona: {label}")
        tab.close()

    def test_periodic_toolbar_buttons_are_text_only(self) -> None:
        tab = PeriodicActivitiesTab()
        for button in (tab.new_btn, tab.edit_btn, tab.perform_btn):
            self.assertTrue(button.text())
            self.assertTrue(button.icon().isNull(), msg=button.text())
        tab.close()

    def test_unsaved_prompt_matches_standard_dialog(self) -> None:
        with patch(
            "core.widgets.editor_dialog_controller.QMessageBox"
        ) as mock_box_cls:
            instance = mock_box_cls.return_value
            instance.clickedButton.return_value = None
            instance.exec.return_value = 0
            confirm_unsaved_editor_close(None, title="Editor")
            instance.setText.assert_called_once_with(EDITOR_UNSAVED_PROMPT)
            instance.setIcon.assert_called()

    def test_meeting_dialog_visible_close_prompts(self) -> None:
        """X na zobrazeném editoru musí nabídnout uložení změn."""
        dialog = MeetingDialog()
        dialog.title_edit.setText("Rozpracovaná událost")
        dialog.show()
        self.assertTrue(dialog.isVisible())
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            from PySide6.QtGui import QCloseEvent

            blocked = dialog._editor.eventFilter(dialog, QCloseEvent())
            self.assertTrue(blocked)
            prompt.assert_called_once()
        dialog.hide()
        dialog._editor.force_close()

    def test_meeting_dialog_discard_closes_without_accept(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Zahodit")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)
        dialog._editor.force_close()

    def test_meeting_dialog_save_from_prompt_accepts(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Uložit z promptu")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            self.assertTrue(dialog._editor.request_close())
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
