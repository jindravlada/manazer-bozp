"""STATE-SUPERVISION-DEADLINE-PROJECTION-6B1: read-only projekce termínů."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

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

    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.statni_dozor.constants import (
        STATUS_ANNOUNCED,
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
        StateSupervisionDeadlineItem,
        document_identity,
        finding_identity,
        list_state_supervision_deadline_items,
        objections_identity,
        planned_start_identity,
        state_supervision_deadline_projection_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.ukoly.sluzby.task_service import task_service


def _count(table: str) -> int:
    db_path = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


class StateSupervisionDeadlineProjection6B1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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

    def _items_for(self, *records, today: date | None = _TODAY):
        wanted = {int(record.id) for record in records}

        def load_supervisions():
            return [record for record in records]

        return [
            item
            for item in list_state_supervision_deadline_items(
                today=today,
                load_supervisions=load_supervisions,
            )
            if item.supervision_id in wanted
        ]

    def _by_kind(self, items, kind: str) -> list[StateSupervisionDeadlineItem]:
        return [item for item in items if item.kind == kind]

    def test_00_module_has_no_ui_attention_or_task_queries(self) -> None:
        import moduly.statni_dozor.sluzby.state_supervision_deadline_projection as module

        source = inspect.getsource(module)
        self.assertNotIn("PySide", source)
        self.assertNotIn("QWidget", source)
        self.assertNotIn("from core.dashboard", source)
        self.assertNotIn("attention_item", source)
        self.assertNotIn("attention_service", source)
        self.assertNotIn("get_tasks_by_ids", source)
        self.assertNotIn("get_all_tasks", source)
        self.assertNotIn("task_service", source)

    def test_01_planned_start_future_today_past_and_identity(self) -> None:
        future_row = self._supervision(planned_start_at=_FUTURE)
        today_row = self._supervision(
            authority_name=f"KHS {self.marker}",
            planned_start_at=_NOW.replace(hour=8, minute=0),
        )
        past_row = self._supervision(
            authority_name=f"Hasiči {self.marker}",
            planned_start_at=_PAST,
        )
        items = self._items_for(future_row, today_row, past_row)
        starts = self._by_kind(items, KIND_PLANNED_START)
        self.assertEqual(len(starts), 3)
        by_id = {item.supervision_id: item for item in starts}
        future_item = by_id[future_row.id]
        self.assertEqual(future_item.identity_key, planned_start_identity(future_row.id))
        self.assertEqual(future_item.due_date, _FUTURE.date())
        self.assertEqual(future_item.event_at, _FUTURE)
        self.assertTrue(future_item.include_in_upcoming)
        self.assertTrue(future_item.include_in_reminders)
        self.assertEqual(future_item.target_tab, TAB_ANNOUNCEMENT)
        self.assertEqual(future_item.type_label, TYPE_LABEL_PLANNED_START)
        self.assertEqual(future_item.priority, PRIORITY_CRITICAL)
        self.assertIsNone(future_item.child_id)
        self.assertIn("OIP", future_item.title)
        self.assertIn(f"Provoz {self.marker}", future_item.title)
        self.assertEqual(future_item.title, f"OIP {self.marker} – Provoz {self.marker}")
        self.assertEqual(by_id[today_row.id].due_date, _TODAY)
        self.assertEqual(by_id[past_row.id].due_date, _PAST.date())
        again = self._items_for(future_row)
        self.assertEqual(again[0].identity_key, future_item.identity_key)

    def test_02_planned_start_hidden_rules(self) -> None:
        missing = self._supervision()
        started = self._supervision(
            planned_start_at=_FUTURE, started_at=_NOW
        )
        ended = self._supervision(
            planned_start_at=_FUTURE,
            started_at=_PAST,
            ended_at=_NOW,
        )
        closed = self._supervision(
            planned_start_at=_FUTURE,
            status=STATUS_CLOSED,
            closed_at=_NOW,
        )
        cancelled = self._supervision(
            planned_start_at=_FUTURE,
            status=STATUS_CANCELLED,
        )
        in_progress = self._supervision(started_at=_NOW, status=STATUS_ANNOUNCED)
        items = self._items_for(
            missing, started, ended, closed, cancelled, in_progress
        )
        self.assertEqual(self._by_kind(items, KIND_PLANNED_START), [])
        titles = " ".join(item.title for item in items)
        self.assertNotIn("Probíhá", titles)

    def test_03_documents_rules_and_multiples(self) -> None:
        parent = self._supervision()
        future_doc = state_supervision_required_document_service.create_document(
            parent.id, title="Budoucí spis", due_at=_FUTURE
        )
        today_doc = state_supervision_required_document_service.create_document(
            parent.id, title="Dnešní spis", due_at=_NOW
        )
        past_doc = state_supervision_required_document_service.create_document(
            parent.id, title="Starý spis", due_at=_PAST
        )
        prepared = state_supervision_required_document_service.create_document(
            parent.id,
            title="Připravený spis",
            due_at=_PAST,
            prepared_at=_PAST,
        )
        submitted = state_supervision_required_document_service.create_document(
            parent.id,
            title="Odeslaný spis",
            due_at=_PAST,
            submitted_at=_PAST,
        )
        inactive = state_supervision_required_document_service.create_document(
            parent.id, title="Neaktivní spis", due_at=_PAST
        )
        state_supervision_required_document_service.deactivate_document(inactive.id)
        no_due = state_supervision_required_document_service.create_document(
            parent.id, title="Bez termínu"
        )
        items = self._by_kind(self._items_for(parent), KIND_DOCUMENT)
        ids = {item.child_id for item in items}
        self.assertEqual(
            ids, {future_doc.id, today_doc.id, past_doc.id, prepared.id}
        )
        self.assertNotIn(submitted.id, ids)
        self.assertNotIn(inactive.id, ids)
        self.assertNotIn(no_due.id, ids)
        by_child = {item.child_id: item for item in items}
        prepared_item = by_child[prepared.id]
        self.assertEqual(prepared_item.identity_key, document_identity(parent.id, prepared.id))
        self.assertEqual(prepared_item.due_date, _PAST.date())
        self.assertEqual(prepared_item.event_at, _PAST)
        self.assertFalse(prepared_item.include_in_upcoming)
        self.assertTrue(prepared_item.include_in_reminders)
        self.assertEqual(prepared_item.target_tab, TAB_SUBJECT_PREPARATION)
        self.assertEqual(prepared_item.type_label, TYPE_LABEL_DOCUMENT)
        self.assertEqual(prepared_item.priority, PRIORITY_CRITICAL)
        self.assertIn("Připravený spis", prepared_item.title)
        self.assertIn("OIP", prepared_item.title)
        self.assertEqual(by_child[today_doc.id].due_date, _TODAY)
        self.assertEqual(by_child[future_doc.id].due_date, _FUTURE.date())

    def test_04_documents_closed_kept_cancelled_hidden(self) -> None:
        closed = self._supervision(status=STATUS_CLOSED, closed_at=_NOW)
        cancelled = self._supervision(status=STATUS_CANCELLED)
        kept = state_supervision_required_document_service.create_document(
            closed.id, title="Doklad uzavřené", due_at=_PAST
        )
        state_supervision_required_document_service.create_document(
            cancelled.id, title="Doklad zrušené", due_at=_PAST
        )
        closed_items = self._by_kind(self._items_for(closed), KIND_DOCUMENT)
        self.assertEqual([item.child_id for item in closed_items], [kept.id])
        self.assertEqual(self._by_kind(self._items_for(cancelled), KIND_DOCUMENT), [])

    def test_05_objections_rules(self) -> None:
        future_row = self._supervision(objections_due_at=_FUTURE)
        today_row = self._supervision(
            authority_name=f"KHS {self.marker}",
            objections_due_at=_NOW,
        )
        past_row = self._supervision(
            authority_name=f"Hasiči {self.marker}",
            objections_due_at=_PAST,
        )
        submitted = self._supervision(
            authority_name=f"Celní {self.marker}",
            objections_due_at=_PAST,
            objections_submitted_at=_NOW,
        )
        missing = self._supervision(authority_name=f"Bez lhůty {self.marker}")
        closed = self._supervision(
            authority_name=f"Uzavřená {self.marker}",
            status=STATUS_CLOSED,
            closed_at=_NOW,
            objections_due_at=_PAST,
        )
        cancelled = self._supervision(
            authority_name=f"Zrušená {self.marker}",
            status=STATUS_CANCELLED,
            objections_due_at=_PAST,
        )
        items = self._items_for(
            future_row, today_row, past_row, submitted, missing, closed, cancelled
        )
        objections = self._by_kind(items, KIND_OBJECTIONS)
        ids = {item.supervision_id for item in objections}
        self.assertEqual(ids, {future_row.id, today_row.id, past_row.id, closed.id})
        sample = next(item for item in objections if item.supervision_id == past_row.id)
        self.assertEqual(sample.identity_key, objections_identity(past_row.id))
        self.assertEqual(sample.due_date, _PAST.date())
        self.assertEqual(sample.event_at, _PAST)
        self.assertTrue(sample.include_in_upcoming)
        self.assertTrue(sample.include_in_reminders)
        self.assertEqual(sample.target_tab, TAB_CONCLUSION)
        self.assertEqual(sample.type_label, TYPE_LABEL_OBJECTIONS)
        self.assertIsNone(sample.child_id)
        self.assertIn("Námitky", sample.title)

    def test_06_findings_without_task_and_exclusions(self) -> None:
        parent = self._supervision()
        closed = self._supervision(status=STATUS_CLOSED, closed_at=_NOW)
        cancelled = self._supervision(status=STATUS_CANCELLED)
        open_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Otevřené {self.marker}",
            due_date=_TODAY,
            status=FINDING_STATUS_OTEVRENE,
        )
        in_process = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"V procesu {self.marker}",
            due_date=_PAST.date(),
            status=FINDING_STATUS_V_PROCESU,
        )
        with_task = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"S úkolem {self.marker}",
            due_date=_TODAY,
            task_id=task_service.create_task(
                title=f"Úkol {self.marker}", due_date=_TODAY
            ).id,
        )
        dangling = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Visící {self.marker}",
            due_date=_TODAY,
            task_id=7_001_001,
        )
        resolved = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Vypořádané {self.marker}",
            due_date=_TODAY,
            status=FINDING_STATUS_VYPORADANO,
        )
        no_due = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Bez termínu {self.marker}",
            status=FINDING_STATUS_OTEVRENE,
        )
        closed_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            closed.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Uzavřená kontrola {self.marker}",
            due_date=_PAST.date(),
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            cancelled.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description=f"Zrušená kontrola {self.marker}",
            due_date=_TODAY,
            status=FINDING_STATUS_OTEVRENE,
        )
        items = self._items_for(parent, closed, cancelled)
        findings = self._by_kind(items, KIND_FINDING)
        ids = {item.child_id for item in findings}
        self.assertEqual(ids, {open_finding.id, in_process.id, closed_finding.id})
        self.assertNotIn(with_task.id, ids)
        self.assertNotIn(dangling.id, ids)
        self.assertNotIn(resolved.id, ids)
        self.assertNotIn(no_due.id, ids)
        open_item = next(item for item in findings if item.child_id == open_finding.id)
        self.assertEqual(
            open_item.identity_key, finding_identity(parent.id, open_finding.id)
        )
        self.assertEqual(open_item.due_date, _TODAY)
        self.assertIsNone(open_item.event_at)
        self.assertFalse(open_item.include_in_upcoming)
        self.assertTrue(open_item.include_in_reminders)
        self.assertEqual(open_item.target_tab, TAB_COURSE)
        self.assertEqual(open_item.type_label, TYPE_LABEL_FINDING)
        self.assertEqual(open_item.priority, PRIORITY_CRITICAL)
        self.assertIn(f"Otevřené {self.marker}", open_item.title)
        self.assertNotIn("task", open_item.kind)

    def test_07_no_duplicate_kinds_and_no_task_rows(self) -> None:
        parent = self._supervision(
            planned_start_at=_FUTURE,
            objections_due_at=_PAST,
        )
        first = state_supervision_required_document_service.create_document(
            parent.id, title="A", due_at=_FUTURE
        )
        second = state_supervision_required_document_service.create_document(
            parent.id, title="B", due_at=_PAST
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Bez úkolu",
            due_date=_TODAY,
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="S úkolem",
            due_date=_TODAY,
            task_id=88,
        )
        items = self._items_for(parent)
        starts = self._by_kind(items, KIND_PLANNED_START)
        objections = self._by_kind(items, KIND_OBJECTIONS)
        documents = self._by_kind(items, KIND_DOCUMENT)
        findings = self._by_kind(items, KIND_FINDING)
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(objections), 1)
        self.assertEqual({item.child_id for item in documents}, {first.id, second.id})
        self.assertEqual(len(findings), 1)
        self.assertEqual(len({item.identity_key for item in items}), len(items))
        self.assertTrue(all(item.kind != "task" for item in items))

    def test_08_deterministic_sort_and_dto_types(self) -> None:
        later = self._supervision(
            authority_name="Zeta",
            planned_start_at=datetime(2026, 8, 1, 9, 0, 0),
        )
        earlier = self._supervision(
            authority_name="Alfa",
            planned_start_at=datetime(2026, 7, 1, 15, 0, 0),
            objections_due_at=datetime(2026, 7, 1, 8, 0, 0),
        )
        items = self._items_for(later, earlier)
        keys = [(item.due_date, item.event_at or datetime.combine(item.due_date, time.min), item.identity_key) for item in items]
        self.assertEqual(keys, sorted(keys))
        for item in items:
            self.assertIsInstance(item, StateSupervisionDeadlineItem)
            self.assertIsInstance(item.identity_key, str)
            self.assertIsInstance(item.supervision_id, int)
            self.assertIsInstance(item.title, str)
            self.assertIsInstance(item.type_label, str)
            self.assertIsInstance(item.due_date, date)
            self.assertTrue(item.event_at is None or isinstance(item.event_at, datetime))
            self.assertEqual(item.priority, PRIORITY_CRITICAL)
            self.assertFalse(hasattr(item, "_sa_instance_state"))

    def test_09_batch_queries_no_n_plus_one_and_no_task_query(self) -> None:
        first = self._supervision(planned_start_at=_FUTURE)
        second = self._supervision(
            authority_name=f"KHS {self.marker}",
            objections_due_at=_PAST,
        )
        state_supervision_required_document_service.create_document(
            first.id, title="Spis 1", due_at=_FUTURE
        )
        state_supervision_required_document_service.create_document(
            second.id, title="Spis 2", due_at=_PAST
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            first.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Z1",
            due_date=_TODAY,
        )
        supervision_calls: list[int] = []
        document_calls: list[list[int]] = []
        finding_calls: list[list[int]] = []

        def load_supervisions():
            supervision_calls.append(1)
            return [first, second]

        def load_documents(ids):
            document_calls.append(list(ids))
            return state_supervision_required_document_service.list_for_supervisions(ids)

        def load_findings(ids):
            finding_calls.append(list(ids))
            return finding_service.get_for_entities(ENTITY_STATE_SUPERVISION, list(ids))

        with (
            patch.object(task_service, "get_all_tasks", side_effect=AssertionError("Task query")),
            patch.object(task_service, "get_tasks_by_ids", side_effect=AssertionError("Task query")),
        ):
            items = list_state_supervision_deadline_items(
                today=_TODAY,
                load_supervisions=load_supervisions,
                load_documents=load_documents,
                load_findings=load_findings,
            )
        self.assertEqual(supervision_calls, [1])
        self.assertEqual(len(document_calls), 1)
        self.assertEqual(len(finding_calls), 1)
        self.assertEqual(set(document_calls[0]), {first.id, second.id})
        self.assertGreaterEqual(len(items), 4)

        empty_docs: list[list[int]] = []
        empty_findings: list[list[int]] = []
        empty = list_state_supervision_deadline_items(
            load_supervisions=lambda: [],
            load_documents=lambda ids: empty_docs.append(list(ids)) or [],
            load_findings=lambda ids: empty_findings.append(list(ids)) or [],
        )
        self.assertEqual(empty, [])
        self.assertEqual(empty_docs, [])
        self.assertEqual(empty_findings, [])

        cancelled = self._supervision(status=STATUS_CANCELLED, planned_start_at=_FUTURE)
        cancelled_docs: list[list[int]] = []
        cancelled_findings: list[list[int]] = []
        cancelled_items = list_state_supervision_deadline_items(
            load_supervisions=lambda: [cancelled],
            load_documents=lambda ids: cancelled_docs.append(list(ids)) or [],
            load_findings=lambda ids: cancelled_findings.append(list(ids)) or [],
        )
        self.assertEqual(cancelled_items, [])
        self.assertEqual(cancelled_docs, [])
        self.assertEqual(cancelled_findings, [])

    def test_10_read_only_no_sql_writes_or_mtime_change(self) -> None:
        parent = self._supervision(planned_start_at=_FUTURE, objections_due_at=_PAST)
        state_supervision_required_document_service.create_document(
            parent.id, title="Read-only spis", due_at=_FUTURE
        )
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Read-only zjištění",
            due_date=_TODAY,
        )
        db_path = storage_module.storage_service.database_path
        before = {
            "supervisions": _count("state_supervisions"),
            "documents": _count("state_supervision_required_documents"),
            "findings": _count("findings"),
            "tasks": _count("tasks"),
        }
        mtime_before = db_path.stat().st_mtime_ns
        with (
            patch.object(Session, "commit") as commit,
            patch.object(Session, "flush") as flush,
            patch.object(task_service, "get_all_tasks", side_effect=AssertionError("Task")),
            patch.object(task_service, "get_tasks_by_ids", side_effect=AssertionError("Task")),
        ):
            first = self._items_for(parent)
            second = self._items_for(parent, today=_TODAY + timedelta(days=30))
            commit.assert_not_called()
            flush.assert_not_called()
        self.assertEqual([item.identity_key for item in first], [item.identity_key for item in second])
        self.assertEqual(_count("state_supervisions"), before["supervisions"])
        self.assertEqual(_count("state_supervision_required_documents"), before["documents"])
        self.assertEqual(_count("findings"), before["findings"])
        self.assertEqual(_count("tasks"), before["tasks"])
        self.assertEqual(db_path.stat().st_mtime_ns, mtime_before)
        reloaded = state_supervision_service.get_supervision(parent.id)
        assert reloaded is not None
        self.assertEqual(reloaded.planned_start_at, _FUTURE)
        self.assertEqual(reloaded.status, STATUS_ANNOUNCED)

    def test_11_today_does_not_drop_future_items(self) -> None:
        parent = self._supervision(planned_start_at=_FUTURE)
        today_items = self._items_for(parent, today=_TODAY)
        past_today = self._items_for(parent, today=_FUTURE.date() + timedelta(days=1))
        self.assertEqual(len(self._by_kind(today_items, KIND_PLANNED_START)), 1)
        self.assertEqual(len(self._by_kind(past_today, KIND_PLANNED_START)), 1)

    def test_12_service_singleton_matches_function(self) -> None:
        parent = self._supervision(planned_start_at=_NOW)
        via_fn = self._items_for(parent)
        via_svc = [
            item
            for item in state_supervision_deadline_projection_service.list_items(
                load_supervisions=lambda: [parent]
            )
            if item.supervision_id == parent.id
        ]
        self.assertEqual(
            [item.identity_key for item in via_fn],
            [item.identity_key for item in via_svc],
        )


if __name__ == "__main__":
    unittest.main()
