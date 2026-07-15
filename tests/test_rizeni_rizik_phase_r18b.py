"""Fáze R18b – evidence původu instance z katalogu."""

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
        format_inventory_item_source_label,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
        bump_template_content_version,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardInventoryItemSourceR18bTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R18b",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18b",
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
            version_number=3,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        reloaded_template = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded_template is not None
        self.template_version_at_apply = reloaded_template.version_number

    def test_apply_from_catalog_stores_source_fields(self) -> None:
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        self.assertEqual(result.item.source_template_id, self.template.id)
        self.assertEqual(result.item.source_template_version, self.template_version_at_apply)

        reloaded = hazard_inventory_item_service.get_by_id(result.item.id)
        assert reloaded is not None
        self.assertEqual(reloaded.source_template_id, self.template.id)
        self.assertEqual(reloaded.source_template_version, self.template_version_at_apply)

    def test_manual_item_has_no_source_fields(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        self.assertIsNone(item.source_template_id)
        self.assertIsNone(item.source_template_version)

    def test_update_item_preserves_source_fields(self) -> None:
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        updated = hazard_inventory_item_service.update_item(
            result.item.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Portálový jeřáb upravený",
            description="Nový popis",
        )
        assert updated is not None
        self.assertEqual(updated.source_template_id, self.template.id)
        self.assertEqual(updated.source_template_version, self.template_version_at_apply)

    def test_source_version_is_snapshot_not_live(self) -> None:
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        snapshot_version = result.item.source_template_version
        bump_template_content_version(self.template.id)
        reloaded_template = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded_template is not None
        self.assertGreater(reloaded_template.version_number, snapshot_version)

        reloaded_item = hazard_inventory_item_service.get_by_id(result.item.id)
        assert reloaded_item is not None
        self.assertEqual(reloaded_item.source_template_version, snapshot_version)

    def test_format_inventory_item_source_label(self) -> None:
        self.assertEqual(
            format_inventory_item_source_label(
                source_template_id=12,
                source_template_version=3,
            ),
            "Katalog zdrojů rizik (ID 12, revize 3)",
        )
        self.assertEqual(
            format_inventory_item_source_label(
                source_template_id=None,
                source_template_version=None,
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
