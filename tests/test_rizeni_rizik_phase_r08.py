"""Fáze R08 – existující opatření."""

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
        EXISTING_MEASURE_COL_DESCRIPTION,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_COL_EXPOSED_GROUP,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        HazardExistingMeasureError,
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_existing_measures_widget import HazardExistingMeasuresWidget
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import HazardRiskAssessmentsWidget


SAMPLE_CONSEQUENCE = "Zranění končetiny"


class HazardExistingMeasurePhaseR08TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardExistingMeasure))
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

        lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        other_lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.other_identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jiná lokomotiva",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=lokomotiva.id,
            name="Sražení s osobou",
        )
        other_event = hazard_event_service.create_event(
            hazard_identification_id=self.other_identification.id,
            inventory_item_id=other_lokomotiva.id,
            name="Jiná událost",
        )
        self.assessment_a = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assessment_b = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.other_identification.id,
            hazard_event_id=other_event.id,
            exposed_group="Posunovač",
            consequence=SAMPLE_CONSEQUENCE,
            severity=RISK_SEVERITY_MODERATE,
        )

    def test_hazard_existing_measures_table_exists(self) -> None:
        columns = _table_columns("hazard_existing_measures")
        self.assertIn("hazard_risk_assessment_id", columns)
        self.assertIn("description", columns)
        self.assertIn("sort_order", columns)

    def test_create_measure(self) -> None:
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
            note="Umístěna u vjezdu",
        )
        self.assertEqual(measure.description, "Výstražná tabule")
        self.assertTrue(measure.active)

    def test_reject_empty_description(self) -> None:
        with self.assertRaises(HazardExistingMeasureError):
            hazard_existing_measure_service.create_measure(
                hazard_identification_id=self.identification.id,
                hazard_risk_assessment_id=self.assessment_a.id,
                description="   ",
            )

    def test_reject_active_duplicate_within_assessment(self) -> None:
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )
        with self.assertRaises(HazardExistingMeasureError):
            hazard_existing_measure_service.create_measure(
                hazard_identification_id=self.identification.id,
                hazard_risk_assessment_id=self.assessment_a.id,
                description="  výstražná tabule ",
            )

    def test_allow_same_description_on_different_assessment(self) -> None:
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.other_identification.id,
            hazard_risk_assessment_id=self.assessment_b.id,
            description="Výstražná tabule",
        )
        self.assertEqual(measure.hazard_risk_assessment_id, self.assessment_b.id)

    def test_update_measure(self) -> None:
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )
        updated = hazard_existing_measure_service.update_measure(
            measure.id,
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Ochranné zábradlí",
            note="Po obnově",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.description, "Ochranné zábradlí")
        self.assertEqual(updated.note, "Po obnově")

    def test_activate_and_deactivate_measure(self) -> None:
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )
        self.assertTrue(hazard_existing_measure_service.deactivate_measure(measure.id))
        reloaded = hazard_existing_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_existing_measure_service.activate_measure(measure.id))
        reloaded = hazard_existing_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_active_measure_counts_for_assessment(self) -> None:
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Ochranné zábradlí",
        )
        inactive = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Reflexní vesta",
        )
        hazard_existing_measure_service.deactivate_measure(inactive.id)

        counts = hazard_existing_measure_service.count_active_by_assessments(
            self.identification.id
        )
        self.assertEqual(counts[self.assessment_a.id], 2)
        self.assertEqual(
            hazard_existing_measure_service.count_active_for_assessment(self.assessment_a.id),
            2,
        )

    def test_assessments_widget_shows_measure_count(self) -> None:
        for index in range(5):
            hazard_existing_measure_service.create_measure(
                hazard_identification_id=self.identification.id,
                hazard_risk_assessment_id=self.assessment_a.id,
                description=f"Opatření {index + 1}",
            )

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.table.selectRow(0)
        name_item = widget.table.item(0, RISK_ASSESSMENT_COL_EXPOSED_GROUP)
        assert name_item is not None
        self.assertIn("5 existujících opatření", name_item.text())

    def test_existing_measures_widget_loads_for_selected_assessment(self) -> None:
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment_a.id,
            description="Výstražná tabule",
        )

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.table.selectRow(0)
        self.assertEqual(widget.existing_measures_widget.table.rowCount(), 1)
        description_item = widget.existing_measures_widget.table.item(
            0,
            EXISTING_MEASURE_COL_DESCRIPTION,
        )
        assert description_item is not None
        self.assertEqual(description_item.text(), "Výstražná tabule")

    def test_read_only_existing_measures_for_completed_identification(self) -> None:
        completed = hazard_identification_service.update_identification(
            self.identification.id,
            operation_id=self.identification.operation_id,
            workplace_id=self.identification.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        widget = HazardExistingMeasuresWidget()
        widget.set_assessment(
            self.assessment_a,
            identification_id=completed.id,
            read_only=True,
        )
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
