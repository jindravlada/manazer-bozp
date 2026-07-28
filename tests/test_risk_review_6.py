"""RISK-REVIEW-6: kontrolující z číselníku THP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-6-"))
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

    from core.widgets.person_selector import PersonSelector
    from core.widgets.thp_worker_selector import ThpWorkerSelector
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        RiskMeasureReviewError,
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog


class RiskReview6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.nastaveni.modely.person import Person
        from moduly.nastaveni.modely.thp_worker import ThpWorker

        with get_session() as session:
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(ThpWorker))
            session.execute(delete(Person))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RR6",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.active_thp = settings_service.save_worker(
            first_name="Anna",
            last_name="Aktivní",
            active=True,
        )
        self.other_thp = settings_service.save_worker(
            first_name="Boris",
            last_name="Delegát",
            active=True,
        )
        self.inactive_thp = settings_service.save_worker(
            first_name="Cyril",
            last_name="Neaktivní",
            active=False,
        )
        self.plain_person = person_service.create_person(
            first_name="Dana",
            last_name="Osoba",
        )

    def _selector_worker_ids(self, dialog: RiskMeasureReviewDialog) -> set[int]:
        selector = dialog.reviewer
        return {
            selector.itemData(index)
            for index in range(selector.count())
            if isinstance(selector.itemData(index), int)
        }

    def _selector_labels(self, dialog: RiskMeasureReviewDialog) -> set[str]:
        selector = dialog.reviewer
        return {
            selector.itemText(index).strip()
            for index in range(selector.count())
            if selector.itemText(index).strip()
        }

    def test_dialog_offers_only_active_thp_workers(self) -> None:
        dialog = RiskMeasureReviewDialog()
        self.assertIsInstance(dialog.reviewer, ThpWorkerSelector)
        self.assertNotIsInstance(dialog.reviewer, PersonSelector)
        worker_ids = self._selector_worker_ids(dialog)
        labels = self._selector_labels(dialog)
        self.assertIn(self.active_thp.id, worker_ids)
        self.assertIn(self.other_thp.id, worker_ids)
        self.assertNotIn(self.inactive_thp.id, worker_ids)
        self.assertNotIn(self.plain_person.display_name, labels)
        self.assertNotIn("Dana Osoba", labels)
        dialog._editor.mark_clean()
        dialog.close()

    def test_new_review_prefills_logged_in_thp(self) -> None:
        dialog = RiskMeasureReviewDialog(current_thp_worker_id=self.active_thp.id)
        self.assertEqual(dialog.reviewer.current_person_id(), self.active_thp.id)
        self.assertEqual(
            dialog.get_data()["reviewer_person_id"],
            self.active_thp.id,
        )
        dialog._editor.mark_clean()
        dialog.close()

    def test_new_review_prefills_via_resolver(self) -> None:
        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_review_dialog.resolve_current_thp_worker_id",
            return_value=self.active_thp.id,
        ):
            dialog = RiskMeasureReviewDialog()
        self.assertEqual(dialog.reviewer.current_person_id(), self.active_thp.id)
        dialog._editor.mark_clean()
        dialog.close()

    def test_can_delegate_to_another_thp_worker(self) -> None:
        dialog = RiskMeasureReviewDialog(current_thp_worker_id=self.active_thp.id)
        self.assertEqual(dialog.reviewer.current_person_id(), self.active_thp.id)
        dialog.reviewer.set_person_id(self.other_thp.id)
        self.assertEqual(dialog.reviewer.current_person_id(), self.other_thp.id)
        dialog._editor.mark_clean()
        dialog.close()

    def test_save_stores_thp_worker_id_unchanged(self) -> None:
        dialog = RiskMeasureReviewDialog(current_thp_worker_id=self.active_thp.id)
        dialog.reviewer.set_person_id(self.other_thp.id)
        index = dialog.operation.findData(self.operation.id)
        self.assertGreaterEqual(index, 0)
        dialog.operation.setCurrentIndex(index)
        dialog.note.setPlainText("Delegace THP")
        self.assertTrue(dialog._save())
        assert dialog.review is not None
        review_id = dialog.review.id
        dialog._editor.mark_clean()
        dialog.close()

        loaded = risk_measure_review_service.get_by_id(review_id)
        assert loaded is not None
        self.assertEqual(loaded.reviewer_person_id, self.other_thp.id)
        self.assertEqual(loaded.reviewer_person_name, self.other_thp.display_name)
        self.assertEqual(loaded.note, "Delegace THP")

        reopened = RiskMeasureReviewDialog(review=loaded)
        self.assertEqual(reopened.reviewer.current_person_id(), self.other_thp.id)
        reopened._editor.mark_clean()
        reopened.close()

    def test_unknown_reviewer_id_is_rejected(self) -> None:
        with self.assertRaises(RiskMeasureReviewError):
            risk_measure_review_service.create_review(
                review_date=date.today(),
                reviewer_person_id=9_999_999,
                operation_id=self.operation.id,
                note="Neexistující kontrolující",
            )


if __name__ == "__main__":
    unittest.main()
