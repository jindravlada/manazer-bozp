"""RISK-CHECKLIST-2: víceřádková opatření jako samostatné body elektronického checklistu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-checklist-2-"))
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

    from core.database.session import get_session
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
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
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_checklist_widget import (
        RiskMeasureReviewChecklistWidget,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


MULTILINE_MEASURE = (
    "Kontrola řádného upnutí pracovního oděvu.\n"
    "Kontrola viditelnosti pracovního oděvu (čistota, stav reflexních prvků).\n"
    "Kontrola zajištění drážních vozidel proti ujetí."
)


class RiskChecklist2ElectronicItemsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz CHECKLIST-2",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Pracoviště CHECKLIST-2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.group = ensure_exposed_group("Skupina CHECKLIST-2")
        self.reviewer = settings_service.save_worker(
            first_name="Eva",
            last_name="Kontrolorka",
            active=True,
        )
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zařízení CHECKLIST-2",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Událost CHECKLIST-2",
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
            title=MULTILINE_MEASURE,
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_three_independent_electronic_checklist_points(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row.item_id for row in rows}), 3)
        self.assertEqual(
            [row.measure_title for row in rows],
            [
                "Kontrola řádného upnutí pracovního oděvu.",
                "Kontrola viditelnosti pracovního oděvu (čistota, stav reflexních prvků).",
                "Kontrola zajištění drážních vozidel proti ujetí.",
            ],
        )
        self.assertTrue(all(row.follow_up_measure_id == self.measure.id for row in rows))
        self.assertTrue(all("\n" not in row.measure_title for row in rows))

        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(rows)
        self.assertEqual(widget.point_count(), 3)
        self.assertEqual(
            [point.measure_label.text() for point in widget.points],
            [row.measure_title for row in rows],
        )

        # Stav jednoho bodu neovlivní ostatní.
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[1].item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                    "note": "Reflexní prvky poškozené",
                },
                {
                    "item_id": rows[0].item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                    "note": "",
                },
            ],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(self.review.id)
        by_id = {row.item_id: row for row in reloaded}
        self.assertEqual(
            by_id[rows[0].item_id].result,
            RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        )
        self.assertEqual(
            by_id[rows[1].item_id].result,
            RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        )
        self.assertEqual(by_id[rows[1].item_id].note, "Reflexní prvky poškozené")
        self.assertEqual(by_id[rows[2].item_id].note, "")
        self.assertFalse(by_id[rows[2].item_id].compliant)


if __name__ == "__main__":
    unittest.main()
