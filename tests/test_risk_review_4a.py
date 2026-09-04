"""RISK-REVIEW-4a: dotažení UX checklistu přezkoumání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-4a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLineEdit, QRadioButton

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
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
    from moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service import (
        risk_measure_review_checklist_export_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_checklist_widget import (
        RiskMeasureReviewChecklistWidget,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview4aTestCase(unittest.TestCase):
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
            name="Provoz RR4a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR4a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Eva",
            last_name="Terén",
        )
        self.group = ensure_exposed_group("Skupina RR4a")
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Frézka",
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
        hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title="Ochranný kryt frézky s dlouhým názvem pro zalomení textu",
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_no_table_header_and_point_layout(self) -> None:
        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(risk_measure_review_service.list_checklist_rows(self.review.id))
        self.assertFalse(hasattr(widget, "table"))
        self.assertEqual(widget.point_count(), 1)
        point = widget.points[0]
        self.assertTrue(point.measure_label.wordWrap())
        self.assertTrue(point.measure_label.font().bold())
        self.assertTrue(point.measure_label.toolTip())
        self.assertIsInstance(point.compliant_radio, QRadioButton)
        self.assertIsInstance(point.non_compliant_radio, QRadioButton)
        self.assertIsInstance(point.note_edit, QLineEdit)
        self.assertEqual(point.note_edit.placeholderText(), "")
        self.assertFalse(point.compliant_radio.isChecked())
        self.assertFalse(point.non_compliant_radio.isChecked())

    def test_radios_mutual_exclusive_default_unchecked(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(rows[0].result, RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED)

        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(rows)
        point = widget.points[0]
        self.assertFalse(point.compliant_radio.isChecked())
        self.assertFalse(point.non_compliant_radio.isChecked())

        point.compliant_radio.setChecked(True)
        self.assertTrue(point.compliant_radio.isChecked())
        self.assertFalse(point.non_compliant_radio.isChecked())

        point.non_compliant_radio.setChecked(True)
        self.assertFalse(point.compliant_radio.isChecked())
        self.assertTrue(point.non_compliant_radio.isChecked())
        self.assertEqual(
            point.get_update()["result"],
            RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        )

    def test_print_layout_paper_only_note_number(self) -> None:
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
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                    "note": "Bez závad",
                }
            ],
        )
        review = risk_measure_review_service.get_by_id(self.review.id)
        text = str(
            risk_measure_review_checklist_export_service.build_context(review)[
                "checklist_text"
            ]
        )
        self.assertNotIn(
            "Kontrolní otázky | Vyhovuje | Nevyhovuje | Foto | Poznámka",
            text,
        )
        self.assertIn("Ochranný kryt frézky", text)
        self.assertIn(
            "Vyhovuje ☐\tNevyhovuje ☐\tFoto ☐\tPoznámka č.:",
            text,
        )
        self.assertNotIn("Bez závad", text)
        self.assertNotIn("Poznámka: Bez závad", text)

        # V ODT musí být tabulátory jako <text:tab/>, jinak se řádek „slepí“.
        with patch(
            "moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service.open_export_file"
        ):
            path = risk_measure_review_checklist_export_service.generate_for_review(review)
        import zipfile

        with zipfile.ZipFile(path) as archive:
            xml = archive.read("content.xml").decode("utf-8")
        self.assertIn("Vyhovuje ☐", xml)
        self.assertIn("<text:tab/>", xml)
        self.assertIn("Poznámka č.:", xml)
        # Nesmí zůstat naplácané bez oddělovačů.
        self.assertNotIn("Vyhovuje ☐ Nevyhovuje ☐ Foto ☐", xml)

    def test_execution_dialog_opens_maximized(self) -> None:
        dialog = RiskMeasureReviewExecutionDialog(
            review=risk_measure_review_service.get_by_id(self.review.id),
        )
        self.assertTrue(bool(dialog.windowState() & Qt.WindowState.WindowMaximized))
        dialog._editor.mark_clean()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
