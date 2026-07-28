"""RISK-CHECKLIST-1: víceřádková navazující opatření jako samostatné položky tisku."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-checklist-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.export import OdtParagraph
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
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
    from moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service import (
        risk_measure_review_checklist_export_service,
        split_checklist_measure_lines,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


MULTILINE_MEASURE = (
    "Kontrola řádného upnutí pracovního oděvu.\n"
    "Kontrola viditelnosti pracovního oděvu (čistota, stav reflexních prvků).\n"
    "Kontrola zajištění drážních vozidel proti ujetí."
)


class RiskChecklist1MultilineItemsTestCase(unittest.TestCase):
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
            name="Provoz CHECKLIST-1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Pracoviště CHECKLIST-1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.group = ensure_exposed_group("Skupina CHECKLIST-1")
        self.reviewer = settings_service.save_worker(
            first_name="Jan",
            last_name="Kontrolor",
            active=True,
        )
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zařízení CHECKLIST-1",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Událost CHECKLIST-1",
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

    def test_split_helper_handles_newlines_and_blanks(self) -> None:
        self.assertEqual(
            split_checklist_measure_lines(MULTILINE_MEASURE),
            [
                "Kontrola řádného upnutí pracovního oděvu.",
                "Kontrola viditelnosti pracovního oděvu (čistota, stav reflexních prvků).",
                "Kontrola zajištění drážních vozidel proti ujetí.",
            ],
        )
        self.assertEqual(
            split_checklist_measure_lines(
                "  První.  \r\n\r\n\tDruhé.\rTřetí.  "
            ),
            ["První.", "Druhé.", "Třetí."],
        )
        self.assertEqual(split_checklist_measure_lines(""), [])

    def test_db_keeps_newlines_and_print_creates_three_items(self) -> None:
        loaded = hazard_required_measure_service.get_by_id(self.measure.id)
        assert loaded is not None
        self.assertIn("\n", loaded.display_title())
        self.assertEqual(loaded.display_title().count("\n"), 2)

        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].follow_up_measure_id, self.measure.id)

        content = risk_measure_review_checklist_export_service.build_context(
            self.review,
        )["checklist_text"]

        def _paragraph_text(paragraph: OdtParagraph) -> str:
            return "".join(run.text for run in paragraph.runs)

        criterion_texts = [
            _paragraph_text(paragraph)
            for paragraph in content.paragraphs
            if isinstance(paragraph, OdtParagraph)
            and paragraph.style == "AuditCriterion"
            and not paragraph.blank
        ]
        control_lines = [
            _paragraph_text(paragraph)
            for paragraph in content.paragraphs
            if isinstance(paragraph, OdtParagraph)
            and "Vyhovuje" in _paragraph_text(paragraph)
        ]
        self.assertEqual(
            criterion_texts,
            [
                "Kontrola řádného upnutí pracovního oděvu.",
                "Kontrola viditelnosti pracovního oděvu (čistota, stav reflexních prvků).",
                "Kontrola zajištění drážních vozidel proti ujetí.",
            ],
        )
        self.assertEqual(len(control_lines), 3)
        # Nesmí zůstat jeden sloučený odstavec s celým textem.
        self.assertFalse(
            any("\n" in (text or "") for text in criterion_texts),
        )


if __name__ == "__main__":
    unittest.main()
