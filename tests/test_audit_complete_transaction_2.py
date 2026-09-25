"""AUDIT-COMPLETE-TRANSACTION-2: první dokončení auditu je jedna transakce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-complete-tx-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED,
        AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_STATUS_PLANNED,
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PROBIHA,
        CONTROL_POINT_SEVERITY_STREDNI,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        EXTRAORDINARY_CATEGORY_PROCESS_ID,
        EXTRAORDINARY_CATEGORY_PROCESS_NAME,
        EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
        EXTRAORDINARY_TARGET_STATUS_VERIFIED,
        extraordinary_assertion_id,
    )
    from moduly.audity.sluzby.audit_extraordinary_assignment_service import (
        audit_extraordinary_assignment_service,
    )
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_lead_recommendation_service import (
        confirmed_recommendation_fields,
    )
    from moduly.audity.sluzby.audit_program_service import (
        AuditProgramService,
        audit_program_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from tests.audit_v2a_test_support import prepare_v2_audit_create


class AuditCompleteTransaction2TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._v2 = prepare_v2_audit_create()
        self._system_wp, self._operation_wp = self._v2.__enter__()

    def tearDown(self) -> None:
        self._v2.__exit__(None, None, None)

    def _program_visit(self):
        program = audit_program_service.create_program(
            name="Program transakce",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=12,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=4,
            planned_date=date(2026, 4, 15),
        )
        audit_program_service.add_visit_process(
            visit.id, process_id="proc_a", process_name="Proces A"
        )
        audit_program_service.add_visit_process(
            visit.id, process_id="proc_b", process_name="Proces B"
        )
        audit = audit_program_service.create_audit_from_visit(
            visit.id, started_at=date(2026, 4, 10)
        )
        return program, visit, audit

    def _complete(self, audit, *, finished_at=date(2026, 4, 20)):
        return audit_service.update_audit(
            audit.id,
            finished_at=finished_at,
            conclusion_text="Závěr transakce.",
            **confirmed_recommendation_fields(audit.id),
        )

    def test_01_first_completion_sets_finished_status(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            year=2026,
            started_at=date(2026, 4, 10),
            title="Ruční dokončení",
        )
        updated = self._complete(audit)
        assert updated is not None
        self.assertEqual(updated.finished_at, date(2026, 4, 20))
        self.assertEqual(updated.status, AUDIT_STATUS_DOKONCENO)

    def test_02_and_03_program_visit_and_processes(self) -> None:
        _program, visit, audit = self._program_visit()
        updated = self._complete(audit, finished_at=date(2026, 4, 22))
        assert updated is not None
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.status, AUDIT_PROGRAM_VISIT_STATUS_COMPLETED)
        processes = audit_program_service.repository.list_visit_processes(visit.id)
        self.assertEqual(len(processes), 2)
        for item in processes:
            self.assertEqual(item.status, AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED)
            self.assertEqual(item.audit_id, audit.id)
            self.assertIsNotNone(item.completed_at)

    def test_04_extraordinary_is_finalized(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="K dokončení",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        _program, _visit, audit = self._program_visit()
        audit_program_service.prepare_audit_from_visit(audit.id)
        control_result_service.set_result(
            ENTITY_AUDITY,
            int(audit.id),
            ControlPointContext(
                area_id=EXTRAORDINARY_CATEGORY_PROCESS_ID,
                area_label=EXTRAORDINARY_CATEGORY_PROCESS_NAME,
                section_id="__extraordinary_section__",
                section_label="Mimořádná ověření",
                control_point_id=extraordinary_assertion_id(question.id),
                control_point_label="K dokončení",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="",
        )
        self._complete(audit)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertEqual(targets[0].status, EXTRAORDINARY_TARGET_STATUS_VERIFIED)
        self.assertEqual(targets[0].verified_audit_id, audit.id)

    def test_05_visit_sync_error_rolls_back_finished_at(self) -> None:
        _program, visit, audit = self._program_visit()

        def fail(self, session, audit_id, *, finished_at):
            raise RuntimeError("návštěva selhala")

        with patch.object(AuditProgramService, "_sync_on_audit_completed", fail):
            with self.assertRaises(RuntimeError):
                self._complete(audit)
        refreshed = audit_service.get_by_id(audit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.finished_at)
        self.assertNotEqual(refreshed.status, AUDIT_STATUS_DOKONCENO)
        visit_row = audit_program_service.repository.get_visit(visit.id)
        assert visit_row is not None
        self.assertEqual(visit_row.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)

    def test_06_process_error_rolls_back_audit_visit_and_processes(self) -> None:
        _program, visit, audit = self._program_visit()

        calls = {"n": 0}
        real = AuditProgramService._complete_visit_process

        def fail(_self, visit_process, *, audit_id, completed_at):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("proces selhal")
            real(visit_process, audit_id=audit_id, completed_at=completed_at)

        with patch.object(AuditProgramService, "_complete_visit_process", fail):
            with self.assertRaises(RuntimeError):
                self._complete(audit)
        refreshed = audit_service.get_by_id(audit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.finished_at)
        visit_row = audit_program_service.repository.get_visit(visit.id)
        assert visit_row is not None
        self.assertEqual(visit_row.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)
        for item in audit_program_service.repository.list_visit_processes(visit.id):
            self.assertEqual(item.status, AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED)
            self.assertIsNone(item.completed_at)

    def test_07_finalize_error_rolls_back_everything(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Rollback ověření",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        _program, visit, audit = self._program_visit()
        audit_program_service.prepare_audit_from_visit(audit.id)
        real = audit_extraordinary_assignment_service.finalize_for_completed_audit

        def fail(session, audit_id, *, when=None):
            real(session, audit_id, when=when)
            raise RuntimeError("finalize selhalo")

        with patch.object(
            audit_extraordinary_assignment_service,
            "finalize_for_completed_audit",
            fail,
        ):
            with self.assertRaises(RuntimeError):
                self._complete(audit)
        refreshed = audit_service.get_by_id(audit.id)
        assert refreshed is not None
        self.assertIsNone(refreshed.finished_at)
        visit_row = audit_program_service.repository.get_visit(visit.id)
        assert visit_row is not None
        self.assertEqual(visit_row.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)
        for item in audit_program_service.repository.list_visit_processes(visit.id):
            self.assertEqual(item.status, AUDIT_PROGRAM_VISIT_PROCESS_STATUS_PLANNED)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertEqual(targets[0].status, EXTRAORDINARY_TARGET_STATUS_ASSIGNED)
        self.assertIsNone(targets[0].verified_at)

    def test_08_previously_saved_result_survives_failed_completion(self) -> None:
        _program, _visit, audit = self._program_visit()
        control_result_service.set_result(
            ENTITY_AUDITY,
            int(audit.id),
            ControlPointContext(
                area_id="proc_a",
                area_label="Proces A",
                section_id="sec",
                section_label="Oblast",
                control_point_id="q1",
                control_point_label="Tvrzení",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="už uloženo",
        )

        def fail(self, session, audit_id, *, finished_at):
            raise RuntimeError("dokončení selhalo")

        with patch.object(AuditProgramService, "_sync_on_audit_completed", fail):
            with self.assertRaises(RuntimeError):
                self._complete(audit)
        stored = control_result_service.get_for_entity(ENTITY_AUDITY, audit.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].result, CONTROL_RESULT_VYHOVUJE)
        self.assertEqual(stored[0].note, "už uloženo")

    def test_09_manual_audit_without_visit_completes(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            year=2026,
            started_at=date(2026, 5, 1),
            title="Bez návštěvy",
        )
        updated = self._complete(audit, finished_at=date(2026, 5, 2))
        assert updated is not None
        self.assertEqual(updated.status, AUDIT_STATUS_DOKONCENO)
        self.assertIsNone(audit_program_service.repository.get_visit_by_audit_id(audit.id))

    def test_10_completion_without_extraordinary_succeeds(self) -> None:
        _program, visit, audit = self._program_visit()
        updated = self._complete(audit)
        assert updated is not None
        self.assertEqual(updated.status, AUDIT_STATUS_DOKONCENO)
        refreshed = audit_program_service.repository.get_visit(visit.id)
        assert refreshed is not None
        self.assertEqual(refreshed.status, AUDIT_PROGRAM_VISIT_STATUS_COMPLETED)

    def test_11_second_update_does_not_sync_again(self) -> None:
        _program, visit, audit = self._program_visit()
        self._complete(audit, finished_at=date(2026, 4, 20))
        processes = audit_program_service.repository.list_visit_processes(visit.id)
        original_completed = processes[0].completed_at

        def fail(*_args, **_kwargs):
            raise AssertionError("synchronizace se nesmí opakovat")

        with patch.object(audit_program_service, "sync_on_audit_completed", fail):
            updated = audit_service.update_audit(audit.id, title="Jen název")
        assert updated is not None
        self.assertEqual(updated.title, "Jen název")
        self.assertEqual(updated.finished_at, date(2026, 4, 20))
        again = audit_program_service.repository.list_visit_processes(visit.id)
        self.assertEqual(again[0].completed_at, original_completed)

    def test_12_and_13_fulfillment_follows_commit_and_rollback(self) -> None:
        _program, visit, audit = self._program_visit()
        self._complete(audit)
        done = audit_program_service.repository.get_visit(visit.id)
        assert done is not None
        self.assertTrue(audit_program_service.linked_audit_is_finished(done))

        _program2, visit2, audit2 = self._program_visit()

        def fail(self, session, audit_id, *, finished_at):
            raise RuntimeError("rollback plnění")

        with patch.object(AuditProgramService, "_sync_on_audit_completed", fail):
            with self.assertRaises(RuntimeError):
                self._complete(audit2)
        open_visit = audit_program_service.repository.get_visit(visit2.id)
        assert open_visit is not None
        self.assertFalse(audit_program_service.linked_audit_is_finished(open_visit))
        reloaded = audit_service.get_by_id(audit2.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, AUDIT_STATUS_PROBIHA)
