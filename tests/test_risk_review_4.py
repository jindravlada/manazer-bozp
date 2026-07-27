"""RISK-REVIEW-4: dokončení editoru checklistu přezkoumání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-4-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QLineEdit, QRadioButton

    from core.services.attachment_service import attachment_service
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        ENTITY_RISK_MEASURE_REVIEW_ITEM,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
        RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
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
    from moduly.rizeni_rizik.ui.risk_measure_review_item_photos_dialog import (
        RiskMeasureReviewItemPhotosDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskReview4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.models.attachment import Attachment
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
            session.execute(delete(Attachment))
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
            name="Provoz RR4",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR4",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Jan",
            last_name="Kontrolor",
        )
        self.group = ensure_exposed_group("Skupina RR4")

        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Lis",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Přivření",
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
            title="Dvouruční ovládání",
        )
        self.review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def test_column_order(self) -> None:
        self.assertEqual(
            RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
            ["ID", "Navazující opatření", "Vyhovuje", "Nevyhovuje", "Foto", "Poznámka"],
        )
        widget = RiskMeasureReviewChecklistWidget()
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        widget.load_rows(rows)
        self.assertFalse(hasattr(widget, "table"))
        self.assertEqual(widget.point_count(), 1)
        point = widget.points[0]
        self.assertEqual(point.measure_label.text(), "Dvouruční ovládání")
        self.assertTrue(point.measure_label.wordWrap())
        self.assertIsInstance(point.compliant_radio, QRadioButton)
        self.assertIsInstance(point.non_compliant_radio, QRadioButton)
        self.assertIsInstance(point.note_edit, QLineEdit)

    def test_compliant_non_compliant_mutual_exclusivity(self) -> None:
        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(risk_measure_review_service.list_checklist_rows(self.review.id))
        point = widget.points[0]
        compliant = point.compliant_radio
        non_compliant = point.non_compliant_radio

        self.assertFalse(compliant.isChecked())
        self.assertFalse(non_compliant.isChecked())

        compliant.setChecked(True)
        self.assertTrue(compliant.isChecked())
        self.assertFalse(non_compliant.isChecked())

        non_compliant.setChecked(True)
        self.assertFalse(compliant.isChecked())
        self.assertTrue(non_compliant.isChecked())

        # Exclusive QRadioButton: clear selection via temporary non-exclusive mode.
        point._result_group.setExclusive(False)
        non_compliant.setChecked(False)
        point._result_group.setExclusive(True)
        self.assertFalse(compliant.isChecked())
        self.assertFalse(non_compliant.isChecked())

        updates = widget.get_updates()
        self.assertEqual(updates[0]["result"], RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED)

    def test_save_note(self) -> None:
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
                    "note": "Chybí kryt",
                }
            ],
        )
        reloaded = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(reloaded[0].note, "Chybí kryt")
        self.assertEqual(reloaded[0].result, RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT)

        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(reloaded)
        note_edit = widget.points[0].note_edit
        self.assertIsInstance(note_edit, QLineEdit)
        self.assertEqual(note_edit.text(), "Chybí kryt")
        self.assertTrue(widget.points[0].non_compliant_radio.isChecked())
        self.assertFalse(widget.points[0].compliant_radio.isChecked())

    def test_open_photo_manager_and_save_photo(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        photo = _TMP / "kontrola.jpg"
        photo.write_bytes(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xd9"
        )

        dialog = RiskMeasureReviewItemPhotosDialog(item_id=item_id)
        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_review_item_photos_dialog.PhotoPickerDialog.get_photo",
            return_value=str(photo),
        ):
            dialog._add_photo()
        self.assertEqual(dialog.photo_count(), 1)
        attachments = attachment_service.get_for_entity(
            ENTITY_RISK_MEASURE_REVIEW_ITEM,
            item_id,
        )
        self.assertEqual(len(attachments), 1)
        dialog.close()

        widget = RiskMeasureReviewChecklistWidget()
        widget.load_rows(risk_measure_review_service.list_checklist_rows(self.review.id))
        photo_btn = widget.points[0].photo_btn
        self.assertIn("(1)", photo_btn.text())

        with patch.object(RiskMeasureReviewItemPhotosDialog, "exec", return_value=0):
            with patch.object(RiskMeasureReviewItemPhotosDialog, "photo_count", return_value=1):
                widget.points[0]._open_photos()
        self.assertIn("(1)", photo_btn.text())

    def test_print_checklist_odt(self) -> None:
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
                    "note": "OK",
                }
            ],
        )
        review = risk_measure_review_service.get_by_id(self.review.id)
        context = risk_measure_review_checklist_export_service.build_context(review)
        self.assertEqual(context["provoz"], "Provoz RR4")
        self.assertEqual(context["pracoviste"], "Dílna RR4")
        self.assertIn("Dvouruční ovládání", str(context["checklist_text"]))
        self.assertIn("Vyhovuje", str(context["checklist_text"]))

        with patch(
            "moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service.open_export_file"
        ) as open_export:
            path = risk_measure_review_checklist_export_service.open_for_review(review)
            open_export.assert_called_once()
        self.assertTrue(path.exists())
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("content.xml").decode("utf-8")
        self.assertIn("Checklist přezkoumání opatření", xml)
        self.assertIn("Provoz RR4", xml)
        self.assertIn("Dvouruční ovládání", xml)


if __name__ == "__main__":
    unittest.main()
