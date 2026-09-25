"""AUDIT-PROGRAM-FULFILLMENT-2: návštěva je splněná až po dokončení auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-fulfillment-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import (
        AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_STATUS_PLANNED,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_annual_export_context_service import (
        audit_annual_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_final_export_context_service import (
        audit_program_final_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service


class AuditProgramFulfillment2TestCase(unittest.TestCase):
    def _program(self, name: str):
        return audit_program_service.create_program(
            name=name,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )

    def _visit(self, program, *, planned_date: date | None, status: str | None = None):
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=planned_date.year if planned_date else 2026,
            planned_month=planned_date.month if planned_date else 6,
            planned_date=planned_date,
        )
        if status is not None and status != visit.status:
            visit.status = status
            visit = audit_program_service.repository.update_visit(visit)
        return visit

    def _link(self, visit, **fields):
        audit = audit_service.create_audit(
            workplace_id=10,
            workplace_name="Provoz",
            year=2026,
            program_id=visit.program_id,
            program_visit_id=visit.id,
            title="Audit plnění",
            **fields,
        )
        visit.audit_id = audit.id
        saved = audit_program_service.repository.update_visit(visit)
        return saved, audit

    def test_01_visit_without_audit_is_not_finished(self) -> None:
        program = self._program("Bez auditu")
        visit = self._visit(program, planned_date=date(2026, 6, 1))
        self.assertFalse(audit_program_service.linked_audit_is_finished(visit))

    def test_02_planned_audit_is_not_finished(self) -> None:
        program = self._program("Plánováno")
        visit = self._visit(program, planned_date=date(2026, 6, 2))
        visit, _audit = self._link(visit, started_at=None, finished_at=None)
        self.assertFalse(audit_program_service.linked_audit_is_finished(visit))

    def test_03_prepared_audit_without_start_is_not_finished(self) -> None:
        program = self._program("Připraveno")
        visit = self._visit(program, planned_date=date(2026, 6, 3))
        visit, _audit = self._link(
            visit,
            started_at=None,
            finished_at=None,
            questions_frozen_at=date(2026, 6, 1),
        )
        self.assertFalse(audit_program_service.linked_audit_is_finished(visit))

    def test_04_running_audit_is_not_finished(self) -> None:
        program = self._program("Probíhá")
        visit = self._visit(program, planned_date=date(2026, 6, 4))
        visit, _audit = self._link(
            visit,
            started_at=date(2026, 6, 4),
            finished_at=None,
        )
        self.assertFalse(audit_program_service.linked_audit_is_finished(visit))

    def test_05_finished_at_counts_as_finished(self) -> None:
        program = self._program("Dokončeno")
        visit = self._visit(program, planned_date=date(2026, 6, 5))
        visit, _audit = self._link(
            visit,
            started_at=date(2026, 6, 5),
            finished_at=date(2026, 6, 6),
        )
        self.assertTrue(audit_program_service.linked_audit_is_finished(visit))

    def test_06_completed_visit_without_finished_audit_does_not_count(self) -> None:
        program = self._program("Status bez auditu")
        visit = self._visit(
            program,
            planned_date=date(2026, 6, 7),
            status=AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
        )
        visit, _audit = self._link(visit, started_at=None, finished_at=None)
        self.assertEqual(visit.status, AUDIT_PROGRAM_VISIT_STATUS_COMPLETED)
        self.assertFalse(audit_program_service.linked_audit_is_finished(visit))
        annual = audit_annual_export_context_service._build_program_fulfillment_text(
            2026, program_id=program.id
        )
        final = audit_program_final_export_context_service._build_program_fulfillment_text(
            program
        )
        self.assertIn("0 z 1 plánovaných auditů v roce 2026 dokončeno", annual)
        self.assertIn("Dokončené návštěvy: 0 z 1", final)

    def test_07_finished_audit_counts_even_if_visit_stays_planned(self) -> None:
        program = self._program("Audit bez sync")
        visit = self._visit(program, planned_date=date(2026, 6, 8))
        visit, _audit = self._link(
            visit,
            started_at=date(2026, 6, 8),
            finished_at=date(2026, 6, 9),
        )
        self.assertEqual(visit.status, AUDIT_PROGRAM_VISIT_STATUS_PLANNED)
        self.assertTrue(audit_program_service.linked_audit_is_finished(visit))
        annual = audit_annual_export_context_service._build_program_fulfillment_text(
            2026, program_id=program.id
        )
        final = audit_program_final_export_context_service._build_program_fulfillment_text(
            program
        )
        self.assertIn("1 z 1 plánovaných auditů v roce 2026 dokončeno", annual)
        self.assertIn("Dokončené návštěvy: 1 z 1", final)

    def test_08_and_09_reports_share_finished_count(self) -> None:
        program = self._program("Stejný počet")
        plain = self._visit(program, planned_date=date(2026, 3, 1))
        planned = self._visit(program, planned_date=date(2026, 4, 1))
        running = self._visit(program, planned_date=date(2026, 5, 1))
        done = self._visit(program, planned_date=date(2026, 6, 1))
        self._link(planned, started_at=None, finished_at=None)
        self._link(running, started_at=date(2026, 5, 2), finished_at=None)
        self._link(done, started_at=date(2026, 6, 1), finished_at=date(2026, 6, 2))
        self.assertIsNone(plain.audit_id)
        annual = audit_annual_export_context_service._build_program_fulfillment_text(
            2026, program_id=program.id
        )
        final = audit_program_final_export_context_service._build_program_fulfillment_text(
            program
        )
        self.assertIn("1 z 4 plánovaných auditů v roce 2026 dokončeno", annual)
        self.assertIn("Dokončené návštěvy: 1 z 4", final)

    def test_10_nearest_keeps_open_audits_and_drops_finished_and_skipped(self) -> None:
        program = self._program("Nejbližší")
        today = date.today()
        planned = self._visit(program, planned_date=today - timedelta(days=3))
        running = self._visit(program, planned_date=today - timedelta(days=2))
        done = self._visit(program, planned_date=today - timedelta(days=1))
        skipped = self._visit(program, planned_date=today + timedelta(days=1))
        self._link(planned, started_at=None, finished_at=None)
        self._link(running, started_at=today - timedelta(days=2), finished_at=None)
        self._link(done, started_at=today - timedelta(days=1), finished_at=today)
        audit_program_service.skip_visit(skipped.id)

        open_ids = {
            visit.id
            for visit in audit_program_service.repository.list_visits(program.id)
            if visit.status != "skipped"
            and not audit_program_service.linked_audit_is_finished(visit)
        }
        self.assertEqual(open_ids, {planned.id, running.id})
        nearest = audit_program_service.get_nearest_unstarted_visit(program.id)
        assert nearest is not None
        self.assertIn(nearest.id, {planned.id, running.id})

    def test_11_overdue_unfinished_audit_stays_tracked(self) -> None:
        program = self._program("Po termínu")
        today = date.today()
        overdue = self._visit(program, planned_date=today - timedelta(days=10))
        done = self._visit(program, planned_date=today + timedelta(days=5))
        skipped = self._visit(program, planned_date=today + timedelta(days=6))
        overdue, _audit = self._link(overdue, started_at=None, finished_at=None)
        self._link(
            done,
            started_at=today,
            finished_at=today,
        )
        audit_program_service.skip_visit(skipped.id)
        nearest = audit_program_service.get_nearest_unstarted_visit(program.id)
        assert nearest is not None
        self.assertEqual(nearest.id, overdue.id)
