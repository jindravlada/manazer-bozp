"""RISK-REVIEW-5: zpracování nevyhovujících bodů přes úkol nebo revizi opatření."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-5-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        ENTITY_RISK_MEASURE_REVIEW,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
        RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK,
        RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        RISK_MEASURE_REVIEW_RESOLUTION_REQUIRED,
        RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        RiskMeasureReviewError,
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from moduly.ukoly.modely.task import Task
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RR5",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR5",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Dana",
            last_name="Řešitelka",
        )
        self.group = ensure_exposed_group("Skupina RR5")
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Zábradlí",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Pád",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        self.measure = hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title="Oprava zábradlí",
        )
        self.identification = identification
        self.assessment = assessment
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_resolution_column_exists(self) -> None:
        self.assertIn("resolution", _table_columns("risk_measure_review_items"))

    def test_non_compliant_appears_in_tasks_tab(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[0].item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                    "note": "Chybí část zábradlí",
                }
            ],
        )
        dialog = RiskMeasureReviewExecutionDialog(
            review=risk_measure_review_service.get_by_id(self.review.id),
        )
        self.assertEqual(len(dialog.tasks._point_widgets), 1)
        point = dialog.tasks._point_widgets[0]
        self.assertEqual(point.row.measure_title, "Oprava zábradlí")
        self.assertIn("Chybí část zábradlí", point.row.note)
        self.assertEqual(
            point.row.resolution,
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
        )
        dialog._editor.mark_clean()
        dialog.close()

    def test_compliant_removes_from_tasks_tab(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                }
            ],
        )
        self.assertEqual(
            len(risk_measure_review_service.list_non_compliant_rows(self.review.id)),
            1,
        )
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                }
            ],
        )
        self.assertEqual(
            risk_measure_review_service.list_non_compliant_rows(self.review.id),
            [],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(self.review.id)[0]
        self.assertEqual(
            reloaded.resolution,
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
        )

    def test_create_task_for_non_compliant_item(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                    "note": "Domluvit termín opravy",
                }
            ],
        )
        task = risk_measure_review_service.create_task_for_checklist_item(
            self.review.id,
            item_id,
            title="Opravit zábradlí",
            description="Do konce týdne",
        )
        self.assertEqual(task.source_module, ENTITY_RISK_MEASURE_REVIEW)
        self.assertEqual(task.source_record_id, self.review.id)
        self.assertEqual(task.source_check_code, f"item:{item_id}")
        row = risk_measure_review_service.list_checklist_rows(self.review.id)[0]
        self.assertEqual(row.resolution, RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK)

    def test_mark_measure_revision(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                }
            ],
        )
        context = risk_measure_review_service.resolve_context_for_measure(
            self.measure.id
        )
        self.assertEqual(context["identification"].id, self.identification.id)
        self.assertEqual(context["assessment"].id, self.assessment.id)
        risk_measure_review_service.mark_measure_revision_for_item(item_id)
        row = risk_measure_review_service.list_checklist_rows(self.review.id)[0]
        self.assertEqual(
            row.resolution,
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
        )

    def test_cannot_complete_with_unresolved_non_compliant(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[0].item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                }
            ],
        )
        with self.assertRaises(RiskMeasureReviewError) as raised:
            risk_measure_review_service.update_review(
                self.review.id,
                review_date=date.today(),
                reviewer_person_id=self.reviewer.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
                status=RISK_MEASURE_REVIEW_STATUS_COMPLETED,
            )
        self.assertIn(RISK_MEASURE_REVIEW_RESOLUTION_REQUIRED, str(raised.exception))

    def test_complete_after_resolution(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                }
            ],
        )
        risk_measure_review_service.create_task_for_checklist_item(
            self.review.id,
            item_id,
            title="Náprava",
        )
        updated = risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            status=RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        )
        self.assertEqual(updated.status, RISK_MEASURE_REVIEW_STATUS_COMPLETED)


if __name__ == "__main__":
    unittest.main()
