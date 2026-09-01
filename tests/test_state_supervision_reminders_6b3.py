"""STATE-SUPERVISION-REMINDERS-6B3: termíny dokladů a zjištění v Připomínkách."""

from __future__ import annotations

import importlib
import inspect
import os
import unittest
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()
_NOW = datetime(2026, 6, 15, 14, 30, 0)
_TODAY = _NOW.date()
_FUTURE = _NOW + timedelta(days=10)
_PAST = _NOW - timedelta(days=5)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_STATE_SUPERVISION,
        ITEM_TYPE_TASK,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import (
        attention_item_from_state_supervision_deadline,
        count_overdue_attention_items,
        get_attention_items,
        get_state_supervision_reminder_items,
        overdue_attention_items,
    )
    from core.dashboard.state_supervision_attention import (
        deadline_item_belongs_in_attention,
        deadline_item_belongs_in_reminders,
    )
    from core.dashboard.widget_today import (
        TodayWidget,
        attention_from_link,
        attention_link,
    )
    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.statni_dozor.constants import (
        DOCUMENT_NOT_IN_ACTIVE_LIST_MESSAGE,
        FINDING_NO_LONGER_AVAILABLE_MESSAGE,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_deadline_projection import (
        KIND_DOCUMENT,
        KIND_FINDING,
        KIND_OBJECTIONS,
        KIND_PLANNED_START,
        TYPE_LABEL_DOCUMENT,
        TYPE_LABEL_FINDING,
        TYPE_LABEL_OBJECTIONS,
        TYPE_LABEL_PLANNED_START,
        document_identity,
        finding_identity,
        list_state_supervision_deadline_items,
        objections_identity,
        planned_start_identity,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.ukoly.constants import TASK_STATUS_WAITING_CHECK
    from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date
    from moduly.ukoly.sluzby.task_service import task_service


def _by_kind(items, kind: str):
    return [item for item in items if (item.open_metadata or {}).get("kind") == kind]


def _ss_attention(*, today: date = _TODAY):
    return [
        item
        for item in get_attention_items(today=today)
        if item.item_type == ITEM_TYPE_STATE_SUPERVISION
    ]


class StateSupervisionReminders6B3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _supervision(self, **fields):
        payload = {
            "authority_name": f"OIP {self.marker}",
            "workplace_name_snapshot": f"Provoz {self.marker}",
            "subject": f"Předmět {self.marker}",
        }
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _reminders_for(self, *records, today: date = _TODAY):
        wanted = {int(record.id) for record in records}
        return [
            item
            for item in get_state_supervision_reminder_items(today=today)
            if item.source_id in wanted
        ]

    def _attention_for(self, *records, today: date = _TODAY):
        wanted = {int(record.id) for record in records}
        return [item for item in _ss_attention(today=today) if item.source_id in wanted]

    def test_00_shared_mapper_same_identity_on_all_surfaces(self) -> None:
        from core.dashboard import attention_service as service_module
        from core.dashboard import state_supervision_attention as mapper_module

        self.assertIs(
            service_module.attention_item_from_state_supervision_deadline,
            mapper_module.attention_item_from_state_supervision_deadline,
        )
        row = self._supervision(planned_start_at=_PAST, objections_due_at=_TODAY)
        projected = next(
            item
            for item in list_state_supervision_deadline_items(today=_TODAY)
            if item.identity_key == planned_start_identity(row.id)
        )
        mapped = attention_item_from_state_supervision_deadline(projected)
        reminder = next(
            item
            for item in self._reminders_for(row)
            if item.identity_key == planned_start_identity(row.id)
        )
        attention = next(
            item
            for item in self._attention_for(row)
            if item.identity_key == planned_start_identity(row.id)
        )
        for item in (mapped, reminder, attention):
            self.assertEqual(item.item_type, ITEM_TYPE_STATE_SUPERVISION)
            self.assertEqual(item.source_type, ITEM_TYPE_STATE_SUPERVISION)
            self.assertEqual(item.source_id, row.id)
            self.assertEqual(item.identity_key, planned_start_identity(row.id))
            self.assertEqual(item.type_label_override, TYPE_LABEL_PLANNED_START)
            self.assertEqual(item.priority, PRIORITY_CRITICAL)
            self.assertEqual(item.open_metadata["kind"], KIND_PLANNED_START)
            self.assertEqual(item.date, _PAST.date())
        self.assertTrue(deadline_item_belongs_in_reminders(projected, _TODAY))
        self.assertTrue(deadline_item_belongs_in_attention(projected, _TODAY))

    def test_01_reminders_date_rules_for_all_kinds(self) -> None:
        start_future = self._supervision(planned_start_at=_FUTURE)
        start_today = self._supervision(planned_start_at=_NOW)
        start_past = self._supervision(planned_start_at=_PAST)
        obj_future = self._supervision(objections_due_at=_FUTURE)
        obj_today = self._supervision(objections_due_at=_NOW)
        obj_past = self._supervision(objections_due_at=_PAST)
        obj_submitted = self._supervision(
            objections_due_at=_PAST, objections_submitted_at=_NOW
        )
        doc_parent = self._supervision()
        doc_future = state_supervision_required_document_service.create_document(
            doc_parent.id, title=f"Budoucí {self.marker}", due_at=_FUTURE
        )
        doc_today = state_supervision_required_document_service.create_document(
            doc_parent.id, title=f"Dnešní {self.marker}", due_at=_NOW
        )
        doc_past = state_supervision_required_document_service.create_document(
            doc_parent.id, title=f"Starý {self.marker}", due_at=_PAST
        )
        doc_submitted = state_supervision_required_document_service.create_document(
            doc_parent.id,
            title=f"Odeslaný {self.marker}",
            due_at=_PAST,
            submitted_at=_NOW,
        )
        finding_parent = self._supervision()
        finding_future = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            finding_parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Budoucí Z {self.marker}",
            due_date=_FUTURE.date(),
        )
        finding_today = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            finding_parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Dnešní Z {self.marker}",
            due_date=_TODAY,
        )
        finding_past = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            finding_parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Staré Z {self.marker}",
            due_date=_PAST.date(),
        )
        finding_done = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            finding_parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Vypořádané {self.marker}",
            due_date=_PAST.date(),
            status=FINDING_STATUS_VYPORADANO,
        )
        cancelled = self._supervision(
            status=STATUS_CANCELLED,
            planned_start_at=_PAST,
            objections_due_at=_PAST,
        )
        state_supervision_required_document_service.create_document(
            cancelled.id, title=f"Zrušený {self.marker}", due_at=_PAST
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            cancelled.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Zrušené Z {self.marker}",
            due_date=_PAST.date(),
        )

        reminders = self._reminders_for(
            start_future,
            start_today,
            start_past,
            obj_future,
            obj_today,
            obj_past,
            obj_submitted,
            doc_parent,
            finding_parent,
            cancelled,
        )
        keys = {item.identity_key for item in reminders}
        self.assertNotIn(planned_start_identity(start_future.id), keys)
        self.assertIn(planned_start_identity(start_today.id), keys)
        self.assertIn(planned_start_identity(start_past.id), keys)
        self.assertNotIn(objections_identity(obj_future.id), keys)
        self.assertIn(objections_identity(obj_today.id), keys)
        self.assertIn(objections_identity(obj_past.id), keys)
        self.assertNotIn(objections_identity(obj_submitted.id), keys)
        self.assertNotIn(document_identity(doc_parent.id, doc_future.id), keys)
        self.assertIn(document_identity(doc_parent.id, doc_today.id), keys)
        self.assertIn(document_identity(doc_parent.id, doc_past.id), keys)
        self.assertNotIn(document_identity(doc_parent.id, doc_submitted.id), keys)
        self.assertNotIn(finding_identity(finding_parent.id, finding_future.id), keys)
        self.assertIn(finding_identity(finding_parent.id, finding_today.id), keys)
        self.assertIn(finding_identity(finding_parent.id, finding_past.id), keys)
        self.assertNotIn(finding_identity(finding_parent.id, finding_done.id), keys)
        self.assertFalse(any(item.source_id == cancelled.id for item in reminders))

        widget = TodayWidget()
        widget.refresh(today=_TODAY)
        html = widget.content.text()
        self.assertIn(TYPE_LABEL_DOCUMENT, html)
        self.assertIn(TYPE_LABEL_FINDING, html)
        self.assertIn(TYPE_LABEL_OBJECTIONS, html)
        self.assertNotIn(f"Budoucí {self.marker}", html)
        widget.close()

    def test_02_upcoming_shows_only_overdue_documents_and_findings(self) -> None:
        parent = self._supervision(planned_start_at=_FUTURE, objections_due_at=_PAST)
        future_doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"Budoucí D {self.marker}", due_at=_FUTURE
        )
        today_doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"Dnešní D {self.marker}", due_at=_NOW
        )
        past_doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"Starý D {self.marker}", due_at=_PAST
        )
        future_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Budoucí F {self.marker}",
            due_date=_FUTURE.date(),
        )
        today_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Dnešní F {self.marker}",
            due_date=_TODAY,
        )
        past_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Staré F {self.marker}",
            due_date=_PAST.date(),
        )
        items = self._attention_for(parent)
        kinds = {item.open_metadata["kind"] for item in items}
        self.assertIn(KIND_PLANNED_START, kinds)
        self.assertIn(KIND_OBJECTIONS, kinds)
        child_ids = {
            item.open_metadata.get("child_id")
            for item in items
            if item.open_metadata.get("child_id") is not None
        }
        self.assertEqual(child_ids, {past_doc.id, past_finding.id})
        self.assertNotIn(future_doc.id, child_ids)
        self.assertNotIn(today_doc.id, child_ids)
        self.assertNotIn(future_finding.id, child_ids)
        self.assertNotIn(today_finding.id, child_ids)
        overdue = overdue_attention_items(items, today=_TODAY)
        overdue_keys = {item.identity_key for item in overdue}
        self.assertIn(document_identity(parent.id, past_doc.id), overdue_keys)
        self.assertIn(finding_identity(parent.id, past_finding.id), overdue_keys)
        self.assertIn(objections_identity(parent.id), overdue_keys)
        self.assertNotIn(planned_start_identity(parent.id), overdue_keys)
        self.assertEqual(count_overdue_attention_items(items, today=_TODAY), len(overdue))
        past_doc_item = _by_kind(items, KIND_DOCUMENT)[0]
        self.assertTrue(attention_item_is_overdue(past_doc_item, today=_TODAY))
        today_reminders = {
            item.identity_key for item in self._reminders_for(parent)
        }
        self.assertIn(document_identity(parent.id, today_doc.id), today_reminders)
        self.assertIn(finding_identity(parent.id, today_finding.id), today_reminders)

    def test_03_duplicates_task_waiting_and_refresh(self) -> None:
        parent = self._supervision()
        first_doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"A {self.marker}", due_at=_PAST
        )
        second_doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"B {self.marker}", due_at=_PAST
        )
        task = task_service.create_task(
            title=f"Úkol {self.marker}",
            due_date=_TODAY,
            priority=PRIORITY_CRITICAL,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"S úkolem {self.marker}",
            due_date=_PAST.date(),
            task_id=task.id,
        )
        dangling = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Visící {self.marker}",
            due_date=_PAST.date(),
            task_id=8_001_001,
        )
        waiting = task_service.create_task(
            title=f"Kontrola {self.marker}",
            due_date=date(2026, 8, 28),
            completed=True,
            completed_date=date(2026, 8, 27),
            requires_verification=True,
            check_due_date=date(2026, 9, 11),
            priority="Vysoká",
        )
        first = [item.identity_key for item in self._reminders_for(parent)]
        second = [item.identity_key for item in self._reminders_for(parent)]
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))
        self.assertIn(document_identity(parent.id, first_doc.id), first)
        self.assertIn(document_identity(parent.id, second_doc.id), first)
        self.assertNotIn(finding_identity(parent.id, dangling.id), first)
        attention = self._attention_for(parent)
        self.assertEqual(_by_kind(attention, KIND_FINDING), [])
        task_rows = [
            item
            for item in get_attention_items(today=_TODAY)
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(task_rows), 1)
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertEqual(task_urgency_due_date(waiting), date(2026, 9, 11))

    def test_04_navigation_document_finding_and_missing_child(self) -> None:
        parent = self._supervision()
        doc = state_supervision_required_document_service.create_document(
            parent.id, title=f"Doklad {self.marker}", due_at=_PAST
        )
        inactive = state_supervision_required_document_service.create_document(
            parent.id, title=f"Neaktivní {self.marker}", due_at=_PAST
        )
        state_supervision_required_document_service.deactivate_document(inactive.id)
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Finding {self.marker}",
            due_date=_PAST.date(),
            status=FINDING_STATUS_OTEVRENE,
        )
        with patch.object(Session, "commit") as commit:
            doc_dialog = StateSupervisionEditorDialog(
                supervision_id=parent.id,
                target_tab=TAB_SUBJECT_PREPARATION,
                focus_kind=KIND_DOCUMENT,
                focus_child_id=doc.id,
            )
            self.assertEqual(
                doc_dialog.tabs.tabText(doc_dialog.tabs.currentIndex()),
                TAB_SUBJECT_PREPARATION,
            )
            self.assertEqual(doc_dialog.tabs.currentIndex(), 1)
            self.assertEqual(doc_dialog._selected_document_key(), f"db-{doc.id}")
            self.assertFalse(doc_dialog._editor.is_dirty())
            doc_dialog.close()

            finding_dialog = StateSupervisionEditorDialog(
                supervision_id=parent.id,
                target_tab=TAB_COURSE,
                focus_kind=KIND_FINDING,
                focus_child_id=finding.id,
            )
            self.assertEqual(
                finding_dialog.tabs.tabText(finding_dialog.tabs.currentIndex()),
                TAB_COURSE,
            )
            self.assertEqual(finding_dialog.tabs.currentIndex(), 2)
            self.assertEqual(finding_dialog._selected_finding_key(), f"db-{finding.id}")
            self.assertFalse(finding_dialog._editor.is_dirty())
            finding_dialog.close()

            with patch.object(QMessageBox, "information") as info:
                missing_doc = StateSupervisionEditorDialog(
                    supervision_id=parent.id,
                    target_tab=TAB_SUBJECT_PREPARATION,
                    focus_kind=KIND_DOCUMENT,
                    focus_child_id=inactive.id,
                )
                info.assert_called()
                self.assertEqual(info.call_args.args[2], DOCUMENT_NOT_IN_ACTIVE_LIST_MESSAGE)
                self.assertEqual(missing_doc.tabs.currentIndex(), 1)
                self.assertFalse(missing_doc._editor.is_dirty())
                missing_doc.close()

            with patch.object(QMessageBox, "information") as info:
                missing_finding = StateSupervisionEditorDialog(
                    supervision_id=parent.id,
                    target_tab=TAB_COURSE,
                    focus_kind=KIND_FINDING,
                    focus_child_id=9_999_444,
                )
                info.assert_called()
                self.assertEqual(
                    info.call_args.args[2], FINDING_NO_LONGER_AVAILABLE_MESSAGE
                )
                self.assertEqual(missing_finding.tabs.currentIndex(), 2)
                self.assertFalse(missing_finding._editor.is_dirty())
                missing_finding.close()
            commit.assert_not_called()

        start = self._supervision(planned_start_at=_FUTURE)
        objections = self._supervision(
            status=STATUS_CLOSED, closed_at=_NOW, objections_due_at=_PAST
        )
        start_dialog = StateSupervisionEditorDialog(
            supervision_id=start.id, target_tab=TAB_ANNOUNCEMENT
        )
        self.assertEqual(start_dialog.tabs.currentIndex(), 0)
        start_dialog.close()
        obj_dialog = StateSupervisionEditorDialog(
            supervision_id=objections.id, target_tab=TAB_CONCLUSION
        )
        self.assertEqual(obj_dialog.tabs.currentIndex(), 3)
        obj_dialog.close()

        dummy = SimpleNamespace(_open_state_supervision_by_id=MagicMock())
        item = next(
            row
            for row in self._attention_for(parent)
            if row.open_metadata.get("kind") == KIND_DOCUMENT
        )
        MainWindow._open_attention_item(dummy, item)
        dummy._open_state_supervision_by_id.assert_called_once_with(
            int(parent.id),
            target_tab=TAB_SUBJECT_PREPARATION,
            focus_kind=KIND_DOCUMENT,
            focus_child_id=doc.id,
        )

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        opened: list[tuple] = []

        class FakeDialog:
            def __init__(
                self,
                parent=None,
                *,
                supervision_id=None,
                target_tab=None,
                focus_kind=None,
                focus_child_id=None,
            ):
                opened.append((supervision_id, target_tab, focus_kind, focus_child_id))
                self.saved = False
                self.supervision_id = supervision_id

        with (
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.StateSupervisionEditorDialog",
                FakeDialog,
            ),
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
                lambda dialog: None,
            ),
        ):
            page.open_supervision(
                parent.id,
                target_tab=TAB_COURSE,
                focus_kind=KIND_FINDING,
                focus_child_id=finding.id,
            )
            self.assertEqual(
                opened[-1],
                (parent.id, TAB_COURSE, KIND_FINDING, finding.id),
            )
        page.close()

    def test_05_reminder_link_uses_identity_key(self) -> None:
        parent = self._supervision(planned_start_at=_PAST, objections_due_at=_PAST)
        items = self._reminders_for(parent)
        self.assertEqual(len(items), 2)
        start = next(item for item in items if item.open_metadata["kind"] == KIND_PLANNED_START)
        href = attention_link(start)
        self.assertIn("key:" + start.identity_key, href)
        resolved = attention_from_link(
            f"attention:key:{start.identity_key}", items
        )
        self.assertIs(resolved, start)

        widget = TodayWidget()
        widget.refresh(today=_TODAY)
        self.assertIn(start.identity_key, widget.content.text())
        widget.close()

    def test_06_collector_failures_do_not_hide_other_items(self) -> None:
        task = task_service.create_task(title=f"Ostatní {self.marker}", due_date=_TODAY)
        with patch(
            "core.dashboard.attention_service._load_state_supervision_deadline_items",
            side_effect=RuntimeError("projekce selhala"),
        ):
            items = get_attention_items(today=_TODAY)
            reminders = get_state_supervision_reminder_items(today=_TODAY)
            widget = TodayWidget()
            widget.refresh(today=_TODAY)
            html = widget.content.text()
            widget.close()
        self.assertTrue(
            any(item.item_type == ITEM_TYPE_TASK and item.source_id == task.id for item in items)
        )
        self.assertEqual(reminders, [])
        self.assertFalse(any(item.item_type == ITEM_TYPE_STATE_SUPERVISION for item in items))
        self.assertIn(f"Ostatní {self.marker}", html)

    def test_07_constant_queries_no_task_n_plus_one(self) -> None:
        first = self._supervision(planned_start_at=_PAST)
        second = self._supervision(objections_due_at=_PAST)
        state_supervision_required_document_service.create_document(
            first.id, title="D1", due_at=_PAST
        )
        state_supervision_required_document_service.create_document(
            second.id, title="D2", due_at=_NOW
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            first.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="F1",
            due_date=_PAST.date(),
        )
        supervision_calls: list[int] = []
        document_calls: list[list[int]] = []
        finding_calls: list[list[int]] = []

        def load_supervisions():
            supervision_calls.append(1)
            return list(state_supervision_service.list_supervisions())

        def load_documents(ids):
            document_calls.append(list(ids))
            return state_supervision_required_document_service.list_for_supervisions(ids)

        def load_findings(ids):
            finding_calls.append(list(ids))
            return finding_service.get_for_entities(ENTITY_STATE_SUPERVISION, list(ids))

        with (
            patch.object(task_service, "get_tasks_by_ids", side_effect=AssertionError("Task query")),
            patch(
                "moduly.statni_dozor.sluzby.state_supervision_deadline_projection._default_load_supervisions",
                load_supervisions,
            ),
            patch(
                "moduly.statni_dozor.sluzby.state_supervision_deadline_projection._default_load_documents",
                load_documents,
            ),
            patch(
                "moduly.statni_dozor.sluzby.state_supervision_deadline_projection._default_load_findings",
                load_findings,
            ),
        ):
            get_attention_items(today=_TODAY)
            get_state_supervision_reminder_items(today=_TODAY)
        self.assertEqual(supervision_calls, [1, 1])
        self.assertEqual(len(document_calls), 2)
        self.assertEqual(len(finding_calls), 2)

    def test_08_agenda_calendar_untouched_and_tab_counts(self) -> None:
        from core.dashboard import widget_calendar_placeholder
        from moduly.agenda.sluzby import agenda_service as agenda_module

        self.assertNotIn("state_supervision", inspect.getsource(agenda_module))
        self.assertNotIn("state_supervision", inspect.getsource(widget_calendar_placeholder))
        self.assertIn(
            "get_state_supervision_reminder_items",
            inspect.getsource(TodayWidget.refresh),
        )
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        page.close()
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 5)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
