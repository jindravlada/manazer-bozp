"""RISK-REVIEW-3: evidence zjištění z přezkoumání opatření."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-3-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_FINDINGS_TITLE,
        RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
        RISK_SEVERITY_SERIOUS,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.risk_measure_finding import RiskMeasureFinding
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
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview3TestCase(unittest.TestCase):
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
            session.execute(delete(RiskMeasureFinding))
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
            name="Provoz RR3",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR3",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Petr",
            last_name="Zjišťovatel",
        )
        self.group = ensure_exposed_group("Skupina RR3")

        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Pád břemene",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        self.measure_a = hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title="Kontrola lan",
        )
        self.measure_b = hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title="Kontrola brzd",
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_findings_table_migration(self) -> None:
        columns = _table_columns("risk_measure_findings")
        for column in (
            "id",
            "review_id",
            "note_number",
            "title",
            "description",
            "recommendation",
            "severity",
            "created_at",
            "updated_at",
        ):
            self.assertIn(column, columns)

    def test_create_finding_and_edit(self) -> None:
        finding = risk_measure_review_service.ensure_finding_for_note_number(
            self.review.id,
            "1",
        )
        assert finding is not None
        updated = risk_measure_review_service.update_finding(
            finding.id,
            title="Poškozené lano",
            description="Viditelné roztřepení",
            recommendation="Vyměnit lano",
            severity=RISK_SEVERITY_SERIOUS,
        )
        assert updated is not None
        self.assertEqual(updated.title, "Poškozené lano")
        self.assertEqual(updated.recommendation, "Vyměnit lano")
        self.assertEqual(updated.severity, RISK_SEVERITY_SERIOUS)

    def test_auto_create_finding_from_note_number(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertGreaterEqual(len(rows), 2)
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            checklist_updates=[
                {
                    "item_id": rows[0].item_id,
                    "compliant": False,
                    "note_number": "5",
                    "has_photo": False,
                }
            ],
        )
        findings = risk_measure_review_service.list_findings(self.review.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].note_number, "5")
        self.assertEqual(findings[0].title, "")

    def test_multiple_items_share_same_finding(self) -> None:
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
                    "compliant": False,
                    "note_number": "2",
                    "has_photo": True,
                },
                {
                    "item_id": rows[1].item_id,
                    "compliant": False,
                    "note_number": "2",
                    "has_photo": False,
                },
            ],
        )
        findings = risk_measure_review_service.list_findings(self.review.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].note_number, "2")
        reloaded = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(reloaded[0].note_number, "2")
        self.assertEqual(reloaded[1].note_number, "2")
        self.assertEqual(reloaded[0].follow_up_measure_id, self.measure_a.id)
        self.assertEqual(reloaded[1].follow_up_measure_id, self.measure_b.id)

    def test_incomplete_finding_warning_list(self) -> None:
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
                    "compliant": False,
                    "note_number": "3",
                    "has_photo": False,
                }
            ],
        )
        incomplete = risk_measure_review_service.list_incomplete_findings(self.review.id)
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].note_number, "3")

        risk_measure_review_service.update_finding(
            incomplete[0].id,
            title="Doplněno",
        )
        self.assertEqual(
            risk_measure_review_service.list_incomplete_findings(self.review.id),
            [],
        )

    def test_dialog_has_findings_tab_and_warns(self) -> None:
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
                    "compliant": False,
                    "note_number": "7",
                    "has_photo": False,
                }
            ],
        )
        dialog = RiskMeasureReviewDialog(
            review=risk_measure_review_service.get_by_id(self.review.id),
        )
        titles = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(titles[0], RISK_MEASURE_REVIEW_CHECKLIST_TITLE)
        self.assertEqual(titles[1], RISK_MEASURE_FINDINGS_TITLE)
        self.assertGreaterEqual(dialog.findings.table.rowCount(), 1)

        with patch.object(QMessageBox, "information") as info:
            dialog._warn_incomplete_findings()
            info.assert_called_once()
            dialog._editor.mark_clean()
            dialog.close()
            self.assertGreaterEqual(info.call_count, 1)


if __name__ == "__main__":
    unittest.main()
