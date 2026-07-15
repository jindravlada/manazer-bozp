"""Fáze R07 – následek a závažnost."""

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

    from tests.rizeni_rizik_test_helpers import ensure_exposed_group
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_COL_CONSEQUENCE,
        RISK_ASSESSMENT_COL_SEVERITY,
        RISK_ASSESSMENT_TABLE_HEADERS,
        RISK_SEVERITIES,
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_LABELS,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
        RISK_SEVERITY_NEGLIGIBLE,
        RISK_SEVERITY_SERIOUS,
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
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget


SAMPLE_CONSEQUENCE = "Zranění končetiny"


class HazardRiskAssessmentPhaseR07TestCase(unittest.TestCase):
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

        lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=lokomotiva.id,
            name="Sražení s osobou",
        )

    def test_table_has_consequence_and_severity_columns(self) -> None:
        columns = _table_columns("hazard_risk_assessments")
        self.assertIn("consequence", columns)
        self.assertIn("severity", columns)

    def test_create_assessment_with_consequence(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence="Zlomenina nohy",
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assertEqual(assessment.consequence, "Zlomenina nohy")

    def test_create_assessment_for_each_severity(self) -> None:
        groups = ["Posunovač", "Strojvedoucí", "Údržba", "Elektrikář", "Dodavatel"]
        for severity, group in zip(RISK_SEVERITIES, groups):
            assessment = hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_id=ensure_exposed_group(group).id,
                consequence=f"Následek pro {group}",
                severity=severity,
            )
            self.assertEqual(assessment.severity, severity)
            rows = hazard_risk_assessment_service.get_for_identification(self.identification.id)
            row = next(item for item in rows if item.exposed_group_name == group)
            self.assertEqual(row.severity_label, RISK_SEVERITY_LABELS[severity])

    def test_reject_empty_consequence(self) -> None:
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_id=ensure_exposed_group("Posunovač").id,
                consequence="   ",
                severity=RISK_SEVERITY_MODERATE,
            )

    def test_reject_invalid_severity(self) -> None:
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_id=ensure_exposed_group("Posunovač").id,
                consequence=SAMPLE_CONSEQUENCE,
                severity="unknown",
            )

    def test_update_consequence(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence="Původní následek",
            severity=RISK_SEVERITY_MINOR,
        )
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence="Aktualizovaný následek",
            severity=RISK_SEVERITY_MINOR,
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.consequence, "Aktualizovaný následek")

    def test_update_severity(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MINOR,
        )
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_CRITICAL,
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.severity, RISK_SEVERITY_CRITICAL)

    def test_widget_shows_consequence_and_severity(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence="Hospitalizace",
            severity=RISK_SEVERITY_SERIOUS,
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
        self.assertEqual(widget.table.item(0, RISK_ASSESSMENT_COL_CONSEQUENCE).text(), "Hospitalizace")
        self.assertEqual(
            widget.table.item(0, RISK_ASSESSMENT_COL_SEVERITY).text(),
            RISK_SEVERITY_LABELS[RISK_SEVERITY_SERIOUS],
        )

    def test_reject_active_duplicate_still_applies(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence="První následek",
            severity=RISK_SEVERITY_NEGLIGIBLE,
        )
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_id=ensure_exposed_group("  posunovač ").id,
                consequence="Druhý následek",
                severity=RISK_SEVERITY_CRITICAL,
            )

    def test_dialog_shows_severity_description(self) -> None:
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event.id,
        )
        index = dialog.severity.findData(RISK_SEVERITY_CRITICAL)
        assert index >= 0
        dialog.severity.setCurrentIndex(index)
        self.assertIn("Smrtelné zranění", dialog.severity_description.text())

    def test_read_only_dialog_disables_consequence_and_severity(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=ensure_exposed_group("Posunovač").id,
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
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
        self.assertTrue(dialog.consequence.isReadOnly())
        self.assertFalse(dialog.severity.isEnabled())

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
