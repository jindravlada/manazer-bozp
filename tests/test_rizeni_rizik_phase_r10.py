"""Fáze R10 – dokončení posouzení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        DEFAULT_RISK_ASSESSMENT_STATUS,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_COL_COMPLETED_AT,
        RISK_ASSESSMENT_COL_EXPOSED_GROUP,
        RISK_ASSESSMENT_COL_STATUS,
        RISK_ASSESSMENT_STATUS_COMPLETED,
        RISK_ASSESSMENT_STATUS_DRAFT,
        RISK_ASSESSMENT_STATUS_LABELS,
        RISK_ASSESSMENT_TABLE_HEADERS,
        RISK_SEVERITY_MODERATE,
        format_risk_assessment_display_name,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        HazardRiskAssessmentError,
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
        identified_hazard_service,
    )
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget


SAMPLE_CONSEQUENCE = "Zranění končetiny"


class HazardRiskAssessmentPhaseR10TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(IdentifiedHazard))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

        lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=lokomotiva.id,
            name="Pohyb kolejového vozidla",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=hazard.id,
            name="Sražení s osobou",
        )

    def _create_assessment(self, *, exposed_group: str = "Posunovač"):
        return hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group=exposed_group,
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )

    def test_hazard_risk_assessments_table_has_status_columns(self) -> None:
        columns = _table_columns("hazard_risk_assessments")
        self.assertIn("assessment_status", columns)
        self.assertIn("conclusion", columns)
        self.assertIn("completed_at", columns)

    def test_default_status_is_draft(self) -> None:
        assessment = self._create_assessment()
        self.assertEqual(assessment.assessment_status, DEFAULT_RISK_ASSESSMENT_STATUS)
        self.assertEqual(assessment.assessment_status, RISK_ASSESSMENT_STATUS_DRAFT)
        self.assertIsNone(assessment.completed_at)

    def test_complete_assessment(self) -> None:
        assessment = self._create_assessment()
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        assert updated is not None
        self.assertEqual(updated.assessment_status, RISK_ASSESSMENT_STATUS_COMPLETED)

    def test_completed_at_set_on_completion(self) -> None:
        assessment = self._create_assessment()
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        assert updated is not None
        self.assertIsNotNone(updated.completed_at)

    def test_revert_to_draft(self) -> None:
        assessment = self._create_assessment()
        completed = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        assert completed is not None
        reverted = hazard_risk_assessment_service.update_assessment(
            completed.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_DRAFT,
        )
        assert reverted is not None
        self.assertEqual(reverted.assessment_status, RISK_ASSESSMENT_STATUS_DRAFT)

    def test_completed_at_cleared_on_revert(self) -> None:
        assessment = self._create_assessment()
        completed = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        assert completed is not None
        reverted = hazard_risk_assessment_service.update_assessment(
            completed.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_DRAFT,
        )
        assert reverted is not None
        self.assertIsNone(reverted.completed_at)

    def test_save_conclusion(self) -> None:
        assessment = self._create_assessment()
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Riziko je přijatelné po zavedení opatření.",
        )
        assert updated is not None
        self.assertEqual(updated.conclusion, "Riziko je přijatelné po zavedení opatření.")

    def test_reject_incomplete_completion(self) -> None:
        assessment = self._create_assessment()
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.update_assessment(
                assessment.id,
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group="Posunovač",
                consequence="",
                severity=RISK_SEVERITY_MODERATE,
                assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
            )

    def test_active_status_summary_counts_only_active(self) -> None:
        first = self._create_assessment(exposed_group="Posunovač A")
        second = self._create_assessment(exposed_group="Posunovač B")
        hazard_risk_assessment_service.update_assessment(
            second.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač B",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        third = self._create_assessment(exposed_group="Posunovač C")
        hazard_risk_assessment_service.deactivate_assessment(third.id)

        summary = hazard_risk_assessment_service.get_active_status_summary(
            self.identification.id
        )
        self.assertEqual(summary, {"total": 2, "draft": 1, "completed": 1})

    def test_widget_shows_status_and_completed_at(self) -> None:
        assessment = self._create_assessment()
        hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        self.assertEqual(
            [
                widget.table.horizontalHeaderItem(column).text()
                for column in range(widget.table.columnCount())
            ],
            RISK_ASSESSMENT_TABLE_HEADERS,
        )
        self.assertEqual(
            widget.table.item(0, RISK_ASSESSMENT_COL_STATUS).text(),
            RISK_ASSESSMENT_STATUS_LABELS[RISK_ASSESSMENT_STATUS_COMPLETED],
        )
        self.assertNotEqual(widget.table.item(0, RISK_ASSESSMENT_COL_COMPLETED_AT).text(), "")
        self.assertIn("Posouzení celkem: 1", widget.summary_label.text())
        self.assertIn("Dokončená: 1", widget.summary_label.text())

    def test_display_name_includes_status(self) -> None:
        display_name = format_risk_assessment_display_name(
            "Posunovač",
            assessment_status_label="Dokončeno",
            existing_measure_count=5,
            required_measure_count=2,
        )
        self.assertEqual(
            display_name,
            "Posunovač — Dokončeno — 5 existujících opatření — 2 potřebná opatření",
        )

    def test_widget_display_name_includes_status(self) -> None:
        self._create_assessment()
        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        display_name = widget.table.item(0, RISK_ASSESSMENT_COL_EXPOSED_GROUP).text()
        self.assertIn("Rozpracováno", display_name)

    def test_read_only_dialog_disables_status_and_conclusion(self) -> None:
        assessment = self._create_assessment()
        completed = hazard_identification_service.update_identification(
            self.identification.id,
            operation_id=self.identification.operation_id,
            workplace_id=self.identification.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=completed.id,
            assessment=assessment,
            read_only=True,
        )
        self.assertFalse(dialog.assessment_status.isEnabled())
        self.assertTrue(dialog.conclusion.isReadOnly())

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
