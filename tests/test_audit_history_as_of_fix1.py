"""AUDIT-HISTORY-AS-OF-FIX1: historie jen dříve zahájené audity stejného provozu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-history-as-of-fix1-"))

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
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_INTRO_FIRST_AUDIT_MESSAGE,
        AUDIT_STATUS_PROBIHA,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_history_service import audit_history_service
    from moduly.audity.sluzby.audit_intro_export_service import (
        audit_intro_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_workplace_history_widget import (
        AuditWorkplaceHistoryWidget,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class AuditHistoryAsOfFix1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(name=f"Provoz-A-{suffix}")
        self.other = settings_service.save_workplace(name=f"Provoz-B-{suffix}")
        self.worker = settings_service.save_worker(
            first_name="Jan", last_name=f"H-{suffix}"
        )

    def _create(self, *, workplace=None, **fields):
        workplace = workplace or self.workplace
        payload = {
            "workplace_id": workplace.id,
            "workplace_name": workplace.name,
            "year": 2026,
        }
        payload.update(fields)
        return audit_service.create_audit(**payload)

    def _ids(self, history) -> list[int]:
        return [item.audit_id for item in history.previous_audits]

    def test_planned_2028_not_history_of_2026(self) -> None:
        current = self._create(
            year=2026,
            started_at=date(2026, 8, 12),
            finished_at=date(2026, 8, 14),
        )
        planned = self._create(year=2028, planned_month=4)
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(planned.id, self._ids(history))
        self.assertTrue(history.is_first_audit)

    def test_later_started_2028_not_shown(self) -> None:
        current = self._create(year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14))
        later = self._create(year=2028, started_at=date(2028, 1, 10))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(later.id, self._ids(history))

    def test_earlier_started_is_shown(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1), finished_at=date(2025, 3, 2))
        current = self._create(year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertEqual(self._ids(history), [earlier.id])
        self.assertFalse(history.is_first_audit)

    def test_earlier_in_progress_keeps_real_status(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 6, 1))
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        self.assertEqual(earlier.status, AUDIT_STATUS_PROBIHA)
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertEqual(history.previous_audits[0].status, AUDIT_STATUS_PROBIHA)
        self.assertEqual(history.previous_audits[0].audit_id, earlier.id)

    def test_current_not_listed_as_own_history(self) -> None:
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(current.id, self._ids(history))

    def test_other_workplace_excluded(self) -> None:
        other = self._create(
            workplace=self.other,
            year=2025,
            started_at=date(2025, 1, 1),
            finished_at=date(2025, 1, 2),
        )
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(other.id, self._ids(history))

    def test_planned_without_started_at_never_history(self) -> None:
        planned = self._create(year=2027, planned_month=1)
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertNotIn(planned.id, self._ids(history))

    def test_current_without_as_of_is_safely_empty(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1))
        current = self._create(year=2026, planned_month=4)
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertEqual(self._ids(history), [])
        self.assertTrue(history.is_first_audit)
        self.assertNotIn(earlier.id, self._ids(history))

    def test_visit_planned_date_used_when_current_not_started(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1), finished_at=date(2025, 3, 2))
        program = audit_program_service.create_program(
            name="Program as-of",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
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
            planned_month=6,
            planned_date=date(2026, 6, 15),
        )
        current = self._create(
            year=2026,
            program_id=program.id,
            program_visit_id=visit.id,
        )
        self.assertIsNone(current.started_at)
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertEqual(self._ids(history), [earlier.id])

    def test_history_order_newest_previous_first(self) -> None:
        oldest = self._create(year=2024, started_at=date(2024, 1, 1), finished_at=date(2024, 1, 2))
        middle = self._create(year=2025, started_at=date(2025, 6, 1), finished_at=date(2025, 6, 2))
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertEqual(self._ids(history), [middle.id, oldest.id])

    def test_findings_and_tasks_only_from_selected_previous(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1), finished_at=date(2025, 3, 2))
        later = self._create(year=2028, started_at=date(2028, 2, 1))
        current = self._create(year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14))
        finding = finding_service.create(
            ENTITY_AUDITY,
            earlier.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Historické zjištění 2025",
            status=FINDING_STATUS_OTEVRENE,
        )
        future_finding = finding_service.create(
            ENTITY_AUDITY,
            later.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění 2028",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = task_service.create_task(
            title="Historický úkol 2025",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 4, 1),
        )
        future_task = task_service.create_task(
            title="Úkol 2028",
            responsible_person_id=self.worker.id,
            due_date=date(2028, 3, 1),
        )
        finding_service.update(finding.id, task_id=task.id)
        finding_service.update(future_finding.id, task_id=future_task.id)

        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        titles = {item.title for item in history.findings}
        self.assertIn("Historické zjištění 2025", titles)
        self.assertNotIn("Zjištění 2028", titles)
        task_titles = {item.title for item in history.tasks}
        self.assertTrue(any("Historický úkol 2025" in title for title in task_titles))
        self.assertFalse(any("Úkol 2028" in title for title in task_titles))

    def test_future_audit_does_not_change_older_detailed_report(self) -> None:
        current = self._create(
            year=2026,
            started_at=date(2026, 8, 12),
            finished_at=date(2026, 8, 14),
        )
        before = audit_export_context_service.build(
            current, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self._create(year=2028, planned_month=1)
        later = self._create(year=2028, started_at=date(2028, 1, 10))
        after = audit_export_context_service.build(
            current, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self.assertEqual(before, after)
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, after)
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(current)
        )
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, content)
        self.assertNotIn(str(later.number or later.id), content)

    def test_future_audit_does_not_change_continuity_aggregate(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1), finished_at=date(2025, 3, 2))
        current = self._create(year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14))
        finding_service.create(
            ENTITY_AUDITY,
            earlier.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Jen 2025",
            status=FINDING_STATUS_OTEVRENE,
        )
        first = audit_history_service.aggregate_continuity_for_audits([current])
        self._create(year=2028, planned_month=4)
        later = self._create(year=2028, started_at=date(2028, 2, 1))
        finding_service.create(
            ENTITY_AUDITY,
            later.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění budoucí",
            status=FINDING_STATUS_OTEVRENE,
        )
        second = audit_history_service.aggregate_continuity_for_audits([current])
        self.assertEqual(first, second)
        self.assertEqual(first.previous_audits_count, 1)
        self.assertEqual(first.findings_total_count, 1)
        text = audit_intro_export_service.build_continuity_text_for_audits([current])
        self.assertIn("Počet dohledaných předchozích auditů: 1", text)
        self.assertNotIn("Zjištění budoucí", text)

    def test_first_audit_uses_existing_message(self) -> None:
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        history = audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        self.assertTrue(history.is_first_audit)
        text = audit_intro_export_service.build_detailed_intro_text(current)
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, text)

    def test_open_and_export_do_not_write(self) -> None:
        current = self._create(year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14))
        before = audit_service.get_by_id(current.id)
        assert before is not None
        stamp = before.updated_at
        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(current)
        widget.refresh()
        audit_history_service.get_workplace_history(
            self.workplace.id, current_audit=current
        )
        protokol_audit_service.generate_detailed_report_for_audit(current)
        after = audit_service.get_by_id(current.id)
        assert after is not None
        self.assertEqual(after.updated_at, stamp)

    def test_no_n_plus_one_or_methodology_load(self) -> None:
        earlier = self._create(year=2025, started_at=date(2025, 3, 1), finished_at=date(2025, 3, 2))
        current = self._create(year=2026, started_at=date(2026, 8, 12))
        finding_service.create(
            ENTITY_AUDITY,
            earlier.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Batch",
            status=FINDING_STATUS_OTEVRENE,
        )
        with (
            patch(
                "moduly.audity.sluzby.audit_history_service.finding_service.get_for_entities",
                wraps=finding_service.get_for_entities,
            ) as findings,
            patch(
                "moduly.audity.sluzby.audit_knowledge_service.AuditKnowledgeService.ensure_catalogs"
            ) as ensure,
            patch(
                "moduly.audity.sluzby.audit_knowledge_service.AuditKnowledgeService.get_knowledge_tree"
            ) as tree,
        ):
            audit_history_service.get_workplace_history(
                self.workplace.id, current_audit=current
            )
            self.assertEqual(findings.call_count, 1)
            ensure.assert_not_called()
            tree.assert_not_called()

    def test_widget_hides_planned_2028(self) -> None:
        current = self._create(
            year=2026, started_at=date(2026, 8, 12), finished_at=date(2026, 8, 14)
        )
        self._create(year=2028, planned_month=4)
        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(current)
        widget.refresh()
        self.assertEqual(widget._audits_table.rowCount(), 0)
        self.assertTrue(widget._history is not None and widget._history.is_first_audit)
        self.assertFalse(widget._first_audit_label.isHidden())


if __name__ == "__main__":
    unittest.main()
