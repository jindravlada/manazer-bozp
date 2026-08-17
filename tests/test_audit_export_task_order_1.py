"""AUDIT-EXPORT-TASK-ORDER-1 – řazení a číslování úkolů podle zjištění."""

from __future__ import annotations

import importlib
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-export-task-order-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_FINDING,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_export_task_order import (
        build_audit_export_task_items,
        finding_export_number_map,
        load_audit_export_task_items,
        ordered_audit_export_findings,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


def _finding(*, finding_id: int, display_order: int, task_id: int | None = None):
    return SimpleNamespace(id=finding_id, display_order=display_order, task_id=task_id)


def _task(*, task_id: int, due: date | None = None, title: str = ""):
    return SimpleNamespace(id=task_id, due_date=due, title=title or f"T{task_id}")


def _titles(items) -> list[str]:
    return [item.task.title for item in items]


def _numbers(items) -> list[int]:
    return [item.export_number for item in items]


class AuditExportTaskOrderHelperTestCase(unittest.TestCase):
    def test_finding_order_uses_display_order_not_id(self) -> None:
        findings = [
            _finding(finding_id=30, display_order=20),
            _finding(finding_id=10, display_order=40),
            _finding(finding_id=20, display_order=10),
        ]
        ordered = ordered_audit_export_findings(findings)
        self.assertEqual([item.id for item in ordered], [20, 30, 10])
        self.assertEqual(finding_export_number_map(findings), {20: 1, 30: 2, 10: 3})

    def test_tasks_follow_finding_export_order_with_stable_inner_sort(self) -> None:
        findings = [
            _finding(finding_id=1, display_order=10, task_id=101),
            _finding(finding_id=2, display_order=20, task_id=201),
            _finding(finding_id=3, display_order=30, task_id=None),
        ]
        tasks = {
            101: _task(task_id=101, due=date(2026, 9, 1), title="A-později"),
            102: _task(task_id=102, due=date(2026, 8, 1), title="A-dříve"),
            103: _task(task_id=103, due=date(2026, 10, 1), title="A-nejpozději"),
            201: _task(task_id=201, due=date(2026, 1, 1), title="B-první-termín"),
            202: _task(task_id=202, due=date(2026, 12, 1), title="B-druhý"),
            301: _task(task_id=301, due=date(2025, 1, 1), title="Nenavázaný"),
        }
        items = build_audit_export_task_items(
            ordered_findings=ordered_audit_export_findings(findings),
            tasks_by_id=tasks,
            source_tasks_by_finding_id={
                1: [tasks[102], tasks[103], tasks[101]],
                2: [tasks[202]],
            },
            unlinked_tasks=[tasks[301]],
        )
        self.assertEqual(_numbers(items), [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            _titles(items),
            [
                "A-dříve",
                "A-později",
                "A-nejpozději",
                "B-první-termín",
                "B-druhý",
                "Nenavázaný",
            ],
        )
        self.assertEqual(items[0].related_finding_numbers, (1,))
        self.assertEqual(items[3].related_finding_numbers, (2,))
        self.assertEqual(items[5].related_finding_numbers, ())

    def test_shared_task_appears_once_under_first_finding(self) -> None:
        shared = _task(task_id=9, due=date(2026, 6, 1), title="Sdílený")
        findings = [
            _finding(finding_id=1, display_order=10, task_id=9),
            _finding(finding_id=2, display_order=20, task_id=9),
        ]
        items = build_audit_export_task_items(
            ordered_findings=findings,
            tasks_by_id={9: shared},
            source_tasks_by_finding_id={},
            unlinked_tasks=[],
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].export_number, 1)
        self.assertEqual(items[0].related_finding_numbers, (1, 2))


class AuditExportTaskOrderIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        with get_session() as session:
            session.execute(delete(Task))
            session.commit()

    def tearDown(self) -> None:
        self.setUp()

    def _create_finding(self, audit_id: int, *, description: str, display_order: int):
        return finding_service.create(
            ENTITY_AUDITY,
            audit_id,
            finding_type=FINDING_TYPE_NESHODA,
            description=description,
            recommended_action=description,
            status=FINDING_STATUS_OTEVRENE,
            display_order=display_order,
        )

    def _extra_finding_task(
        self,
        finding_id: int,
        *,
        title: str,
        due: date,
        completed: bool = False,
        canceled: bool = False,
    ):
        return task_service.create_task(
            title=title,
            due_date=due,
            source_module=ENTITY_FINDING,
            source_record_id=finding_id,
            completed=completed,
            canceled=canceled,
        )

    def test_protocol_and_detailed_report_share_numbers(self) -> None:
        audit = audit_service.create_audit()
        finding_late = self._create_finding(
            audit.id, description="Druhé zjištění", display_order=20
        )
        finding_early = self._create_finding(
            audit.id, description="První zjištění", display_order=10
        )
        finding_empty = self._create_finding(
            audit.id, description="Bez úkolu", display_order=15
        )
        del finding_empty

        task_b = finding_task_service.create_task_from_finding(finding_late.id)
        task_service.update_task(
            task_b.id,
            title="Úkol B2",
            due_date=date(2026, 12, 1),
            responsible_person_id=None,
        )
        self._extra_finding_task(
            finding_late.id, title="Úkol B1", due=date(2026, 2, 1)
        )

        task_a = finding_task_service.create_task_from_finding(finding_early.id)
        task_service.update_task(
            task_a.id,
            title="Úkol A2",
            due_date=date(2026, 9, 1),
            responsible_person_id=None,
        )
        self._extra_finding_task(
            finding_early.id, title="Úkol A1", due=date(2026, 8, 1)
        )
        self._extra_finding_task(
            finding_early.id,
            title="Úkol A3 zrušený",
            due=date(2026, 10, 1),
            canceled=True,
        )
        completed = self._extra_finding_task(
            finding_late.id, title="Úkol B dokončený", due=date(2026, 3, 1)
        )
        task_service.update_task(
            completed.id,
            title="Úkol B dokončený",
            due_date=date(2026, 3, 1),
            responsible_person_id=None,
            completed=True,
            completed_date=date(2026, 3, 2),
            requires_verification=False,
        )
        task_service.create_task(
            title="Nenavázaný úkol",
            due_date=date(2026, 1, 1),
            source_module=ENTITY_AUDITY,
            source_record_id=audit.id,
        )

        protocol = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        )
        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        repeated = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        )
        self.assertEqual(protocol.tasks_text(), detailed.tasks_text())
        self.assertEqual(protocol.findings_text(), detailed.findings_text())
        self.assertEqual(protocol.tasks_text(), repeated.tasks_text())
        self.assertEqual(
            protocol.placeholder_values()["ukoly_text"],
            detailed.placeholder_values()["ukoly_text"],
        )
        self.assertEqual(
            protocol.placeholder_values()["zjisteni_text"],
            detailed.placeholder_values()["zjisteni_text"],
        )

        findings_text = protocol.findings_text()
        self.assertIn("1. Neshoda", findings_text)
        self.assertLess(
            findings_text.index("První zjištění"),
            findings_text.index("Bez úkolu"),
        )
        self.assertLess(
            findings_text.index("Bez úkolu"),
            findings_text.index("Druhé zjištění"),
        )
        self.assertNotIn("4. Neshoda", findings_text)

        tasks_text = protocol.tasks_text()
        numbered = re.findall(r"^(\d+)\. (.+)$", tasks_text, flags=re.M)
        self.assertEqual(
            numbered,
            [
                ("1", "Úkol A1"),
                ("2", "Úkol A2"),
                ("3", "Úkol A3 zrušený"),
                ("4", "Úkol B1"),
                ("5", "Úkol B dokončený"),
                ("6", "Úkol B2"),
                ("7", "Nenavázaný úkol"),
            ],
        )
        self.assertEqual(tasks_text, repeated.tasks_text())

    def test_findings_numbering_regression_ignores_database_id(self) -> None:
        audit = audit_service.create_audit()
        first_created = self._create_finding(
            audit.id, description="Vyšší ID, nižší pořadí", display_order=50
        )
        second_created = self._create_finding(
            audit.id, description="Nižší ID po úpravě pořadí", display_order=5
        )
        self.assertGreater(second_created.id, first_created.id)

        context = audit_export_context_service.build(audit)
        findings_text = context.findings_text()
        self.assertLess(
            findings_text.index("1. Neshoda"),
            findings_text.index("2. Neshoda"),
        )
        self.assertLess(
            findings_text.index("Nižší ID po úpravě pořadí"),
            findings_text.index("Vyšší ID, nižší pořadí"),
        )
        self.assertTrue(findings_text.strip().startswith("1. Neshoda"))
        self.assertIn("Nižší ID po úpravě pořadí", findings_text.split("2. Neshoda")[0])

    def test_shared_task_not_duplicated_and_export_is_read_only(self) -> None:
        audit = audit_service.create_audit()
        finding_a = self._create_finding(
            audit.id, description="Sdílené zjištění A", display_order=10
        )
        finding_b = self._create_finding(
            audit.id, description="Sdílené zjištění B", display_order=20
        )
        task = finding_task_service.create_task_from_finding(finding_a.id)
        task_service.update_task(
            task.id,
            title="Jediný sdílený úkol XYZ-77",
            responsible_person_id=None,
        )
        finding_service.update(finding_b.id, task_id=task.id)

        findings_before = [
            (item.id, item.task_id, item.updated_at, item.display_order)
            for item in finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        ]
        task_before = task_service.get_task_by_id(task.id)
        assert task_before is not None
        task_stamp = (task_before.updated_at, task_before.title)

        context = audit_export_context_service.build(audit)
        items = load_audit_export_task_items(
            audit.id, findings=finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].related_finding_numbers, (1, 2))
        numbered = re.findall(r"^(\d+)\. (.+)$", context.tasks_text(), flags=re.M)
        self.assertEqual(numbered, [("1", "Jediný sdílený úkol XYZ-77")])

        findings_after = [
            (item.id, item.task_id, item.updated_at, item.display_order)
            for item in finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        ]
        task_after = task_service.get_task_by_id(task.id)
        assert task_after is not None
        self.assertEqual(findings_before, findings_after)
        self.assertEqual(task_stamp, (task_after.updated_at, task_after.title))

    def test_load_does_not_query_tasks_per_finding(self) -> None:
        audit = audit_service.create_audit()
        finding_a = self._create_finding(audit.id, description="A", display_order=10)
        finding_b = self._create_finding(audit.id, description="B", display_order=20)
        finding_task_service.create_task_from_finding(finding_a.id)
        finding_task_service.create_task_from_finding(finding_b.id)
        self._extra_finding_task(finding_a.id, title="A2", due=date(2026, 8, 2))
        task_service.create_task(
            title="Volný",
            source_module=ENTITY_AUDITY,
            source_record_id=audit.id,
        )
        findings = finding_service.get_for_entity(ENTITY_AUDITY, audit.id)

        with (
            patch.object(
                task_service,
                "get_task_by_id",
                side_effect=AssertionError("N+1 get_task_by_id"),
            ),
            patch.object(
                task_service,
                "get_tasks_by_ids",
                wraps=task_service.get_tasks_by_ids,
            ) as by_ids,
            patch.object(
                task_service,
                "list_by_sources",
                wraps=task_service.list_by_sources,
            ) as by_sources,
            patch.object(
                task_service,
                "list_by_source",
                wraps=task_service.list_by_source,
            ) as by_source,
        ):
            items = load_audit_export_task_items(audit.id, findings=findings)

        self.assertEqual(len(items), 4)
        self.assertEqual(by_ids.call_count, 1)
        self.assertEqual(by_sources.call_count, 1)
        self.assertEqual(by_source.call_count, 1)


if __name__ == "__main__":
    unittest.main()
