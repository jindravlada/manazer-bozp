"""UX-TABLE-1c – typované řazení tabulek Auditů a Prověrek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())

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
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.finding_display import finding_status_label
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import (
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
    from moduly.audity.ui.audit_table import AuditTable
    from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget
    from moduly.proverky.constants import (
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_findings_widget import (
        BozpInspectionFindingsWidget,
    )
    from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
    from moduly.ukoly.sluzby.task_service import task_service


def _column_texts(table, column: int) -> list[str]:
    return [table.item(row, column).text() for row in range(table.rowCount())]


def _column_ids(table, column: int = 0) -> list[int]:
    return [int(table.item(row, column).text()) for row in range(table.rowCount())]


class UxTable1cAuditySortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def test_audit_list_czech_workplace_names(self) -> None:
        a = audit_service.create_audit(workplace_name="Chalupa", year=2026)
        b = audit_service.create_audit(workplace_name="Cibule", year=2026)
        c = audit_service.create_audit(workplace_name="Hrášek", year=2026)

        table = AuditTable()
        table.load_audits(audit_service.get_all())
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 4), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table), [b.id, c.id, a.id])

        table.sortItems(4, Qt.SortOrder.DescendingOrder)
        self.assertEqual(_column_texts(table, 4), ["Chalupa", "Hrášek", "Cibule"])

    def test_audit_list_date_sort(self) -> None:
        mid = audit_service.create_audit(
            workplace_name="A",
            year=2026,
            audit_date=date(2026, 3, 15),
        )
        early = audit_service.create_audit(
            workplace_name="B",
            year=2026,
            audit_date=date(2026, 1, 5),
        )
        late = audit_service.create_audit(
            workplace_name="C",
            year=2026,
            audit_date=date(2026, 7, 1),
        )

        table = AuditTable()
        table.load_audits(audit_service.get_all())
        table.sortItems(5, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [early.id, mid.id, late.id])

    def test_audit_list_status_workflow_order(self) -> None:
        done = audit_service.create_audit(
            workplace_name="Hotovo",
            year=2026,
            started_at=date(2026, 1, 1),
            finished_at=date(2026, 1, 2),
        )
        planned = audit_service.create_audit(workplace_name="Plán", year=2026)
        running = audit_service.create_audit(
            workplace_name="Běží",
            year=2026,
            started_at=date(2026, 2, 1),
        )
        self.assertEqual(planned.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(running.status, AUDIT_STATUS_PROBIHA)
        self.assertEqual(done.status, AUDIT_STATUS_DOKONCENO)

        table = AuditTable()
        table.load_audits([done, planned, running])
        table.sortItems(6, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, 6),
            [AUDIT_STATUS_PLANOVANO, AUDIT_STATUS_PROBIHA, AUDIT_STATUS_DOKONCENO],
        )
        self.assertEqual(_column_ids(table), [planned.id, running.id, done.id])

    def test_audit_list_opens_correct_record_after_sort(self) -> None:
        target = audit_service.create_audit(workplace_name="Cibule", year=2026)
        audit_service.create_audit(workplace_name="Chalupa", year=2026)

        table = AuditTable()
        table.load_audits(audit_service.get_all())
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        selected = table.selectionModel().selectedRows()
        self.assertEqual(int(table.item(selected[0].row(), 0).text()), target.id)

    def test_audit_list_refresh_keeps_active_sort(self) -> None:
        audit_service.create_audit(workplace_name="Chalupa", year=2026)
        audit_service.create_audit(workplace_name="Cibule", year=2026)

        table = AuditTable()
        table.load_audits(audit_service.get_all())
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 4)[0], "Cibule")

        audit_service.create_audit(workplace_name="Hrášek", year=2026)
        table.load_audits(audit_service.get_all())
        self.assertEqual(_column_texts(table, 4), ["Cibule", "Hrášek", "Chalupa"])

    def test_audit_tasks_due_date_and_status(self) -> None:
        audit = audit_service.create_audit(workplace_name="Úkoly", year=2026)
        finding_late = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Pozdě",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_early = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Brzy",
            status=FINDING_STATUS_OTEVRENE,
        )
        task_late = finding_task_service.create_task_from_finding(finding_late.id)
        task_early = finding_task_service.create_task_from_finding(finding_early.id)
        task_service.update_task(
            task_id=task_late.id,
            title=task_late.title,
            due_date=date(2026, 8, 1),
        )
        task_service.update_task(
            task_id=task_early.id,
            title=task_early.title,
            due_date=date(2026, 2, 1),
        )
        task_service.update_task(
            task_id=task_late.id,
            title=task_late.title,
            due_date=date(2026, 8, 1),
            completed=True,
            completed_date=date(2026, 8, 2),
        )

        widget = AuditTasksWidget()
        widget.set_audit_id(audit.id)
        table = widget.table
        self.assertEqual(table.rowCount(), 2)

        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [task_early.id, task_late.id])

        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        statuses = _column_texts(table, 4)
        self.assertEqual(statuses[0], "Aktivní")
        self.assertEqual(statuses[1], "Ukončeno")

        table.selectRow(0)
        self.assertEqual(widget._selected_task_id(), int(table.item(0, 0).text()))

    def test_audit_findings_status_order_and_open(self) -> None:
        audit = audit_service.create_audit(workplace_name="Zjištění", year=2026)
        resolved = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Hotovo",
            status=FINDING_STATUS_VYPORADANO,
        )
        open_finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )
        in_progress = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="V procesu",
            status=FINDING_STATUS_V_PROCESU,
        )

        widget = AuditFindingsWidget()
        widget.set_audit_id(audit.id)
        table = widget.table
        table.sortItems(8, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, 8),
            [
                finding_status_label(FINDING_STATUS_OTEVRENE),
                finding_status_label(FINDING_STATUS_V_PROCESU),
                finding_status_label(FINDING_STATUS_VYPORADANO),
            ],
        )
        self.assertEqual(
            _column_ids(table),
            [open_finding.id, in_progress.id, resolved.id],
        )
        table.selectRow(0)
        self.assertEqual(widget._selected_finding_id(), open_finding.id)


class UxTable1cProverkySortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _row(self, inspection):
        class Row:
            def __init__(self, item):
                self.id = item.id
                self.number = item.number
                self.inspection_date = item.inspection_date
                self.workplace_name = item.workplace_name
                self.lead_inspector_name = ""
                self.findings_count = bozp_inspection_service.findings_count(item.id)
                self.status = item.status
                self.title = item.title or f"Prověrka {uuid.uuid4().hex[:4]}"

        return Row(inspection)

    def test_inspection_list_czech_workplace_names(self) -> None:
        a = bozp_inspection_service.create_inspection(
            workplace_name="Chalupa",
            year=2026,
            title="A",
        )
        b = bozp_inspection_service.create_inspection(
            workplace_name="Cibule",
            year=2026,
            title="B",
        )
        c = bozp_inspection_service.create_inspection(
            workplace_name="Hrášek",
            year=2026,
            title="C",
        )

        table = BozpInspectionTable()
        table.load_inspections([self._row(a), self._row(b), self._row(c)])
        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 3), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table), [b.id, c.id, a.id])

    def test_inspection_list_date_sort(self) -> None:
        mid = bozp_inspection_service.create_inspection(
            workplace_name="A",
            year=2026,
            inspection_date=date(2026, 3, 15),
            title="Mid",
        )
        early = bozp_inspection_service.create_inspection(
            workplace_name="B",
            year=2026,
            inspection_date=date(2026, 1, 5),
            title="Early",
        )
        late = bozp_inspection_service.create_inspection(
            workplace_name="C",
            year=2026,
            inspection_date=date(2026, 7, 1),
            title="Late",
        )

        table = BozpInspectionTable()
        table.load_inspections([self._row(mid), self._row(early), self._row(late)])
        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [early.id, mid.id, late.id])

    def test_inspection_list_status_workflow_order(self) -> None:
        done = bozp_inspection_service.create_inspection(
            workplace_name="Hotovo",
            year=2026,
            started_at=date(2026, 1, 1),
            finished_at=date(2026, 1, 2),
            title="Done",
        )
        planned = bozp_inspection_service.create_inspection(
            workplace_name="Plán",
            year=2026,
            title="Plan",
        )
        running = bozp_inspection_service.create_inspection(
            workplace_name="Běží",
            year=2026,
            started_at=date(2026, 2, 1),
            title="Run",
        )
        self.assertEqual(planned.status, INSPECTION_STATUS_PLANOVANO)
        self.assertEqual(running.status, INSPECTION_STATUS_PROBIHA)
        self.assertEqual(done.status, INSPECTION_STATUS_DOKONCENO)

        table = BozpInspectionTable()
        table.load_inspections([self._row(done), self._row(planned), self._row(running)])
        table.sortItems(6, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, 6),
            [
                INSPECTION_STATUS_PLANOVANO,
                INSPECTION_STATUS_PROBIHA,
                INSPECTION_STATUS_DOKONCENO,
            ],
        )
        self.assertEqual(_column_ids(table), [planned.id, running.id, done.id])

    def test_inspection_opens_correct_record_after_sort(self) -> None:
        target = bozp_inspection_service.create_inspection(
            workplace_name="Cibule",
            year=2026,
            title="Target",
        )
        bozp_inspection_service.create_inspection(
            workplace_name="Chalupa",
            year=2026,
            title="Other",
        )

        table = BozpInspectionTable()
        table.load_inspections(
            [self._row(item) for item in bozp_inspection_service.get_all()]
        )
        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        selected = table.selectionModel().selectedRows()
        self.assertEqual(int(table.item(selected[0].row(), 0).text()), target.id)

    def test_inspection_refresh_keeps_active_sort(self) -> None:
        first = bozp_inspection_service.create_inspection(
            workplace_name="Chalupa",
            year=2026,
            title="1",
        )
        second = bozp_inspection_service.create_inspection(
            workplace_name="Cibule",
            year=2026,
            title="2",
        )

        table = BozpInspectionTable()
        table.load_inspections([self._row(first), self._row(second)])
        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 3)[0], "Cibule")

        third = bozp_inspection_service.create_inspection(
            workplace_name="Hrášek",
            year=2026,
            title="3",
        )
        table.load_inspections([self._row(first), self._row(second), self._row(third)])
        self.assertEqual(_column_texts(table, 3), ["Cibule", "Hrášek", "Chalupa"])

    def test_inspection_findings_type_and_status_domain_order(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Nález",
            year=2026,
            title="Findings",
        )
        resolved = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Hotovo",
            status=FINDING_STATUS_VYPORADANO,
            source_area_label="Oblast Chalupa",
        )
        open_finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Otevřené",
            status=FINDING_STATUS_OTEVRENE,
            source_area_label="Oblast Cibule",
        )
        in_progress = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="V procesu",
            status=FINDING_STATUS_V_PROCESU,
            source_area_label="Oblast Hrášek",
        )

        widget = BozpInspectionFindingsWidget()
        widget.set_inspection_id(inspection.id)
        table = widget.table

        table.sortItems(8, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_ids(table),
            [open_finding.id, in_progress.id, resolved.id],
        )

        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, 3),
            ["Oblast Cibule", "Oblast Hrášek", "Oblast Chalupa"],
        )
        table.selectRow(0)
        self.assertEqual(widget._selected_finding_id(), open_finding.id)


if __name__ == "__main__":
    unittest.main()
