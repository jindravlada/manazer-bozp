"""RISK-REVIEW-3: oddělení evidence přezkoumání od provedení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-3-split-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QTabWidget

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
        RISK_MEASURE_REVIEW_PRINT_BUTTON,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
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
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview3SplitTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
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
            name="Provoz Split",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna Split",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.workplace_part = settings_service.save_workplace(
            name="Úsek Split",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.other_workplace = settings_service.save_workplace(
            name="Jiná dílna Split",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Anna",
            last_name="Provedení",
        )
        self.group = ensure_exposed_group("Skupina Split")

    def _create_measure(
        self,
        *,
        workplace_id: int | None,
        workplace_part_id: int | None,
        title: str,
    ) -> HazardRequiredMeasure:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name=f"Zdroj {title}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=f"Událost {title}",
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
            title=title,
        )

    def test_evidence_dialog_has_no_checklist(self) -> None:
        dialog = RiskMeasureReviewDialog()
        self.assertFalse(hasattr(dialog, "checklist"))
        self.assertEqual(len(dialog.findChildren(QTabWidget)), 0)
        dialog.close()

    def test_tab_has_execute_button(self) -> None:
        tab = RiskMeasureReviewsTab()
        self.assertEqual(tab.execute_btn.text(), "Provést přezkoumání")
        self.assertFalse(tab.execute_btn.isEnabled())

    def test_open_execution_loads_follow_up_measures(self) -> None:
        measure = self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            title="Kontrola krytu",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        dialog = RiskMeasureReviewExecutionDialog(review=review)
        self.assertEqual(dialog.checklist.point_count(), 1)
        point = dialog.checklist.points[0]
        self.assertEqual(point.measure_label.text(), "Kontrola krytu")
        self.assertEqual(point.compliant_radio.text(), "Vyhovuje")
        self.assertEqual(point.non_compliant_radio.text(), "Nevyhovuje")
        self.assertFalse(hasattr(dialog.checklist, "table"))
        self.assertEqual(dialog.print_btn.text(), RISK_MEASURE_REVIEW_PRINT_BUTTON)
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(rows[0].follow_up_measure_id, measure.id)
        dialog._editor.mark_clean()
        dialog.close()

    def test_scope_filtering_workplace_and_part(self) -> None:
        keep = self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=self.workplace_part.id,
            title="Keep",
        )
        self._create_measure(
            workplace_id=self.other_workplace.id,
            workplace_part_id=None,
            title="Skip",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.workplace_part.id,
        )
        rows = risk_measure_review_service.ensure_checklist(review.id)
        self.assertEqual([row.follow_up_measure_id for row in rows], [keep.id])

    def test_save_execution_results_keeps_assessment_link(self) -> None:
        measure = self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            title="Brzdy",
        )
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rows = risk_measure_review_service.ensure_checklist(review.id)
        risk_measure_review_service.update_review(
            review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[0].item_id,
                    "compliant": True,
                    "note": "Bez závad",
                }
            ],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertTrue(reloaded[0].compliant)
        self.assertEqual(reloaded[0].note, "Bez závad")
        self.assertEqual(reloaded[0].follow_up_measure_id, measure.id)
        linked = hazard_required_measure_service.get_by_id(measure.id)
        assert linked is not None
        self.assertIsNotNone(linked.hazard_risk_assessment_id)

    def test_print_stub(self) -> None:
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
        )
        dialog = RiskMeasureReviewExecutionDialog(review=review)
        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog."
            "risk_measure_review_checklist_export_service.open_for_review"
        ) as open_print:
            dialog._print_checklist()
            open_print.assert_called_once()
        dialog._editor.mark_clean()
        dialog.close()

    def test_checklist_headers_without_paper_columns(self) -> None:
        self.assertEqual(
            RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
            ["ID", "Kontrolní otázky", "Vyhovuje", "Nevyhovuje", "Foto", "Poznámka"],
        )
        self.assertNotIn("Poznámka č.", RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.assertNotIn("Výsledek přezkoumání", RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)


if __name__ == "__main__":
    unittest.main()
