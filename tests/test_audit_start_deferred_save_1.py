"""AUDIT-START-DEFERRED-SAVE-1: zahájení auditu z návštěvy až při Uložit."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QDialog
from sqlalchemy import event, func, select

_TMP = Path(tempfile.mkdtemp(prefix="audit-start-deferred-save-1-"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.audity.constants import (
        AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
        COMMISSION_MISSING_LEADER_MESSAGE,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        YEAR_FILTER_VSE,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_question_snapshot_service import (
        AuditV2SnapshotError,
        audit_question_snapshot_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audity_page import AudityPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from tests.audit_v2a_test_support import prepare_v2_audit_create


def _snapshot_count(audit_id: int) -> int:
    with get_session() as session:
        return int(
            session.scalar(
                select(func.count()).select_from(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit_id
                )
            )
            or 0
        )


class AuditStartDeferredSave1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.leader = settings_service.save_worker(
            first_name="Jan", last_name=f"Vedoucí-{suffix}"
        )
        self.workplace_rep = settings_service.save_worker(
            first_name="Eva", last_name=f"Provoz-{suffix}"
        )
        self.union = person_service.create_person(
            first_name="Lucie", last_name=f"Odbory-{suffix}"
        )

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _create_visit(self, *, planned_date: date | None = date(2026, 4, 15)):
        program = audit_program_service.create_program(
            name="Program odloženého zahájení",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=4,
            planned_date=planned_date,
        )
        tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
        process_id = tree[0].process_id if tree else "dokumentace"
        process_name = (
            (tree[0].process_label or process_id) if tree else "Dokumentace"
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id=process_id,
            process_name=process_name,
            standards=["ISO 45001"],
        )
        return program, visit

    def _visit_context(self, visit_id: int):
        context = audit_program_service.get_visit_audit_context(visit_id)
        assert context is not None
        return context

    def _fill_commission(self, dialog: AuditDialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader.id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep.id)
        dialog.commission_widget.union_selector.set_person_id(self.union.id)

    def _capture_writes(self) -> tuple[list[str], object]:
        statements: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            statements.append(statement.lstrip().upper())

        engine = session_module.engine
        event.listen(engine, "before_cursor_execute", _capture)
        return statements, _capture

    def _stop_capture(self, listener) -> None:
        event.remove(session_module.engine, "before_cursor_execute", listener)

    def _close_dialog(self, dialog) -> None:
        """Zavře editor bez dirty promptu (QMessageBox by v offscreen testu visel)."""
        dialog._closing = True
        QDialog.close(dialog)

    def test_01_opening_unstarted_visit_creates_no_audit(self) -> None:
        _, visit = self._create_visit()
        before = {audit.id for audit in audit_service.get_all()}
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self.assertIsNone(dialog.audit)
        self.assertEqual({audit.id for audit in audit_service.get_all()}, before)
        self._close_dialog(dialog)

    def test_02_opening_does_not_assign_number(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self.assertEqual(dialog.spis_widget.number_label.text(), "—")
        self._close_dialog(dialog)

    def test_03_opening_does_not_set_today_as_started_at(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self.assertIsNone(dialog.spis_widget.started_at_edit.get_date())
        self.assertNotEqual(dialog.spis_widget.started_at_edit.get_date(), date.today())
        self._close_dialog(dialog)

    def test_04_and_05_opening_creates_no_snapshot_and_no_visit_link(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.audit_id)
        self.assertEqual(_snapshot_count(0), 0)
        with get_session() as session:
            total = session.scalar(select(func.count()).select_from(AuditQuestionSnapshot))
        self.assertEqual(int(total or 0), 0)
        self._close_dialog(dialog)

    def test_06_close_without_save_writes_nothing(self) -> None:
        _, visit = self._create_visit()
        statements, listener = self._capture_writes()
        try:
            dialog = AuditDialog(visit_context=self._visit_context(visit.id))
            dialog.reject()
        finally:
            self._stop_capture(listener)
        self.assertFalse(
            any(stmt.startswith(("INSERT", "UPDATE", "DELETE")) for stmt in statements),
            statements[:20],
        )
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.audit_id)
        self.assertEqual(audit_service.get_all(), [])

    def test_07_save_without_started_at_creates_unfrozen_plan(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self._fill_commission(dialog)
        with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning:
            saved = dialog._persist()
        self.assertTrue(saved)
        warning.assert_not_called()
        audit = dialog.audit
        assert audit is not None
        self.assertIsNone(audit.started_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(_snapshot_count(audit.id), 0)
        self.assertIsNone(audit.questions_frozen_at)
        self.assertEqual(
            audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self._close_dialog(dialog)

    def test_08_missing_commission_validates_before_db(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        dialog.spis_widget.started_at_edit.set_date_value(date(2026, 4, 12))
        statements, listener = self._capture_writes()
        try:
            with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning:
                saved = dialog._persist()
        finally:
            self._stop_capture(listener)
        self.assertFalse(saved)
        self.assertIn(COMMISSION_MISSING_LEADER_MESSAGE, warning.call_args.args[2])
        self.assertFalse(
            any(stmt.startswith(("INSERT", "UPDATE", "DELETE")) for stmt in statements),
            statements[:20],
        )
        self._close_dialog(dialog)

    def test_09_and_10_successful_save_keeps_date_and_creates_atomically(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self._fill_commission(dialog)
        started = date(2026, 4, 12)
        dialog.spis_widget.started_at_edit.set_date_value(started)
        self.assertTrue(dialog._persist())

        audit = dialog.audit
        assert audit is not None
        self.assertEqual(audit.started_at, started)
        self.assertEqual(audit.status, AUDIT_STATUS_PROBIHA)
        self.assertTrue(audit.number)
        self.assertEqual(audit.program_visit_id, visit.id)
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.audit_id, audit.id)
        self.assertEqual(_snapshot_count(audit.id), 0)
        self.assertEqual(
            audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertEqual(dialog.spis_widget.number_label.text(), audit.number)
        self._close_dialog(dialog)

    def test_11_snapshot_error_rolls_back_prepare_not_the_plan(self) -> None:
        _, visit = self._create_visit()
        audit = audit_program_service.create_audit_from_visit(
            visit.id,
            started_at=date(2026, 4, 12),
        )
        with patch.object(
            audit_question_snapshot_service,
            "build_v2_snapshot_for_audit",
            side_effect=AuditV2SnapshotError("snapshot selhal"),
        ):
            with self.assertRaises((AuditV2SnapshotError, ValueError)):
                audit_program_service.prepare_audit_from_visit(audit.id)
        refreshed_audit = audit_service.get_by_id(audit.id)
        assert refreshed_audit is not None
        self.assertEqual(
            refreshed_audit.methodology_generation,
            AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        self.assertIsNone(refreshed_audit.questions_frozen_at)
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.audit_id, audit.id)
        with get_session() as session:
            total = session.scalar(select(func.count()).select_from(AuditQuestionSnapshot))
        self.assertEqual(int(total or 0), 0)

    def test_12_commit_error_leaves_no_partial_data(self) -> None:
        _, visit = self._create_visit()
        real_get_session = session_module.get_session

        def _failing_session():
            session = real_get_session()
            session.commit = lambda: (_ for _ in ()).throw(RuntimeError("commit fail"))
            return session

        with patch(
            "moduly.audity.sluzby.audit_v2_create_service.get_session",
            _failing_session,
        ):
            with self.assertRaises((ValueError, RuntimeError)):
                audit_program_service.create_audit_from_visit(
                    visit.id,
                    started_at=date(2026, 4, 12),
                )
        self.assertEqual(audit_service.get_all(), [])
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.audit_id)

    def test_13_repeated_save_does_not_duplicate(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self._fill_commission(dialog)
        dialog.spis_widget.started_at_edit.set_date_value(date(2026, 4, 12))
        self.assertTrue(dialog._persist())
        first_id = dialog.audit.id
        first_snaps = _snapshot_count(first_id)
        self.assertTrue(dialog._persist())
        self.assertEqual(dialog.audit.id, first_id)
        self.assertEqual(len(audit_service.get_all()), 1)
        self.assertEqual(_snapshot_count(first_id), first_snaps)
        self._close_dialog(dialog)

    def test_14_existing_audit_opens_that_record(self) -> None:
        _, visit = self._create_visit()
        audit = audit_program_service.create_audit_from_visit(
            visit.id,
            started_at=date(2026, 4, 10),
        )
        dialog = AuditDialog(
            audit=audit_service.get_by_id(audit.id),
            visit_context=self._visit_context(visit.id),
        )
        self.assertEqual(dialog.audit.id, audit.id)
        self.assertEqual(dialog.spis_widget.number_label.text(), audit.number)
        self._close_dialog(dialog)

    def test_15_stale_link_does_not_create_second_audit(self) -> None:
        _, visit = self._create_visit()
        dialog = AuditDialog(visit_context=self._visit_context(visit.id))
        self._fill_commission(dialog)
        dialog.spis_widget.started_at_edit.set_date_value(date(2026, 4, 12))
        first = audit_program_service.create_audit_from_visit(
            visit.id,
            started_at=date(2026, 4, 10),
        )
        with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning:
            saved = dialog._persist()
        self.assertFalse(saved)
        self.assertIsNone(dialog.audit)
        self.assertIn(AUDIT_PROGRAM_VISIT_STARTED_ELSEWHERE, warning.call_args.args[2])
        self.assertEqual([item.id for item in audit_service.get_all()], [first.id])
        self._close_dialog(dialog)

    def test_16_manager_open_and_refresh_are_read_only(self) -> None:
        program, visit = self._create_visit()
        statements, listener = self._capture_writes()
        try:
            manager = AuditProgramManagerDialog()
            manager._reload_program_list(select_program_id=program.id)
            visit_item = manager._plan_tree.topLevelItem(0).child(0)
            manager._plan_tree.setCurrentItem(visit_item)
            with patch(
                "moduly.audity.ui.audit_program_manager_dialog.exec_maximized",
                return_value=False,
            ) as exec_mock:
                def _inspect(dialog):
                    self.assertIsNone(dialog.audit)
                    self.assertIsNone(dialog.spis_widget.started_at_edit.get_date())
                    return False

                exec_mock.side_effect = _inspect
                manager._start_audit_for_selection()
            manager._reload_program_list(select_program_id=program.id)
            manager.close()
        finally:
            self._stop_capture(listener)
        writes = [stmt for stmt in statements if stmt.startswith(("INSERT", "UPDATE", "DELETE"))]
        self.assertEqual(writes, [])
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.audit_id)

    def test_17_existing_audit_uses_update_path(self) -> None:
        _, visit = self._create_visit()
        audit = audit_program_service.create_audit_from_visit(
            visit.id,
            started_at=date(2026, 4, 10),
        )
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        self._fill_commission(dialog)
        with patch.object(
            audit_program_service,
            "create_audit_from_visit",
            side_effect=AssertionError("existing audit used visit create"),
        ):
            self.assertTrue(dialog._persist())
        self.assertEqual(len(audit_service.get_all()), 1)
        self._close_dialog(dialog)

    def test_18_numbering_contract_unchanged(self) -> None:
        _, visit_a = self._create_visit()
        program_b, visit_b = self._create_visit()
        audit_a = audit_program_service.create_audit_from_visit(
            visit_a.id,
            started_at=date(2026, 4, 10),
        )
        audit_b = audit_program_service.create_audit_from_visit(
            visit_b.id,
            started_at=date(2026, 4, 11),
        )
        self.assertEqual(audit_a.number, f"{audit_a.id}/{audit_a.year}")
        self.assertEqual(audit_b.number, f"{audit_b.id}/{audit_b.year}")
        page = AudityPage()
        page.status_filter.setCurrentText("Vše")
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        ids = [int(page.table.item(row, 0).text()) for row in range(page.table.rowCount())]
        self.assertIn(audit_a.id, ids)
        self.assertIn(audit_b.id, ids)
        page.close()
        self.assertNotEqual(program_b.id, visit_a.program_id)

    def test_service_allows_missing_started_at(self) -> None:
        _, visit = self._create_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id, started_at=None)
        self.assertIsNone(audit.started_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(_snapshot_count(audit.id), 0)


if __name__ == "__main__":
    unittest.main()
