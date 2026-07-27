"""RISK-REVIEW-2: generování checklistu přezkoumání opatření."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-2-"))
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
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.repository.risk_measure_review_item_repository import (
        RiskMeasureReviewItemRepository,
    )
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
        risk_measure_review_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )
        from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
        from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem

        with get_session() as session:
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RR2",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.workplace_part = settings_service.save_workplace(
            name="Úsek RR2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.other_workplace = settings_service.save_workplace(
            name="Jiná dílna RR2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Jana",
            last_name="Kontrola",
        )
        self.group = ensure_exposed_group("Skupina RR2")

    def _create_scoped_measure(
        self,
        *,
        workplace_id: int | None,
        workplace_part_id: int | None,
        item_name: str,
        event_name: str,
        measure_title: str,
        measure_description: str = "",
    ) -> HazardRequiredMeasure:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name=item_name,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=event_name,
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title=measure_title,
            description=measure_description,
        )

    def test_create_follow_up_measure_with_title_and_description(self) -> None:
        measure = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Lis",
            event_name="Přimáčknutí",
            measure_title="Ochranný kryt",
            measure_description="Zajistit funkčnost krytu",
        )
        loaded = hazard_required_measure_service.get_by_id(measure.id)
        assert loaded is not None
        self.assertEqual(loaded.display_title(), "Ochranný kryt")
        self.assertEqual(loaded.display_description(), "Zajistit funkčnost krytu")
        self.assertTrue(loaded.title)

    def test_create_checklist_from_scope(self) -> None:
        measure = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Fréza",
            event_name="Odlet třísek",
            measure_title="Ochranné brýle",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].follow_up_measure_id, measure.id)
        self.assertEqual(rows[0].measure_title, "Ochranné brýle")
        self.assertEqual(rows[0].result, RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED)
        self.assertIn("Fréza", rows[0].risk_label)

    def test_scope_operation_includes_all_workplaces(self) -> None:
        first = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="A",
            event_name="EA",
            measure_title="M1",
        )
        second = self._create_scoped_measure(
            workplace_id=self.other_workplace.id,
            workplace_part_id=None,
            item_name="B",
            event_name="EB",
            measure_title="M2",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
        )
        measure_ids = {
            row.follow_up_measure_id
            for row in risk_measure_review_service.list_checklist_rows(review.id)
        }
        self.assertEqual(measure_ids, {first.id, second.id})

    def test_scope_workplace_filters(self) -> None:
        keep = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Keep",
            event_name="E1",
            measure_title="Keep measure",
        )
        self._create_scoped_measure(
            workplace_id=self.other_workplace.id,
            workplace_part_id=None,
            item_name="Skip",
            event_name="E2",
            measure_title="Skip measure",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual([row.follow_up_measure_id for row in rows], [keep.id])

    def test_scope_workplace_part_filters(self) -> None:
        keep = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=self.workplace_part.id,
            item_name="PartKeep",
            event_name="EP",
            measure_title="Part measure",
        )
        self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="WorkplaceOnly",
            event_name="EW",
            measure_title="Workplace measure",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.workplace_part.id,
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual([row.follow_up_measure_id for row in rows], [keep.id])

    def test_no_duplicate_checklist_items(self) -> None:
        measure = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Dup",
            event_name="DupE",
            measure_title="Jediné opatření",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        # Druhé volání generování nesmí přidat duplicity.
        again = risk_measure_review_service._generate_checklist(review)
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0].follow_up_measure_id, measure.id)

    def test_reopen_does_not_regenerate(self) -> None:
        first = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Orig",
            event_name="OrigE",
            measure_title="Původní",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Later",
            event_name="LaterE",
            measure_title="Nové později",
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].follow_up_measure_id, first.id)

    def test_save_item_results_keeps_follow_up_link(self) -> None:
        measure = self._create_scoped_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            item_name="Result",
            event_name="ResultE",
            measure_title="Kontrola",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        risk_measure_review_service.update_review(
            review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[0].item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                    "note": "OK",
                }
            ],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(reloaded[0].result, RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT)
        self.assertEqual(reloaded[0].note, "OK")
        self.assertEqual(reloaded[0].follow_up_measure_id, measure.id)

        stored = RiskMeasureReviewItemRepository().list_for_review(review.id)
        self.assertEqual(stored[0].follow_up_measure_id, measure.id)

        measure.title = "Přejmenováno"
        from core.database.session import get_session

        with get_session() as session:
            session.merge(measure)
            session.commit()

        renamed_rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(renamed_rows[0].measure_title, "Přejmenováno")
        self.assertEqual(renamed_rows[0].follow_up_measure_id, measure.id)
        self.assertNotEqual(
            renamed_rows[0].result,
            RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        )


if __name__ == "__main__":
    unittest.main()
