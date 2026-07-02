import importlib
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

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
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_PROGRAM_DASHBOARD_FILTER_OPEN_ONLY,
        AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS,
        AUDIT_PROGRAM_DASHBOARD_TAB_TASKS,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_program_dashboard_service import (
        audit_program_dashboard_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


class AuditProgramDashboardServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {suffix}",
            address="",
            note="",
            active=True,
        )

    def _create_program_with_audit(self):
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self.workplace.id,
            planned_year=2026,
            planned_month=4,
        )
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            program_id=program.id,
            program_visit_id=visit.id,
        )
        visit.audit_id = audit.id
        audit_program_service.repository.update_visit(visit)
        return program, audit, visit

    def test_get_program_findings_only_for_program(self) -> None:
        program, audit, _visit = self._create_program_with_audit()
        other_program = audit_program_service.create_program(
            name="Jiný program",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        other_audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            program_id=other_program.id,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění programu",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_AUDITY,
            other_audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Cizí zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )

        findings = audit_program_dashboard_service.get_program_findings(program.id)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].title, "Zjištění programu")
        self.assertEqual(findings[0].audit_id, audit.id)
        self.assertEqual(findings[0].workplace_name, self.workplace.name)

    def test_get_program_tasks_and_summary(self) -> None:
        program, audit, _visit = self._create_program_with_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Kritické zjištění",
            status=FINDING_STATUS_OTEVRENE,
            due_date=date(2020, 1, 1),
        )
        task = task_service.create_task(
            title="Nápravné opatření",
            responsible_person_id=None,
            due_date=date(2020, 2, 1),
        )
        finding_service.update(finding.id, task_id=task.id)
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Uzavřené zjištění",
            status=FINDING_STATUS_VYPORADANO,
        )

        tasks = audit_program_dashboard_service.get_program_tasks(program.id)
        summary = audit_program_dashboard_service.get_program_summary(program.id)

        self.assertEqual(len(tasks), 1)
        self.assertIn("Nápravné opatření", tasks[0].title)
        self.assertEqual(summary.findings_total, 2)
        self.assertEqual(summary.findings_open, 1)
        self.assertEqual(summary.findings_overdue, 1)
        self.assertEqual(summary.findings_critical, 1)
        self.assertEqual(summary.tasks_total, 1)
        self.assertEqual(summary.tasks_open, 1)
        self.assertEqual(summary.tasks_overdue, 1)

    def test_finding_filters_open_and_severe(self) -> None:
        program, audit, _visit = self._create_program_with_audit()
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda otevřená",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type="prilezitost_zlepseni",
            description="PKZ otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )

        findings = audit_program_dashboard_service.get_program_findings(program.id)
        open_only = [item for item in findings if item.is_open]
        severe_only = [item for item in open_only if item.is_severe]

        self.assertEqual(len(open_only), 2)
        self.assertEqual(len(severe_only), 1)
        self.assertEqual(severe_only[0].title, "Neshoda otevřená")


class AuditProgramDashboardWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        self.workplace = settings_service.save_workplace(
            name="Provoz dashboard",
            address="",
            note="",
            active=True,
        )

    def test_widget_has_findings_and_tasks_tabs(self) -> None:
        from moduly.audity.ui.audit_program_dashboard_widget import AuditProgramDashboardWidget

        widget = AuditProgramDashboardWidget()
        self.assertEqual(widget._tabs.tabText(0), AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS)
        self.assertEqual(widget._tabs.tabText(1), AUDIT_PROGRAM_DASHBOARD_TAB_TASKS)
        self.assertTrue(widget._filter_open_only.isChecked())

    def test_widget_loads_program_summary(self) -> None:
        from moduly.audity.ui.audit_program_dashboard_widget import AuditProgramDashboardWidget

        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
        )
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            program_id=program.id,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Test zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )

        widget = AuditProgramDashboardWidget()
        widget.load_program(program.id)

        self.assertIn("Celkem zjištění: 1", widget._summary_label.text())
        self.assertEqual(widget._findings_table.rowCount(), 1)
        self.assertEqual(
            widget._findings_table.item(0, 5).text(),
            "Test zjištění",
        )

    def test_open_only_filter_hides_resolved(self) -> None:
        from moduly.audity.ui.audit_program_dashboard_widget import AuditProgramDashboardWidget

        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
        )
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            program_id=program.id,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Uzavřené",
            status=FINDING_STATUS_VYPORADANO,
        )

        widget = AuditProgramDashboardWidget()
        widget.load_program(program.id)

        self.assertEqual(widget._findings_table.rowCount(), 1)
        self.assertEqual(widget._filter_open_only.text(), AUDIT_PROGRAM_DASHBOARD_FILTER_OPEN_ONLY)


if __name__ == "__main__":
    unittest.main()
