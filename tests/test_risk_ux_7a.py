"""RISK-UX-7a: základní filtry seznamů řízení rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ux-7a-"))
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
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER,
        RISK_LIST_FILTER_ACTIVE,
        RISK_LIST_FILTER_ALL,
        RISK_LIST_FILTER_INACTIVE,
        RISK_MEASURE_REVIEW_DEFAULT_STATUS_FILTER,
        RISK_MEASURE_REVIEW_FILTER_ALL,
        RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
        RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        RISK_MEASURE_REVIEW_STATUS_DRAFT,
        RISK_MEASURE_REVIEW_STATUS_LABELS,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import HazardIdentificationsTab
    from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab


class RiskUx7aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz UX7a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna UX7a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = person_service.create_person(
            first_name="Filtr",
            last_name="Tester",
        )

    def test_identification_active_filter_defaults_and_filters(self) -> None:
        active = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        inactive = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        hazard_identification_service.deactivate(inactive.id)

        tab = HazardIdentificationsTab()
        self.assertEqual(tab.active_filter.currentData(), RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER)
        self.assertEqual(tab.active_filter.currentText(), RISK_LIST_FILTER_ACTIVE)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(int(tab.table.item(0, 0).text()), active.id)
        self.assertTrue(tab.text_filter.count_label.text().startswith("Zobrazeno:"))

        tab.active_filter.setCurrentIndex(tab.active_filter.findData(RISK_LIST_FILTER_INACTIVE))
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(int(tab.table.item(0, 0).text()), inactive.id)

        tab.active_filter.setCurrentIndex(tab.active_filter.findData(RISK_LIST_FILTER_ALL))
        self.assertEqual(tab.table.rowCount(), 2)

        tab.text_filter.search_edit.setText("neexistujici-retezec-xyz")
        tab.text_filter.apply_filter()
        visible = sum(1 for row in range(tab.table.rowCount()) if not tab.table.isRowHidden(row))
        self.assertEqual(visible, 0)
        self.assertEqual(tab.text_filter.count_label.text(), "Zobrazeno: 0 / 2")

        tab.text_filter.search_edit.setText("dílna ux7a")
        tab.text_filter.apply_filter()
        visible = sum(1 for row in range(tab.table.rowCount()) if not tab.table.isRowHidden(row))
        self.assertEqual(visible, 2)
        self.assertEqual(tab.text_filter.count_label.text(), "Zobrazeno: 2 / 2")

    def test_review_status_filter_defaults_and_filters(self) -> None:
        draft = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        completed = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        risk_measure_review_service.update_review(
            completed.id,
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            status=RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        )
        archived = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        risk_measure_review_service.archive(archived.id)

        tab = RiskMeasureReviewsTab()
        self.assertEqual(
            tab.status_filter.currentData(),
            RISK_MEASURE_REVIEW_DEFAULT_STATUS_FILTER,
        )
        self.assertEqual(
            tab.status_filter.currentText(),
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_DRAFT],
        )
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(int(tab.table.item(0, 0).text()), draft.id)

        tab.status_filter.setCurrentIndex(
            tab.status_filter.findData(RISK_MEASURE_REVIEW_STATUS_COMPLETED)
        )
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(int(tab.table.item(0, 0).text()), completed.id)

        tab.status_filter.setCurrentIndex(
            tab.status_filter.findData(RISK_MEASURE_REVIEW_STATUS_ARCHIVED)
        )
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(int(tab.table.item(0, 0).text()), archived.id)

        tab.status_filter.setCurrentIndex(
            tab.status_filter.findData(RISK_MEASURE_REVIEW_FILTER_ALL)
        )
        self.assertEqual(tab.table.rowCount(), 3)
        self.assertTrue(tab.text_filter.count_label.text().startswith("Zobrazeno:"))


if __name__ == "__main__":
    unittest.main()
