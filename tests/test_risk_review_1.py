"""RISK-REVIEW-1: založení přezkoumání opatření rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QGroupBox

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        EXISTING_MEASURES_TITLE,
        REQUIRED_MEASURES_TITLE,
    RISK_MEASURE_REVIEW_CHECKLIST_EMPTY,
    RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
        RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        RISK_MEASURE_REVIEW_STATUS_DRAFT,
        RISK_MEASURE_REVIEW_TAB_TITLE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE,
        HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        RiskMeasureReviewError,
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
    from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage


class RiskReview1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RR1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna RR1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.workplace_part = settings_service.save_workplace(
            name="Úsek RR1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.other_operation = settings_service.save_workplace(
            name="Jiný provoz RR1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.other_workplace = settings_service.save_workplace(
            name="Jiná dílna RR1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.other_operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Karel",
            last_name="Kontrolní",
        )

    def test_migration_creates_review_tables(self) -> None:
        review_columns = _table_columns("risk_measure_reviews")
        item_columns = _table_columns("risk_measure_review_items")
        for column in (
            "id",
            "review_number",
            "review_date",
            "reviewer_person_id",
            "operation_id",
            "workplace_id",
            "workplace_part_id",
            "status",
            "note",
            "created_at",
            "updated_at",
            "archived_at",
        ):
            self.assertIn(column, review_columns)
        for column in (
            "id",
            "review_id",
            "follow_up_measure_id",
            "result",
            "note",
            "sort_order",
            "created_at",
            "updated_at",
        ):
            self.assertIn(column, item_columns)
        self.assertTrue(hasattr(RiskMeasureReviewItem, "follow_up_measure_id"))
        self.assertTrue(hasattr(HazardRequiredMeasure, "id"))

    def test_measure_terminology_renamed(self) -> None:
        self.assertEqual(EXISTING_MEASURES_TITLE, "Zásady bezpečné práce")
        self.assertEqual(REQUIRED_MEASURES_TITLE, "Navazující opatření")
        self.assertEqual(
            HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE,
            "Zásady bezpečné práce",
        )
        self.assertEqual(
            HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
            "Navazující opatření",
        )

    def test_module_has_review_tab(self) -> None:
        page = RizeniRizikPage()
        titles = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        self.assertEqual(titles[0], "Identifikace")
        self.assertEqual(titles[2], RISK_MEASURE_REVIEW_TAB_TITLE)
        self.assertIsInstance(page.reviews_tab, RiskMeasureReviewsTab)

    def test_create_review_requires_operation(self) -> None:
        with self.assertRaises(RiskMeasureReviewError):
            risk_measure_review_service.create_review(
                review_date=date.today(),
                reviewer_person_id=self.reviewer.id,
                operation_id=0,
            )

    def test_create_and_reload_review(self) -> None:
        created = risk_measure_review_service.create_review(
            review_date=date(2026, 7, 20),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.workplace_part.id,
            status=RISK_MEASURE_REVIEW_STATUS_DRAFT,
            note="Poznámka RR1",
        )
        self.assertTrue(created.review_number)
        self.assertRegex(created.review_number, r"^\d{4}-\d{4}$")
        loaded = risk_measure_review_service.get_by_id(created.id)
        assert loaded is not None
        self.assertEqual(loaded.operation_id, self.operation.id)
        self.assertEqual(loaded.workplace_id, self.workplace.id)
        self.assertEqual(loaded.workplace_part_id, self.workplace_part.id)
        self.assertEqual(loaded.reviewer_person_id, self.reviewer.id)
        self.assertEqual(loaded.note, "Poznámka RR1")
        self.assertEqual(loaded.status, RISK_MEASURE_REVIEW_STATUS_DRAFT)

    def test_dependent_workplace_and_part_selection(self) -> None:
        workplaces = risk_measure_review_service.get_workplaces_for_operation(
            self.operation.id,
            include_inactive=True,
        )
        workplace_ids = {item.id for item in workplaces}
        self.assertIn(self.workplace.id, workplace_ids)
        self.assertNotIn(self.other_workplace.id, workplace_ids)

        parts = risk_measure_review_service.get_workplace_parts_for_workplace(
            self.workplace.id,
            include_inactive=True,
        )
        self.assertEqual([item.id for item in parts], [self.workplace_part.id])
        self.assertEqual(
            risk_measure_review_service.get_workplace_parts_for_workplace(None),
            [],
        )

        with self.assertRaises(RiskMeasureReviewError):
            risk_measure_review_service.create_review(
                review_date=date.today(),
                reviewer_person_id=self.reviewer.id,
                operation_id=self.operation.id,
                workplace_id=self.other_workplace.id,
            )
        with self.assertRaises(RiskMeasureReviewError):
            risk_measure_review_service.create_review(
                review_date=date.today(),
                reviewer_person_id=self.reviewer.id,
                operation_id=self.operation.id,
                workplace_part_id=self.workplace_part.id,
            )

    def test_status_change_and_archive_restore(self) -> None:
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
        )
        updated = risk_measure_review_service.update_review(
            review.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            status=RISK_MEASURE_REVIEW_STATUS_COMPLETED,
            note="",
        )
        assert updated is not None
        self.assertEqual(updated.status, RISK_MEASURE_REVIEW_STATUS_COMPLETED)

        self.assertTrue(risk_measure_review_service.archive(review.id))
        archived = risk_measure_review_service.get_by_id(review.id)
        assert archived is not None
        self.assertEqual(archived.status, RISK_MEASURE_REVIEW_STATUS_ARCHIVED)
        self.assertIsNotNone(archived.archived_at)

        self.assertTrue(risk_measure_review_service.restore(review.id))
        restored = risk_measure_review_service.get_by_id(review.id)
        assert restored is not None
        self.assertIsNone(restored.archived_at)
        self.assertEqual(restored.status, RISK_MEASURE_REVIEW_STATUS_DRAFT)

    def test_editor_defaults_and_checklist_placeholder(self) -> None:
        from PySide6.QtWidgets import QLabel

        dialog = RiskMeasureReviewDialog()
        self.assertEqual(
            date(
                dialog.review_date.date().year(),
                dialog.review_date.date().month(),
                dialog.review_date.date().day(),
            ),
            date.today(),
        )
        self.assertEqual(dialog.status.currentData(), RISK_MEASURE_REVIEW_STATUS_DRAFT)
        groups = dialog.findChildren(QGroupBox)
        titles = [group.title() for group in groups]
        self.assertIn(RISK_MEASURE_REVIEW_CHECKLIST_TITLE, titles)
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        self.assertIn(RISK_MEASURE_REVIEW_CHECKLIST_EMPTY, labels)
        dialog.close()

    def test_editor_dirty_tracking(self) -> None:
        dialog = RiskMeasureReviewDialog()
        self.assertFalse(dialog._editor.is_dirty())
        dialog.note.setPlainText("změna")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog._editor.mark_clean()
        dialog.close()

    def test_editor_save_and_reload_via_dialog(self) -> None:
        dialog = RiskMeasureReviewDialog()
        dialog.reviewer.set_person_id(self.reviewer.id)
        index = dialog.operation.findData(self.operation.id)
        self.assertGreaterEqual(index, 0)
        dialog.operation.setCurrentIndex(index)
        dialog.note.setPlainText("Uloženo z editoru")
        self.assertTrue(dialog._save())
        assert dialog.review is not None
        review_id = dialog.review.id
        dialog._editor.mark_clean()
        dialog.close()

        reopened = RiskMeasureReviewDialog(
            review=risk_measure_review_service.get_by_id(review_id),
        )
        self.assertEqual(reopened.note.toPlainText(), "Uloženo z editoru")
        self.assertEqual(reopened.operation.currentData(), self.operation.id)
        reopened._editor.mark_clean()
        reopened.close()

    def test_double_click_opens_existing_review(self) -> None:
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            note="Dvojklik",
        )
        tab = RiskMeasureReviewsTab()
        tab.refresh()
        self.assertGreaterEqual(tab.table.rowCount(), 1)
        tab.table.selectRow(0)

        opened: list[int] = []

        class _CaptureDialog(RiskMeasureReviewDialog):
            def __init__(self, parent=None, review=None):
                opened.append(int(review.id) if review is not None else 0)
                super().__init__(parent, review=review)

            def exec(self):
                return 0

        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_reviews_tab.RiskMeasureReviewDialog",
            _CaptureDialog,
        ):
            tab.edit_selected_review()
        self.assertEqual(opened, [review.id])

    def test_existing_risk_register_data_preserved(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import select
        from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
            hazard_identification_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
            hazard_inventory_item_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
        from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
            hazard_risk_assessment_service,
        )
        from moduly.rizeni_rizik.constants import (
            HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            RISK_SEVERITY_MODERATE,
        )
        from tests.rizeni_rizik_test_helpers import ensure_exposed_group

        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Stroj RR1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Úraz RR1",
        )
        group = ensure_exposed_group("Skupina RR1")
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        with get_session() as session:
            session.add(
                HazardExistingMeasure(
                    hazard_risk_assessment_id=assessment.id,
                    description="Zásada RR1",
                    sort_order=0,
                )
            )
            session.add(
                HazardRequiredMeasure(
                    hazard_risk_assessment_id=assessment.id,
                    description="Navazující RR1",
                    sort_order=0,
                )
            )
            session.commit()

        initialize_database()

        with get_session() as session:
            preserved_id = session.get(HazardIdentification, identification.id)
            preserved_assessment = session.get(HazardRiskAssessment, assessment.id)
            existing = list(
                session.scalars(
                    select(HazardExistingMeasure).where(
                        HazardExistingMeasure.hazard_risk_assessment_id == assessment.id,
                    )
                )
            )
            required = list(
                session.scalars(
                    select(HazardRequiredMeasure).where(
                        HazardRequiredMeasure.hazard_risk_assessment_id == assessment.id,
                    )
                )
            )
        self.assertIsNotNone(preserved_id)
        self.assertIsNotNone(preserved_assessment)
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0].description, "Zásada RR1")
        self.assertEqual(len(required), 1)
        self.assertEqual(required[0].description, "Navazující RR1")


if __name__ == "__main__":
    unittest.main()
