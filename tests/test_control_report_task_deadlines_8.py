"""CONTROL-REPORT-TASK-DEADLINES-8: souhrn navazujících úkolů v úvodu zpráv."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="control-report-task-deadlines-8-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.control_activity_statistics_service import (
        ControlActivityStatistics,
    )
    from core.shared.sluzby.control_report_task_deadlines import (
        ALL_TASKS_TERMINAL_SENTENCE,
        NO_LINKED_TASKS_SENTENCE,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG as AUDIT_DETAILED_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG as AUDIT_PROTOCOL_CONFIG,
        AuditExportContext,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG as INSPECTION_DETAILED_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG as INSPECTION_PROTOCOL_CONFIG,
        InspectionExportContext,
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
    from moduly.ukoly.constants import TASK_STATUS_WAITING_CHECK
    from moduly.ukoly.sluzby.task_deadline import task_urgency_due_date
    from moduly.ukoly.sluzby.task_service import task_service


REPO_ROOT = Path(__file__).resolve().parents[1]
_EMPTY_STATS = ControlActivityStatistics(
    areas_checked=0,
    sections_checked=0,
    control_points_checked=0,
    ratings_vyhovuje=0,
    ratings_nevyhovuje=0,
    ratings_netyka_se=0,
    ratings_nehodnoceno=0,
    findings_total=0,
    tasks_total=0,
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _sync_templates() -> None:
    import moduly.audity.sluzby.protokol_audit_service as audit_protokol
    import moduly.proverky.sluzby.protokol_proverky_service as inspection_protokol

    importlib.reload(inspection_protokol)
    importlib.reload(audit_protokol)
    pairs = (
        (
            REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty",
            inspection_protokol.protokol_proverky_service,
            ("ProtokolProverkyBOZP.odt", "PodrobnaZpravaProverky.odt"),
        ),
        (
            REPO_ROOT / "moduly" / "audity" / "templates" / "exporty",
            audit_protokol.protokol_audit_service,
            ("ProtokolAudit.odt", "PodrobnaZpravaAudit.odt"),
        ),
    )
    for bundled_root, service, names in pairs:
        for name in names:
            target = service.template_path(detailed="Podrobna" in name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_root / name, target)


class ControlReportTaskDeadlines8TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_inspection(self):
        workplace = settings_service.save_workplace(name="Poříčí")
        return bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=1,
            started_at=date(2026, 1, 10),
            finished_at=date(2026, 1, 12),
            notes_mode=None,
        )

    def _create_audit(self):
        workplace = settings_service.save_workplace(name="Provoz Audit")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=2,
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 3),
            notes_mode=None,
        )

    def _add_finding_with_task(
        self,
        entity_type: str,
        entity_id: int,
        *,
        finding_type: str,
        due: date | None = None,
        point_id: str = "",
    ):
        finding = finding_service.create(
            entity_type,
            entity_id,
            finding_type=finding_type,
            description="zjištění",
            due_date=due,
            source_control_point_id=point_id,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        return finding_service.get_by_id(finding.id), task

    def test_inspection_no_findings_no_task_sentence(self) -> None:
        inspection = self._create_inspection()
        ctx = bozp_inspection_export_context_service.build(inspection)
        assessment = ctx.overall_assessment_text()
        overview = ctx.results_overview_text()
        self.assertNotIn("navazující", assessment)
        self.assertNotIn(NO_LINKED_TASKS_SENTENCE, assessment)
        self.assertIn("Otevřené úkoly: 0", overview)
        self.assertNotIn("Nejzazší evidovaný termín", overview)
        self.assertNotIn("Otevřené úkoly bez termínu", overview)

    def test_inspection_finding_without_task(self) -> None:
        inspection = self._create_inspection()
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="bez úkolu",
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(NO_LINKED_TASKS_SENTENCE, ctx.overall_assessment_text())
        self.assertIn("Otevřené úkoly: 0", ctx.results_overview_text())

    def test_inspection_open_tasks_with_due(self) -> None:
        inspection = self._create_inspection()
        self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 10, 31),
            point_id="a",
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        assessment = ctx.overall_assessment_text()
        overview = ctx.results_overview_text()
        self.assertIn(
            "Evidence obsahuje 1 otevřený navazující úkol. "
            "Nejzazší evidovaný termín otevřených úkolů je 31. 10. 2026.",
            assessment,
        )
        self.assertIn("Otevřené úkoly: 1", overview)
        self.assertIn("Nejzazší evidovaný termín: 31. 10. 2026", overview)
        self.assertEqual(
            bozp_inspection_service.get_conclusion_summary(inspection.id)["tasks_active"],
            1,
        )

        for index in range(2):
            self._add_finding_with_task(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                due=date(2026, 9, index + 1),
                point_id=f"b{index}",
            )
        few = bozp_inspection_export_context_service.build(inspection)
        self.assertIn("3 otevřené navazující úkoly", few.overall_assessment_text())

        for index in range(2):
            self._add_finding_with_task(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                due=date(2026, 11, index + 1),
                point_id=f"c{index}",
            )
        many = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(
            "5 otevřených navazujících úkolů",
            many.overall_assessment_text(),
        )
        self.assertIn("Otevřené úkoly: 5", many.results_overview_text())
        self.assertIn("Nejzazší evidovaný termín: 02. 11. 2026", many.results_overview_text())

    def test_inspection_some_without_due(self) -> None:
        inspection = self._create_inspection()
        self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 10, 31),
            point_id="a",
        )
        self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=None,
            point_id="b",
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        assessment = ctx.overall_assessment_text()
        overview = ctx.results_overview_text()
        self.assertIn(
            "Evidence obsahuje 2 otevřené navazující úkoly; "
            "1 z nich nemá stanovený termín.",
            assessment,
        )
        self.assertIn("Otevřené úkoly bez termínu: 1", overview)
        self.assertNotIn("Nejzazší evidovaný termín", overview)

    def test_inspection_all_terminal_and_mix(self) -> None:
        inspection = self._create_inspection()
        _finding, closed = self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 10, 1),
            point_id="c",
        )
        _finding2, canceled = self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 10, 2),
            point_id="d",
        )
        task_service.cancel_task(canceled.id)
        closed_row = task_service.get_task_by_id(closed.id)
        closed_row.completed = True
        closed_row.completed_date = date.today()
        closed_row.checked_date = date.today()
        task_service.repository.update(closed_row)

        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(ALL_TASKS_TERMINAL_SENTENCE, ctx.overall_assessment_text())
        self.assertIn("Otevřené úkoly: 0", ctx.results_overview_text())

        self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 12, 1),
            point_id="e",
        )
        mixed = bozp_inspection_export_context_service.build(inspection)
        self.assertIn("1 otevřený navazující úkol", mixed.overall_assessment_text())
        self.assertIn("Otevřené úkoly: 1", mixed.results_overview_text())

    def test_waiting_check_due_and_without_check_due(self) -> None:
        inspection = self._create_inspection()
        _finding, task = self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 5, 1),
            point_id="w",
        )
        task_service.mark_completed(task.id)
        waiting = task_service.get_task_by_id(task.id)
        self.assertEqual(TASK_STATUS_WAITING_CHECK, waiting.computed_status)
        check_due = date(2026, 11, 15)
        waiting.check_due_date = check_due
        task_service.repository.update(waiting)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(check_due, task_urgency_due_date(reloaded))

        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn("15. 11. 2026", ctx.overall_assessment_text())
        self.assertNotIn("01. 05. 2026", ctx.overall_assessment_text())
        self.assertNotIn("1. 5. 2026", ctx.overall_assessment_text())

        waiting.check_due_date = None
        waiting.due_date = date(2026, 5, 1)
        task_service.repository.update(waiting)
        ctx2 = bozp_inspection_export_context_service.build(inspection)
        overview = ctx2.results_overview_text()
        self.assertIn("Otevřené úkoly bez termínu: 1", overview)
        self.assertNotIn("Nejzazší evidovaný termín", overview)
        self.assertNotIn("05. 05. 2026", ctx2.overall_assessment_text())
        self.assertNotIn("01. 05. 2026", ctx2.overall_assessment_text())

    def test_missing_task_link_does_not_crash(self) -> None:
        inspection = self._create_inspection()
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="visící vazba",
        )
        finding_service.update(finding.id, task_id=999_001)
        ctx = bozp_inspection_export_context_service.build(inspection)
        with self.assertLogs(
            "core.shared.sluzby.control_report_task_deadlines",
            level="WARNING",
        ):
            assessment = ctx.overall_assessment_text()
            overview = ctx.results_overview_text()
        self.assertIn(NO_LINKED_TASKS_SENTENCE, assessment)
        self.assertNotIn("999001", assessment)
        self.assertIn("Otevřené úkoly: 0", overview)
        reloaded = finding_service.get_by_id(finding.id)
        self.assertEqual(999_001, reloaded.task_id)

    def test_inspection_no_n_plus_one_and_same_outputs(self) -> None:
        inspection = self._create_inspection()
        for index in range(4):
            self._add_finding_with_task(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZAVADA,
                due=date(2026, 10, 31),
                point_id=f"n{index}",
            )
        context = bozp_inspection_export_context_service.build(inspection)
        with patch.object(
            InspectionExportContext,
            "_activity_statistics",
            return_value=_EMPTY_STATS,
        ):
            with patch.object(
                task_service,
                "get_task_by_id",
                side_effect=AssertionError("N+1 get_task_by_id"),
            ):
                with patch.object(
                    task_service,
                    "get_tasks_by_ids",
                    wraps=task_service.get_tasks_by_ids,
                ) as batched:
                    assessment = context.overall_assessment_text()
                    overview = context.results_overview_text()
                    context.attention_areas_text()
        self.assertEqual(1, batched.call_count)
        self.assertIn("4 otevřené navazující úkoly", assessment)
        self.assertIn("Otevřené úkoly: 4", overview)

        protocol_ctx = bozp_inspection_export_context_service.build(
            inspection, INSPECTION_PROTOCOL_CONFIG
        )
        detailed_ctx = bozp_inspection_export_context_service.build(
            inspection, INSPECTION_DETAILED_CONFIG
        )
        self.assertEqual(
            protocol_ctx.overall_assessment_text(),
            detailed_ctx.overall_assessment_text(),
        )
        self.assertEqual(
            protocol_ctx.results_overview_text(),
            detailed_ctx.results_overview_text(),
        )
        protocol = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        detailed = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        for content in (protocol, detailed):
            self.assertIn("31. 10. 2026", content)
            self.assertIn("Otevřené úkoly: 4", content)

    def test_inspection_export_does_not_write(self) -> None:
        inspection = self._create_inspection()
        finding, task = self._add_finding_with_task(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            due=date(2026, 10, 31),
        )
        before_task = task.updated_at
        before_finding = finding_service.get_by_id(finding.id)
        protokol_proverky_service.generate_for_inspection(inspection)
        after_task = task_service.get_task_by_id(task.id)
        after_finding = finding_service.get_by_id(finding.id)
        self.assertEqual(before_task, after_task.updated_at)
        self.assertEqual(before_finding.task_id, after_finding.task_id)
        self.assertEqual(before_finding.status, after_finding.status)

    def test_audit_main_situations(self) -> None:
        audit = self._create_audit()
        empty = audit_export_context_service.build(audit)
        self.assertNotIn("navazující", empty.overall_assessment_text())
        self.assertIn("Otevřené úkoly: 0", empty.results_overview_text())

        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="bez úkolu",
        )
        no_task = audit_export_context_service.build(audit)
        self.assertIn(NO_LINKED_TASKS_SENTENCE, no_task.overall_assessment_text())

        self._add_finding_with_task(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            due=date(2026, 10, 31),
            point_id="a",
        )
        with_due = audit_export_context_service.build(audit)
        self.assertIn(
            "Evidence obsahuje 1 otevřený navazující úkol. "
            "Nejzazší evidovaný termín otevřených úkolů je 31. 10. 2026.",
            with_due.overall_assessment_text(),
        )
        self._add_finding_with_task(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            due=None,
            point_id="b",
        )
        mixed = audit_export_context_service.build(audit)
        overview = mixed.results_overview_text()
        self.assertIn("Otevřené úkoly bez termínu: 1", overview)
        self.assertNotIn("Nejzazší evidovaný termín", overview)

    def test_audit_terminal_waiting_missing_and_batch(self) -> None:
        audit = self._create_audit()
        _finding, closed = self._add_finding_with_task(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            due=date(2026, 10, 1),
            point_id="c",
        )
        closed_row = task_service.get_task_by_id(closed.id)
        closed_row.completed = True
        closed_row.completed_date = date.today()
        closed_row.checked_date = date.today()
        task_service.repository.update(closed_row)
        terminal = audit_export_context_service.build(audit)
        self.assertIn(ALL_TASKS_TERMINAL_SENTENCE, terminal.overall_assessment_text())

        dangling = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="visící",
            source_control_point_id="dangle",
        )
        finding_service.update(dangling.id, task_id=888_002)
        with self.assertLogs(
            "core.shared.sluzby.control_report_task_deadlines",
            level="WARNING",
        ):
            still_terminal = audit_export_context_service.build(
                audit
            ).overall_assessment_text()
        self.assertIn(ALL_TASKS_TERMINAL_SENTENCE, still_terminal)
        self.assertNotIn("888002", still_terminal)

        context = audit_export_context_service.build(audit)
        with patch.object(
            AuditExportContext,
            "_activity_statistics",
            return_value=_EMPTY_STATS,
        ):
            with patch.object(
                task_service,
                "get_task_by_id",
                side_effect=AssertionError("N+1 get_task_by_id"),
            ):
                with patch.object(
                    task_service,
                    "get_tasks_by_ids",
                    wraps=task_service.get_tasks_by_ids,
                ) as batched:
                    context.overall_assessment_text()
                    context.results_overview_text()
        self.assertEqual(1, batched.call_count)

        protocol_ctx = audit_export_context_service.build(audit, AUDIT_PROTOCOL_CONFIG)
        detailed_ctx = audit_export_context_service.build(audit, AUDIT_DETAILED_CONFIG)
        self.assertEqual(
            protocol_ctx.overall_assessment_text(),
            detailed_ctx.overall_assessment_text(),
        )
        self.assertEqual(
            protocol_ctx.results_overview_text(),
            detailed_ctx.results_overview_text(),
        )
        protocol = _odt_content(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        for content in (protocol, detailed):
            self.assertIn(ALL_TASKS_TERMINAL_SENTENCE, content)


if __name__ == "__main__":
    unittest.main()
