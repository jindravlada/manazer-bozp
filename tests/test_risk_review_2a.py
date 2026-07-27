"""RISK-REVIEW-2a: zjednodušení checklistu přezkoumání opatření."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-2a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QCheckBox, QGroupBox, QLineEdit

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
        RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER,
        RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
        RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
        RISK_MEASURE_REVIEW_NOTES_TITLE,
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
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_checklist_widget import (
        RiskMeasureReviewChecklistWidget,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview2aTestCase(unittest.TestCase):
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
            name="Provoz RR2a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR2a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Eva",
            last_name="Terén",
        )
        self.group = ensure_exposed_group("Skupina RR2a")

        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Soustruh",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Zachycení",
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
            title="Ochranný kryt",
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_item_table_has_simplified_columns(self) -> None:
        columns = _table_columns("risk_measure_review_items")
        self.assertIn("compliant", columns)
        self.assertIn("note_number", columns)
        self.assertIn("has_photo", columns)
        self.assertIn("follow_up_measure_id", columns)

        self.assertEqual(
            RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
            ["ID", "Navazující opatření", "Vyhovuje", "Poznámka č.", "Foto"],
        )
        self.assertNotIn("Riziko", RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.assertNotIn("Výsledek", RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.assertNotIn("Poznámka", RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)

    def test_checklist_widget_layout(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(rows)

        headers = [
            widget.table.horizontalHeaderItem(column).text()
            for column in range(widget.table.columnCount())
        ]
        self.assertEqual(headers, RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.assertEqual(widget.table.rowCount(), 1)

        compliant_host = widget.table.cellWidget(0, RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT)
        note_number = widget.table.cellWidget(0, RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER)
        photo_host = widget.table.cellWidget(0, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO)
        measure_item = widget.table.item(0, RISK_MEASURE_REVIEW_ITEM_COL_MEASURE)

        self.assertIsNotNone(measure_item)
        self.assertEqual(measure_item.text(), "Ochranný kryt")
        self.assertIsInstance(getattr(compliant_host, "_checkbox", None), QCheckBox)
        self.assertIsInstance(note_number, QLineEdit)
        self.assertEqual(note_number.placeholderText(), "____")
        self.assertIsInstance(getattr(photo_host, "_checkbox", None), QCheckBox)

        notes = [
            group
            for group in widget.findChildren(QGroupBox)
            if group.title() == RISK_MEASURE_REVIEW_NOTES_TITLE
        ]
        self.assertEqual(len(notes), 1)
        self.assertGreaterEqual(len(widget.note_lines), 3)

    def test_database_links_preserved_after_checkbox_save(self) -> None:
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
                    "compliant": True,
                    "note_number": "2",
                    "has_photo": True,
                }
            ],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(reloaded[0].follow_up_measure_id, self.measure.id)
        self.assertTrue(reloaded[0].compliant)
        self.assertEqual(reloaded[0].note_number, "2")
        self.assertTrue(reloaded[0].has_photo)

    def test_dialog_uses_simplified_checklist(self) -> None:
        dialog = RiskMeasureReviewDialog(
            review=risk_measure_review_service.get_by_id(self.review.id),
        )
        headers = [
            dialog.checklist.table.horizontalHeaderItem(column).text()
            for column in range(dialog.checklist.table.columnCount())
        ]
        self.assertEqual(headers, RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.assertTrue(
            any(
                group.title() == RISK_MEASURE_REVIEW_NOTES_TITLE
                for group in dialog.checklist.findChildren(QGroupBox)
            )
        )
        dialog._editor.mark_clean()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
