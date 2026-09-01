"""STATE-SUPERVISION-UPCOMING-6B2: plánované kontroly a námitky v Nadcházejících."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
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
        SOURCE_LABEL_STATE_SUPERVISION,
        TYPE_LABELS,
        attention_item_identity,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import (
        attention_item_from_state_supervision_deadline,
        count_overdue_attention_items,
        get_attention_items,
        overdue_attention_items,
    )
    from core.dashboard.widget_upcoming_tasks import COL_TYPE, UpcomingTasksWidget
    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.statni_dozor.constants import (
        ITEM_NOT_FOUND_MESSAGE,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_CONCLUSION,
        TAB_STATE_SUPERVISION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_deadline_projection import (
        KIND_DOCUMENT,
        KIND_FINDING,
        KIND_OBJECTIONS,
        KIND_PLANNED_START,
        TYPE_LABEL_OBJECTIONS,
        TYPE_LABEL_PLANNED_START,
        StateSupervisionDeadlineItem,
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


def _count(table: str) -> int:
    db_path = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _ss_items(items=None, *, today: date | None = _TODAY):
    items = items if items is not None else get_attention_items(today=today)
    return [item for item in items if item.item_type == ITEM_TYPE_STATE_SUPERVISION]


def _by_kind(items, kind: str):
    return [item for item in items if (item.open_metadata or {}).get("kind") == kind]


def _projected(
    *,
    kind: str,
    supervision_id: int = 11,
    child_id: int | None = None,
    title: str = "OIP – Provoz",
    type_label: str = TYPE_LABEL_PLANNED_START,
    due_date: date = _TODAY,
    event_at: datetime | None = _NOW,
    target_tab: str = TAB_ANNOUNCEMENT,
    include_in_upcoming: bool = True,
    identity_key: str = "ss:11:start",
    detail: str = "OIP – Provoz",
) -> StateSupervisionDeadlineItem:
    return StateSupervisionDeadlineItem(
        identity_key=identity_key,
        supervision_id=supervision_id,
        kind=kind,
        child_id=child_id,
        title=title,
        type_label=type_label,
        due_date=due_date,
        event_at=event_at,
        priority=PRIORITY_CRITICAL,
        target_tab=target_tab,
        include_in_upcoming=include_in_upcoming,
        include_in_reminders=True,
        detail=detail,
    )


class StateSupervisionUpcoming6B2TestCase(unittest.TestCase):
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

    def test_00_single_item_type_and_mapping_fields(self) -> None:
        self.assertEqual(TYPE_LABELS[ITEM_TYPE_STATE_SUPERVISION], "Státní dozor")
        self.assertNotIn("planned_start", TYPE_LABELS)
        self.assertNotIn("objections", TYPE_LABELS)
        self.assertNotIn("document", TYPE_LABELS)
        self.assertNotIn("finding", TYPE_LABELS)

        start = attention_item_from_state_supervision_deadline(
            _projected(kind=KIND_PLANNED_START)
        )
        objections = attention_item_from_state_supervision_deadline(
            _projected(
                kind=KIND_OBJECTIONS,
                identity_key="ss:11:objections",
                type_label=TYPE_LABEL_OBJECTIONS,
                target_tab=TAB_CONCLUSION,
                title="Námitky – OIP – Provoz",
            )
        )
        for item, kind, label, tab, key in (
            (
                start,
                KIND_PLANNED_START,
                TYPE_LABEL_PLANNED_START,
                TAB_ANNOUNCEMENT,
                "ss:11:start",
            ),
            (
                objections,
                KIND_OBJECTIONS,
                TYPE_LABEL_OBJECTIONS,
                TAB_CONCLUSION,
                "ss:11:objections",
            ),
        ):
            self.assertEqual(item.item_type, ITEM_TYPE_STATE_SUPERVISION)
            self.assertEqual(item.source_type, ITEM_TYPE_STATE_SUPERVISION)
            self.assertEqual(item.source_id, 11)
            self.assertEqual(item.identity_key, key)
            self.assertEqual(item.type_label_override, label)
            self.assertEqual(item.type_label, label)
            self.assertEqual(item.priority, PRIORITY_CRITICAL)
            self.assertEqual(item.date, _TODAY)
            self.assertEqual(item.event_at, _NOW)
            self.assertEqual(item.subtitle, SOURCE_LABEL_STATE_SUPERVISION)
            self.assertEqual(item.open_metadata["kind"], kind)
            self.assertEqual(item.open_metadata["target_tab"], tab)
            self.assertEqual(item.open_metadata["supervision_id"], 11)
            self.assertNotIn("child_id", item.open_metadata)
            self.assertFalse(hasattr(item, "_sa_instance_state"))

        with_child = attention_item_from_state_supervision_deadline(
            _projected(
                kind=KIND_DOCUMENT,
                child_id=44,
                identity_key="ss:11:doc:44",
                include_in_upcoming=False,
            )
        )
        self.assertEqual(with_child.open_metadata["child_id"], 44)
        self.assertNotEqual(
            attention_item_identity(start),
            attention_item_identity(objections),
        )

    def test_01_upcoming_keeps_start_and_objections_drops_document_finding(self) -> None:
        row = self._supervision(
            planned_start_at=_FUTURE,
            objections_due_at=_PAST,
        )
        doc = state_supervision_required_document_service.create_document(
            row.id, title=f"Spis {self.marker}", due_at=_FUTURE
        )
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            row.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Zjištění {self.marker}",
            due_date=_FUTURE.date(),
            status=FINDING_STATUS_OTEVRENE,
        )
        items = [
            item
            for item in _ss_items()
            if item.source_id == row.id
        ]
        kinds = {item.open_metadata["kind"] for item in items}
        self.assertEqual(kinds, {KIND_PLANNED_START, KIND_OBJECTIONS})
        self.assertNotIn(KIND_DOCUMENT, kinds)
        self.assertNotIn(KIND_FINDING, kinds)
        self.assertTrue(all(item.identity_key for item in items))
        start = _by_kind(items, KIND_PLANNED_START)[0]
        objections = _by_kind(items, KIND_OBJECTIONS)[0]
        self.assertEqual(start.identity_key, planned_start_identity(row.id))
        self.assertEqual(objections.identity_key, objections_identity(row.id))
        self.assertEqual(start.event_at, _FUTURE)
        self.assertEqual(objections.event_at, _PAST)
        self.assertNotEqual(start.identity_key, objections.identity_key)
        self.assertIsNone(next((i for i in items if i.open_metadata.get("child_id") == doc.id), None))
        self.assertIsNone(
            next((i for i in items if i.open_metadata.get("child_id") == finding.id), None)
        )

    def test_02_planned_start_visibility_and_dates(self) -> None:
        future_row = self._supervision(planned_start_at=_FUTURE)
        today_row = self._supervision(
            authority_name=f"KHS {self.marker}",
            planned_start_at=_NOW.replace(hour=8, minute=0),
        )
        past_row = self._supervision(
            authority_name=f"HZS {self.marker}",
            planned_start_at=_PAST,
        )
        hidden = [
            self._supervision(),
            self._supervision(planned_start_at=_FUTURE, started_at=_NOW),
            self._supervision(
                planned_start_at=_FUTURE, started_at=_PAST, ended_at=_NOW
            ),
            self._supervision(
                planned_start_at=_FUTURE, status=STATUS_CLOSED, closed_at=_NOW
            ),
            self._supervision(planned_start_at=_FUTURE, status=STATUS_CANCELLED),
            self._supervision(started_at=_NOW, status=STATUS_ANNOUNCED),
        ]
        wanted = {future_row.id, today_row.id, past_row.id, *(row.id for row in hidden)}
        items = [
            item
            for item in _by_kind(_ss_items(), KIND_PLANNED_START)
            if item.source_id in wanted
        ]
        by_id = {item.source_id: item for item in items}
        self.assertEqual(set(by_id), {future_row.id, today_row.id, past_row.id})
        for row in hidden:
            self.assertNotIn(row.id, by_id)
        self.assertEqual(by_id[future_row.id].date, _FUTURE.date())
        self.assertEqual(by_id[today_row.id].date, _TODAY)
        self.assertEqual(by_id[past_row.id].date, _PAST.date())
        self.assertFalse(attention_item_is_overdue(by_id[today_row.id], today=_TODAY))
        self.assertTrue(attention_item_is_overdue(by_id[past_row.id], today=_TODAY))
        self.assertFalse(
            attention_item_is_overdue(
                by_id[today_row.id],
                today=_TODAY,
            )
        )
        titles = " ".join(item.title for item in items)
        self.assertNotIn("Probíhá", titles)

    def test_03_objections_visibility_including_closed(self) -> None:
        future_row = self._supervision(objections_due_at=_FUTURE)
        today_row = self._supervision(objections_due_at=_NOW)
        past_row = self._supervision(objections_due_at=_PAST)
        submitted = self._supervision(
            objections_due_at=_PAST, objections_submitted_at=_NOW
        )
        missing = self._supervision()
        closed = self._supervision(
            status=STATUS_CLOSED,
            closed_at=_NOW,
            objections_due_at=_PAST,
        )
        cancelled = self._supervision(
            status=STATUS_CANCELLED,
            objections_due_at=_PAST,
        )
        wanted = {
            future_row.id,
            today_row.id,
            past_row.id,
            submitted.id,
            missing.id,
            closed.id,
            cancelled.id,
        }
        items = [
            item
            for item in _by_kind(_ss_items(), KIND_OBJECTIONS)
            if item.source_id in wanted
        ]
        ids = {item.source_id for item in items}
        self.assertEqual(ids, {future_row.id, today_row.id, past_row.id, closed.id})
        self.assertNotIn(submitted.id, ids)
        self.assertNotIn(missing.id, ids)
        self.assertNotIn(cancelled.id, ids)
        past_item = next(item for item in items if item.source_id == past_row.id)
        self.assertEqual(past_item.type_label, TYPE_LABEL_OBJECTIONS)
        self.assertTrue(attention_item_is_overdue(past_item, today=_TODAY))
        today_item = next(item for item in items if item.source_id == today_row.id)
        self.assertFalse(attention_item_is_overdue(today_item, today=_TODAY))

    def test_04_overdue_card_counts_calendar_day_separately(self) -> None:
        past_start = self._supervision(planned_start_at=_PAST)
        today_start = self._supervision(
            authority_name=f"KHS {self.marker}",
            planned_start_at=_NOW.replace(hour=7, minute=0),
        )
        past_obj = self._supervision(objections_due_at=_PAST)
        today_obj = self._supervision(
            authority_name=f"HZS {self.marker}",
            objections_due_at=_NOW.replace(hour=23, minute=59),
        )
        wanted_ids = {past_start.id, today_start.id, past_obj.id, today_obj.id}
        ss = [item for item in _ss_items() if item.source_id in wanted_ids]
        overdue = overdue_attention_items(ss, today=_TODAY)
        overdue_ids = {item.identity_key for item in overdue}
        self.assertIn(planned_start_identity(past_start.id), overdue_ids)
        self.assertIn(objections_identity(past_obj.id), overdue_ids)
        self.assertNotIn(planned_start_identity(today_start.id), overdue_ids)
        self.assertNotIn(objections_identity(today_obj.id), overdue_ids)
        self.assertEqual(count_overdue_attention_items(ss, today=_TODAY), 2)
        self.assertEqual(count_overdue_attention_items(ss, today=_TODAY), len(overdue))

    def test_05_no_identity_merge_and_refresh_without_duplicates(self) -> None:
        row = self._supervision(planned_start_at=_FUTURE, objections_due_at=_FUTURE)
        first = [item.identity_key for item in _ss_items() if item.source_id == row.id]
        second = [item.identity_key for item in _ss_items() if item.source_id == row.id]
        self.assertEqual(len(first), 2)
        self.assertEqual(set(first), {planned_start_identity(row.id), objections_identity(row.id)})
        self.assertEqual(first, second)
        other = self._supervision(
            authority_name=f"KHS {self.marker}",
            planned_start_at=_FUTURE,
        )
        keys = [item.identity_key for item in _ss_items() if item.source_id in {row.id, other.id}]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 3)

    def test_06_finding_with_task_is_only_task_row(self) -> None:
        parent = self._supervision()
        due = date.today() + timedelta(days=4)
        task = task_service.create_task(
            title=f"Úkol {self.marker}",
            due_date=due,
            priority=PRIORITY_CRITICAL,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"S úkolem {self.marker}",
            due_date=due,
            task_id=task.id,
            status=FINDING_STATUS_OTEVRENE,
        )
        items = get_attention_items(today=date.today())
        ss_for_parent = [item for item in items if item.item_type == ITEM_TYPE_STATE_SUPERVISION and item.source_id == parent.id]
        self.assertEqual(_by_kind(ss_for_parent, KIND_FINDING), [])
        task_rows = [
            item
            for item in items
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(task_rows), 1)
        self.assertEqual(task_rows[0].date, due)

    def test_07_waiting_check_task_keeps_check_due_date(self) -> None:
        task = task_service.create_task(
            title=f"Kontrola {self.marker}",
            due_date=date(2026, 8, 28),
            completed=True,
            completed_date=date(2026, 8, 27),
            requires_verification=True,
            check_due_date=date(2026, 9, 11),
            priority="Vysoká",
        )
        self.assertEqual(task.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertEqual(task_urgency_due_date(task), date(2026, 9, 11))
        items = [
            item
            for item in get_attention_items(today=date(2026, 9, 1))
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].date, date(2026, 9, 11))
        self.assertEqual(items[0].item_type, ITEM_TYPE_TASK)

    def test_08_widget_type_label_tooltip_and_width(self) -> None:
        row = self._supervision(planned_start_at=datetime.now() + timedelta(days=3))
        widget = UpcomingTasksWidget()
        self.assertEqual(widget.table.columnWidth(COL_TYPE), 130)
        self.assertEqual(widget.table.textElideMode(), Qt.TextElideMode.ElideRight)
        found = None
        for table_row in range(widget.table.rowCount()):
            cell = widget.table.item(table_row, COL_TYPE)
            payload = cell.data(Qt.ItemDataRole.UserRole)
            if (
                getattr(payload, "source_id", None) == row.id
                and payload.open_metadata.get("kind") == KIND_PLANNED_START
            ):
                found = cell
                break
        self.assertIsNotNone(found)
        self.assertEqual(found.text(), TYPE_LABEL_PLANNED_START)
        self.assertEqual(found.toolTip(), TYPE_LABEL_PLANNED_START)
        self.assertEqual(found.data(Qt.ItemDataRole.UserRole).priority, PRIORITY_CRITICAL)
        widget.close()

    def test_09_open_target_tabs_without_dirty_or_write(self) -> None:
        start_row = self._supervision(planned_start_at=_FUTURE)
        obj_row = self._supervision(objections_due_at=_FUTURE)
        closed = self._supervision(
            status=STATUS_CLOSED,
            closed_at=_NOW,
            objections_due_at=_PAST,
        )
        before_mtime = storage_module.storage_service.database_path.stat().st_mtime
        before_count = _count("state_supervisions")
        with patch.object(Session, "commit") as commit:
            start_dialog = StateSupervisionEditorDialog(
                supervision_id=start_row.id,
                target_tab=TAB_ANNOUNCEMENT,
            )
            self.assertEqual(start_dialog.tabs.tabText(start_dialog.tabs.currentIndex()), TAB_ANNOUNCEMENT)
            self.assertFalse(start_dialog._editor.is_dirty())
            self.assertEqual(start_dialog.tabs.count(), 5)
            start_dialog.close()

            obj_dialog = StateSupervisionEditorDialog(
                supervision_id=obj_row.id,
                target_tab=TAB_CONCLUSION,
            )
            self.assertEqual(obj_dialog.tabs.tabText(obj_dialog.tabs.currentIndex()), TAB_CONCLUSION)
            self.assertEqual(obj_dialog.tabs.currentIndex(), 3)
            self.assertFalse(obj_dialog._editor.is_dirty())
            obj_dialog.close()

            unknown = StateSupervisionEditorDialog(
                supervision_id=start_row.id,
                target_tab="neznámá-záložka",
            )
            self.assertEqual(unknown.tabs.currentIndex(), 0)
            self.assertFalse(unknown._editor.is_dirty())
            unknown.close()

            closed_dialog = StateSupervisionEditorDialog(
                supervision_id=closed.id,
                target_tab=TAB_CONCLUSION,
            )
            self.assertEqual(closed_dialog.tabs.tabText(closed_dialog.tabs.currentIndex()), TAB_CONCLUSION)
            self.assertFalse(closed_dialog._editor.is_dirty())
            closed_dialog.close()
            commit.assert_not_called()
        self.assertEqual(_count("state_supervisions"), before_count)
        self.assertEqual(
            storage_module.storage_service.database_path.stat().st_mtime,
            before_mtime,
        )

    def test_10_open_supervision_uses_indexof_and_ignores_filter(self) -> None:
        from moduly.statni_dozor.constants import COL_STATUS, FILTER_MODE_ACTIVE

        closed = self._supervision(
            status=STATUS_CLOSED,
            closed_at=_NOW,
            objections_due_at=_PAST,
        )
        page = AgendaPage()
        opened: list[tuple[int | None, str | None]] = []

        class FakeDialog:
            def __init__(self, parent=None, *, supervision_id=None, target_tab=None, **_kwargs):
                opened.append((supervision_id, target_tab))
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
            ss_index = page.tabs.indexOf(page.state_supervision_tab)
            self.assertEqual(page.tabs.count(), 4)
            self.assertEqual(page.tabs.tabText(ss_index), TAB_STATE_SUPERVISION)
            open_src = inspect.getsource(AgendaPage.open_supervision)
            self.assertIn("indexOf(self.state_supervision_tab)", open_src)
            self.assertNotIn("setCurrentIndex(1)", open_src)

            page.state_supervision_tab.mode_filter.setCurrentText(FILTER_MODE_ACTIVE)
            page.state_supervision_tab.refresh()
            present_ids: list[int] = []
            table = page.state_supervision_tab.table
            for row in range(table.rowCount()):
                cell = table.item(row, COL_STATUS)
                if cell is None:
                    continue
                present_ids.append(int(cell.data(Qt.ItemDataRole.UserRole)))
            self.assertNotIn(closed.id, present_ids)

            page.open_supervision(closed.id, target_tab=TAB_CONCLUSION)
            self.assertEqual(page.tabs.currentIndex(), ss_index)
            self.assertEqual(opened[-1], (closed.id, TAB_CONCLUSION))
            self.assertEqual(
                page.state_supervision_tab.mode_filter.currentText(),
                FILTER_MODE_ACTIVE,
            )
        page.close()

        dummy = SimpleNamespace(_open_state_supervision_by_id=MagicMock())
        item = attention_item_from_state_supervision_deadline(
            _projected(kind=KIND_PLANNED_START, supervision_id=closed.id)
        )
        MainWindow._open_attention_item(dummy, item)
        dummy._open_state_supervision_by_id.assert_called_once_with(
            int(closed.id),
            target_tab=TAB_ANNOUNCEMENT,
            focus_kind=KIND_PLANNED_START,
            focus_child_id=None,
        )

    def test_11_missing_parent_and_collector_failure(self) -> None:
        task = task_service.create_task(
            title=f"Ostatní {self.marker}",
            due_date=_TODAY,
        )
        with patch.object(QMessageBox, "warning", return_value=None) as warn:
            dummy = SimpleNamespace(
                _refresh_dashboard_and_agenda=MagicMock(),
                _show=MagicMock(),
                _page_widgets={},
            )
            MainWindow._open_state_supervision_by_id(dummy, 9_999_333)
            warn.assert_called()
            self.assertEqual(warn.call_args.args[2], ITEM_NOT_FOUND_MESSAGE)
            dummy._refresh_dashboard_and_agenda.assert_called()

        with patch(
            "moduly.statni_dozor.sluzby.state_supervision_deadline_projection.list_state_supervision_deadline_items",
            side_effect=RuntimeError("projekce selhala"),
        ):
            items = get_attention_items(today=_TODAY)
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
                for item in items
            )
        )
        self.assertFalse(
            any(item.item_type == ITEM_TYPE_STATE_SUPERVISION for item in items)
        )

    def test_12_reminders_agenda_calendar_untouched(self) -> None:
        from core.dashboard import widget_calendar_placeholder, widget_today
        from moduly.agenda.sluzby import agenda_service as agenda_service_module

        today_src = inspect.getsource(widget_today)
        self.assertNotIn("_from_state_supervision_upcoming", today_src)
        self.assertNotIn("include_in_upcoming", today_src)
        self.assertNotIn("KIND_PLANNED_START", today_src)

        agenda_src = inspect.getsource(agenda_service_module)
        self.assertNotIn("state_supervision", agenda_src)
        self.assertNotIn("planned_start", agenda_src)

        calendar_src = inspect.getsource(widget_calendar_placeholder)
        self.assertNotIn("state_supervision", calendar_src)
        self.assertIn("agenda_service.get_items", calendar_src)

        attention_src = inspect.getsource(get_attention_items)
        self.assertIn("_from_state_supervision_upcoming", attention_src)
        self.assertIn("_from_tasks", attention_src)

        double_click = inspect.getsource(
            __import__(
                "moduly.statni_dozor.ui.state_supervision_tab",
                fromlist=["StateSupervisionTab"],
            ).StateSupervisionTab.edit_selected
        )
        self.assertIn("_open_editor(supervision_id)", double_click)


if __name__ == "__main__":
    unittest.main()
