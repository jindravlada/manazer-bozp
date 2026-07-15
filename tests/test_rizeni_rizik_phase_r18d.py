"""Fáze R18d – porovnání lokální instance s Master katalogem."""

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

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_COMPARE_KIND_ADDED,
        CATALOG_COMPARE_KIND_CHANGED,
        CATALOG_COMPARE_KIND_REMOVED,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_compare_service import (
        HazardCatalogInstanceCompareError,
        hazard_catalog_instance_compare_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
        hazard_library_template_apply_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogInstanceCompareR18dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R18d",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18d",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
            hazard_library_template_existing_measure_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
            hazard_library_template_required_measure_service,
        )

        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Ochranné zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Doplnit zábradlí",
        )

        apply_result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        self.catalog_item = apply_result.item
        self.event = hazard_event_service.get_for_inventory_item(self.catalog_item.id)[0]
        self.assessment = hazard_risk_assessment_service.get_for_identification(
            self.identification.id,
        )[0].assessment
        self.existing_measure = hazard_existing_measure_service.get_for_assessment(
            self.assessment.id,
        )[0]
        self.required_measure = hazard_required_measure_service.get_for_assessment(
            self.assessment.id,
        )[0]

    def test_no_differences_after_apply(self) -> None:
        result = hazard_catalog_instance_compare_service.compare(self.catalog_item.id)
        self.assertFalse(result.has_differences)

    def test_added_event_is_reported(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Nová událost",
        )
        result = hazard_catalog_instance_compare_service.compare(self.catalog_item.id)
        kinds = {line.kind for line in result.lines}
        labels = " ".join(line.label for line in result.lines)
        self.assertIn(CATALOG_COMPARE_KIND_ADDED, kinds)
        self.assertIn("Nová událost", labels)

    def test_changed_event_text_is_reported(self) -> None:
        hazard_event_service.update_event(
            self.event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Pád břemene",
            description="Lokální popis",
        )
        result = hazard_catalog_instance_compare_service.compare(self.catalog_item.id)
        changed = [line for line in result.lines if line.kind == CATALOG_COMPARE_KIND_CHANGED]
        self.assertTrue(any("Událost: Pád břemene" in line.label for line in changed))
        self.assertTrue(any("popis" in line.detail for line in changed))

    def test_removed_measure_is_reported(self) -> None:
        hazard_existing_measure_service.deactivate_measure(self.existing_measure.id)
        result = hazard_catalog_instance_compare_service.compare(self.catalog_item.id)
        removed = [line for line in result.lines if line.kind == CATALOG_COMPARE_KIND_REMOVED]
        self.assertTrue(
            any("Ochranné zábradlí" in line.label for line in removed),
            msg=str(result.lines),
        )

    def test_manual_item_cannot_be_compared(self) -> None:
        manual_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        with self.assertRaises(HazardCatalogInstanceCompareError):
            hazard_catalog_instance_compare_service.compare(manual_item.id)

    def test_local_changes_do_not_modify_master(self) -> None:
        hazard_event_service.update_event(
            self.event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Lokální název",
        )
        template_event = hazard_library_template_event_service.get_for_template(self.template.id)[0]
        self.assertEqual(template_event.name, "Pád břemene")

    def test_inventory_widget_compare_button_enabled_for_catalog_item(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=False,
            identification_status=self.identification.status,
        )
        widget._selected_item_id = self.catalog_item.id
        widget._load_table()
        widget._update_compare_with_master_enabled()
        self.assertTrue(widget.compare_with_master_btn.isEnabled())

    def test_inventory_widget_compare_button_disabled_for_manual_item(self) -> None:
        manual_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=False,
            identification_status=self.identification.status,
        )
        widget._selected_item_id = manual_item.id
        widget._load_table()
        widget._update_compare_with_master_enabled()
        self.assertFalse(widget.compare_with_master_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
