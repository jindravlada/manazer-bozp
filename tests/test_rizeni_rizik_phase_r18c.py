"""Fáze R18c – lokální úpravy instancí převzatých z katalogu."""

from __future__ import annotations

import importlib
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
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
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
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogInstanceModificationR18cTestCase(unittest.TestCase):
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
            name="Provoz R18c",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18c",
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
        self.template_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        self.template_assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.template_event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
            hazard_library_template_existing_measure_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
            hazard_library_template_required_measure_service,
        )

        self.template_existing = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.template_assessment.id,
            description="Ochranné zábradlí",
        )
        self.template_required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.template_assessment.id,
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

    def test_apply_from_catalog_has_modified_false(self) -> None:
        self.assertFalse(self.event.modified)
        self.assertFalse(self.assessment.modified)
        self.assertFalse(self.existing_measure.modified)
        self.assertFalse(self.required_measure.modified)

    def test_update_event_on_catalog_instance_sets_modified(self) -> None:
        updated = hazard_event_service.update_event(
            self.event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Pád břemene – lokálně",
        )
        assert updated is not None
        self.assertTrue(updated.modified)

    def test_update_assessment_on_catalog_instance_sets_modified(self) -> None:
        updated = hazard_risk_assessment_service.update_assessment(
            self.assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        assert updated is not None
        self.assertTrue(updated.modified)

    def test_update_measures_on_catalog_instance_sets_modified(self) -> None:
        existing = hazard_existing_measure_service.update_measure(
            self.existing_measure.id,
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Zábradlí upravené",
        )
        required = hazard_required_measure_service.update_measure(
            self.required_measure.id,
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Nové opatření",
        )
        assert existing is not None
        assert required is not None
        self.assertTrue(existing.modified)
        self.assertTrue(required.modified)

    def test_create_on_catalog_instance_sets_modified(self) -> None:
        new_event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Nová událost",
        )
        self.assertTrue(new_event.modified)

        other_group = ensure_exposed_group("Návštěvníci")
        new_assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=new_event.id,
            exposed_group_id=other_group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assertTrue(new_assessment.modified)

        new_existing = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Nové stávající opatření",
        )
        new_required = hazard_required_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Nové potřebné opatření",
        )
        self.assertTrue(new_existing.modified)
        self.assertTrue(new_required.modified)

    def test_manual_item_changes_do_not_set_modified(self) -> None:
        manual_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=manual_item.id,
            name="Ruční událost",
        )
        self.assertFalse(event.modified)

        updated = hazard_event_service.update_event(
            event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=manual_item.id,
            name="Ruční událost upravená",
        )
        assert updated is not None
        self.assertFalse(updated.modified)

    def test_local_changes_do_not_modify_master_template(self) -> None:
        hazard_event_service.update_event(
            self.event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Lokální název události",
        )
        hazard_risk_assessment_service.update_assessment(
            self.assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )

        template_event = hazard_library_template_event_service.get_by_id(self.template_event.id)
        template_assessment = hazard_library_template_assessment_service.get_by_id(
            self.template_assessment.id,
        )
        assert template_event is not None
        assert template_assessment is not None
        self.assertEqual(template_event.name, "Pád břemene")
        self.assertEqual(template_assessment.severity, RISK_SEVERITY_MODERATE)


if __name__ == "__main__":
    unittest.main()
