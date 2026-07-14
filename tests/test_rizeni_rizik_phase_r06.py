"""Fáze R06 – ohrožené skupiny osob."""

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
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
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
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget


SAMPLE_CONSEQUENCE = "Zranění končetiny"


class HazardRiskAssessmentPhaseR06TestCase(unittest.TestCase):
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
        self.other_identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

        self.item_a = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.item_b = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Vagon",
        )
        self.event_a = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_a.id,
            name="Sražení s osobou",
        )
        self.event_b = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_b.id,
            name="Sražení s osobou",
        )

    def test_hazard_risk_assessments_table_exists(self) -> None:
        columns = _table_columns("hazard_risk_assessments")
        self.assertIn("hazard_event_id", columns)
        self.assertIn("exposed_group", columns)
        self.assertIn("consequence", columns)
        self.assertIn("severity", columns)

    def test_create_assessment(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            note="Poznámka",
        )
        self.assertEqual(assessment.hazard_event_id, self.event_a.id)
        self.assertEqual(assessment.exposed_group, "Posunovač")
        self.assertTrue(assessment.active)

    def test_reject_empty_group(self) -> None:
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event_a.id,
                exposed_group="   ",
                consequence=SAMPLE_CONSEQUENCE,
                severity=RISK_SEVERITY_MODERATE,
            )

    def test_reject_active_duplicate_within_event(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event_a.id,
                exposed_group="  posunovač ",
                consequence=SAMPLE_CONSEQUENCE,
                severity=RISK_SEVERITY_MODERATE,
            )

    def test_allow_same_group_on_different_event(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_b.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assertEqual(assessment.hazard_event_id, self.event_b.id)

    def test_update_assessment(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Strojvedoucí",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            note="Aktualizovaná poznámka",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.exposed_group, "Strojvedoucí")
        self.assertEqual(updated.note, "Aktualizovaná poznámka")

    def test_activate_and_deactivate_assessment(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assertTrue(hazard_risk_assessment_service.deactivate_assessment(assessment.id))
        reloaded = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_risk_assessment_service.activate_assessment(assessment.id))
        reloaded = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_reject_event_from_other_identification(self) -> None:
        other_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.other_identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jiná lokomotiva",
        )
        other_event = hazard_event_service.create_event(
            hazard_identification_id=self.other_identification.id,
            inventory_item_id=other_item.id,
            name="Jiná událost",
        )
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=other_event.id,
                exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
            )

    def test_active_assessment_counts_for_event(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Strojvedoucí",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        inactive = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Údržba",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_risk_assessment_service.deactivate_assessment(inactive.id)

        counts = hazard_risk_assessment_service.count_active_by_events(self.identification.id)
        self.assertEqual(counts[self.event_a.id], 2)
        self.assertEqual(
            hazard_risk_assessment_service.count_active_for_event(self.event_a.id),
            2,
        )

    def test_create_assessment_from_event_context(self) -> None:
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event_a.id,
        )
        self.assertEqual(dialog.event.currentData(), self.event_a.id)
        dialog.exposed_group.setText("Elektrikář")
        dialog.consequence.setPlainText(SAMPLE_CONSEQUENCE)
        dialog.accept()

        rows = hazard_risk_assessment_service.get_for_identification(self.identification.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].assessment.exposed_group, "Elektrikář")
        self.assertEqual(rows[0].event_name, "Sražení s osobou")

    def test_inventory_events_show_assessment_count(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event_a.id,
            exposed_group="Strojvedoucí",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )

        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget._selected_item_id = self.item_a.id
        widget.refresh()
        from moduly.rizeni_rizik.constants import ITEM_EVENT_COL_ID, ITEM_EVENT_COL_NAME

        event_name_by_id = {}
        for row_index in range(widget.events_table.rowCount()):
            id_item = widget.events_table.item(row_index, ITEM_EVENT_COL_ID)
            name_item = widget.events_table.item(row_index, ITEM_EVENT_COL_NAME)
            assert id_item is not None and name_item is not None
            event_name_by_id[int(id_item.text())] = name_item.text()
        self.assertEqual(len(event_name_by_id), 1)
        self.assertIn("2 posouzení", event_name_by_id[self.event_a.id])
        self.assertNotIn(self.event_b.id, event_name_by_id)

    def test_read_only_assessments_for_completed_identification(self) -> None:
        completed = hazard_identification_service.update_identification(
            self.identification.id,
            operation_id=self.identification.operation_id,
            workplace_id=self.identification.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())

        inventory = HazardInventoryWidget()
        inventory.set_identification(completed.id, read_only=True)
        self.assertFalse(inventory.add_event_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
