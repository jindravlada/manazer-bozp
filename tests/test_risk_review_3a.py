"""RISK-REVIEW-3a: sjednocení evidence úkolů s Auditem."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-3a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        ENTITY_RISK_MEASURE_REVIEW,
        RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
        RISK_MEASURE_REVIEW_TASKS_TITLE,
    )
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_tasks_widget import (
        RiskMeasureReviewTasksWidget,
    )
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


class RiskReview3aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RR3a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR3a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Petr",
            last_name="Úkolový",
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_execution_dialog_has_checklist_and_tasks_tabs(self) -> None:
        dialog = RiskMeasureReviewExecutionDialog(review=self.review)
        titles = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(titles, [RISK_MEASURE_REVIEW_CHECKLIST_TITLE, RISK_MEASURE_REVIEW_TASKS_TITLE])
        self.assertTrue(hasattr(dialog, "checklist"))
        self.assertTrue(hasattr(dialog, "tasks"))
        self.assertFalse(hasattr(dialog, "findings"))
        dialog._editor.mark_clean()
        dialog.close()

    def test_get_tasks_for_review_empty(self) -> None:
        self.assertEqual(risk_measure_review_service.get_tasks_for_review(self.review.id), [])

    def test_create_and_list_task_linked_to_review(self) -> None:
        task = risk_measure_review_service.create_task_for_review(
            self.review.id,
            title="Doplnit kryt",
            description="Po přezkoumání",
            due_date=date(2026, 8, 1),
        )
        self.assertEqual(task.source_module, ENTITY_RISK_MEASURE_REVIEW)
        self.assertEqual(task.source_record_id, self.review.id)
        self.assertEqual(task.source_check_code, "")

        tasks = risk_measure_review_service.get_tasks_for_review(self.review.id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, task.id)
        self.assertEqual(tasks[0].title, "Doplnit kryt")

    def test_task_can_prepare_control_point_link(self) -> None:
        task = risk_measure_review_service.create_task_for_review(
            self.review.id,
            title="Bod checklistu",
            source_check_code="item:42",
        )
        self.assertEqual(task.source_check_code, "item:42")
        self.assertEqual(task.source_module, ENTITY_RISK_MEASURE_REVIEW)
        self.assertEqual(task.source_record_id, self.review.id)

    def test_tasks_widget_lists_linked_tasks(self) -> None:
        risk_measure_review_service.create_task_for_review(
            self.review.id,
            title="První úkol",
        )
        risk_measure_review_service.create_task_for_review(
            self.review.id,
            title="Druhý úkol",
        )
        other = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
        )
        risk_measure_review_service.create_task_for_review(
            other.id,
            title="Cizí úkol",
        )

        widget = RiskMeasureReviewTasksWidget()
        widget.set_review_id(self.review.id)
        self.assertEqual(widget.table.rowCount(), 2)

        titles = {
            widget.table.item(row, 1).text()
            for row in range(widget.table.rowCount())
        }
        self.assertIn("První úkol", titles)
        self.assertIn("Druhý úkol", titles)
        self.assertNotIn("Cizí úkol", titles)

    def test_tasks_widget_empty_state(self) -> None:
        widget = RiskMeasureReviewTasksWidget()
        widget.set_review_id(self.review.id)
        self.assertEqual(widget.table.rowCount(), 0)
        self.assertEqual(widget.empty_label.text(), "Přezkoumání zatím nemá žádné úkoly.")

    def test_no_finding_entities_in_service_api(self) -> None:
        self.assertFalse(hasattr(risk_measure_review_service, "list_findings"))
        self.assertFalse(hasattr(risk_measure_review_service, "sync_findings_from_checklist"))
        self.assertFalse(hasattr(risk_measure_review_service, "ensure_finding_for_note_number"))


if __name__ == "__main__":
    unittest.main()
