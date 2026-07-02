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

    import core.services.editable_catalog_service as editable_catalog_module

    importlib.reload(editable_catalog_module)

    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
        AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
        AUDIT_STATUS_DOKONCENO,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        TAB_WORKPLACE_HISTORY,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_history_service import audit_history_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


class AuditWorkplaceHistoryServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

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
        self.leader_id = settings_service.save_worker(
            first_name="Jan",
            last_name=f"Novák-{suffix}",
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Králová-{suffix}",
        ).id
        from moduly.nastaveni.sluzby.person_service import person_service

        self.union_id = person_service.create_person(
            first_name="Lucie",
            last_name=f"Horáková-{suffix}",
        ).id

    def _create_completed_audit(
        self,
        *,
        audit_date: date,
        workplace_id: int | None = None,
        process_id: str = "rizeni_rizik",
    ):
        workplace_id = workplace_id or self.workplace.id
        audit = audit_service.create_audit(
            workplace_id=workplace_id,
            workplace_name=self.workplace.name,
            year=audit_date.year,
            planned_month=audit_date.month,
            audit_date=audit_date,
            finished_at=audit_date,
        )
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "Eva Králová",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
            ],
        )
        process = audit_knowledge_service.get_process_by_id(process_id)
        assert process is not None
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=process_id,
                area_label=process.nazev,
                section_id="sekce",
                section_label="Sekce",
                control_point_id="bod-1",
                control_point_label="Kontrolní bod",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        return audit

    def test_last_audit_and_ignore_current(self) -> None:
        older = self._create_completed_audit(audit_date=date(2025, 10, 15))
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            audit_date=date(2026, 4, 15),
        )

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )

        assert history.last_audit is not None
        self.assertEqual(history.last_audit.audit_id, older.id)
        self.assertEqual(history.last_audit.audit_date, date(2025, 10, 15))
        self.assertIn("Jan Novák", history.last_audit.leader_name)

    def test_open_findings_and_tasks(self) -> None:
        audit = self._create_completed_audit(audit_date=date(2025, 10, 15))
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Chybí revize OOPP",
            status=FINDING_STATUS_OTEVRENE,
            due_date=date(2026, 1, 31),
        )
        task = task_service.create_task(
            title="Doplnit revize OOPP",
            responsible_person_id=self.workplace_rep_id,
            due_date=date(2026, 2, 15),
        )
        finding_service.update(finding.id, task_id=task.id)

        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )

        self.assertEqual(len(history.findings), 1)
        self.assertEqual(history.findings[0].title, "Chybí revize OOPP")
        self.assertEqual(history.findings[0].severity_label, "Neshoda")
        self.assertEqual(len(history.tasks), 1)
        self.assertIn("Doplnit revize OOPP", history.tasks[0].title)

    def test_resolved_findings_are_excluded(self) -> None:
        audit = self._create_completed_audit(audit_date=date(2025, 10, 15))
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Uzavřené zjištění",
            status=FINDING_STATUS_VYPORADANO,
        )
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )

        self.assertEqual(len(history.findings), 0)

    def test_process_history_from_control_results_and_program(self) -> None:
        self._create_completed_audit(
            audit_date=date(2026, 4, 15),
            process_id="rizeni_rizik",
        )

        program = audit_program_service.create_program(
            name="Program 2026",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
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
            planned_month=10,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="rizeni_dokumentovanych_informaci",
            process_name="Řízení dokumentovaných informací",
        )
        visit.status = AUDIT_PROGRAM_VISIT_STATUS_COMPLETED
        audit_program_service.repository.update_visit(visit)
        for visit_process in audit_program_service.repository.list_visit_processes(visit.id):
            visit_process.status = AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
            audit_program_service.repository.update_visit_process(visit_process)

        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=5,
        )

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )

        by_process = {item.process_id: item for item in history.process_history}
        self.assertEqual(by_process["rizeni_rizik"].last_audit_label, "Duben 2026")
        self.assertEqual(by_process["rizeni_dokumentovanych_informaci"].last_audit_label, "Říjen 2026")
        never_audited = [
            item for item in history.process_history if item.last_audit_date is None
        ]
        self.assertGreater(len(never_audited), 0)
        self.assertEqual(never_audited[0].last_audit_label, "Nikdy")

    def test_summary_counts(self) -> None:
        audit = self._create_completed_audit(audit_date=date(2025, 10, 15))
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )

        self.assertEqual(history.summary.last_audit_date, date(2025, 10, 15))
        self.assertEqual(history.summary.open_findings_count, 1)
        self.assertGreater(history.summary.total_processes_count, 0)
        self.assertGreaterEqual(
            history.summary.audited_processes_count,
            1,
        )


class AuditWorkplaceHistoryWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

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

    def test_dialog_has_history_tab(self) -> None:
        from moduly.audity.constants import TAB_LABELS
        from moduly.audity.ui.audit_dialog import AuditDialog

        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        dialog = AuditDialog(audit=audit)

        self.assertEqual(dialog.tabs.count(), 7)
        self.assertEqual(dialog.tabs.tabText(3), TAB_WORKPLACE_HISTORY)
        self.assertIsNotNone(dialog.history_widget)

    def test_history_widget_loads_summary(self) -> None:
        from moduly.audity.ui.audit_workplace_history_widget import AuditWorkplaceHistoryWidget

        previous = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=10,
            audit_date=date(2025, 10, 15),
            finished_at=date(2025, 10, 15),
        )
        self.assertEqual(previous.status, AUDIT_STATUS_DOKONCENO)

        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )

        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(current)

        self.assertIn("15.10.2025", widget._summary_label.text())
        self.assertIn("Poslední audit", widget._summary_label.text())


if __name__ == "__main__":
    unittest.main()
