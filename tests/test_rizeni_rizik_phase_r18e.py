"""Fáze R18e – aktualizace lokální instance z novější verze Master."""

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
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
        HazardCatalogInstanceUpdateError,
        hazard_catalog_instance_update_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
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
    from moduly.rizeni_rizik.ui.hazard_catalog_instance_update_offer_dialog import (
        CATALOG_UPDATE_CHOICE_KEEP,
        HazardCatalogInstanceUpdateOfferDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogInstanceUpdateR18eTestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R18e",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18e",
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
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.template_event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        reloaded_template = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded_template is not None
        self.template_version_at_apply = reloaded_template.version_number

        apply_result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        self.catalog_item = apply_result.item
        self.event = hazard_event_service.get_for_inventory_item(self.catalog_item.id)[0]

    def test_no_offer_when_versions_match(self) -> None:
        offer = hazard_catalog_instance_update_service.get_update_offer(self.catalog_item.id)
        self.assertIsNone(offer)

    def test_offer_when_master_is_newer(self) -> None:
        bump_template_content_version(self.template.id)
        offer = hazard_catalog_instance_update_service.get_update_offer(self.catalog_item.id)
        assert offer is not None
        self.assertEqual(offer.source_template_version, self.template_version_at_apply)
        self.assertGreater(offer.master_version, offer.source_template_version)
        self.assertEqual(offer.template_name, "Portálový jeřáb")

    def test_update_from_master_requires_explicit_call(self) -> None:
        bump_template_content_version(self.template.id)
        reloaded = hazard_inventory_item_service.get_by_id(self.catalog_item.id)
        assert reloaded is not None
        self.assertEqual(reloaded.source_template_version, self.template_version_at_apply)

    def test_update_from_master_syncs_content_and_version(self) -> None:
        hazard_event_service.update_event(
            self.event.id,
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.catalog_item.id,
            name="Lokální událost",
        )
        bump_template_content_version(self.template.id)
        hazard_library_template_event_service.update_event(
            self.template_event.id,
            template_id=self.template.id,
            name="Pád břemene aktualizovaný",
        )
        bump_template_content_version(self.template.id)

        result = hazard_catalog_instance_update_service.update_from_master(self.catalog_item.id)
        self.assertGreater(result.new_version, result.previous_version)

        reloaded_item = hazard_inventory_item_service.get_by_id(self.catalog_item.id)
        assert reloaded_item is not None
        self.assertEqual(reloaded_item.source_template_version, result.new_version)

        events = hazard_event_service.get_for_inventory_item(self.catalog_item.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Pád břemene aktualizovaný")
        self.assertFalse(events[0].modified)

    def test_manual_item_cannot_be_updated(self) -> None:
        manual_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        with self.assertRaises(HazardCatalogInstanceUpdateError):
            hazard_catalog_instance_update_service.update_from_master(manual_item.id)

    def test_update_offer_dialog_defaults_to_keep(self) -> None:
        bump_template_content_version(self.template.id)
        offer = hazard_catalog_instance_update_service.get_update_offer(self.catalog_item.id)
        assert offer is not None
        dialog = HazardCatalogInstanceUpdateOfferDialog(offer=offer)
        dialog.accept()
        self.assertEqual(dialog.selected_choice, CATALOG_UPDATE_CHOICE_KEEP)

    def test_widget_dismisses_offer_after_keep(self) -> None:
        bump_template_content_version(self.template.id)
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=False,
            identification_status=self.identification.status,
        )
        widget._selected_item_id = self.catalog_item.id

        class _FakeOfferDialog:
            def __init__(self, parent=None, *, offer):
                self.selected_choice = CATALOG_UPDATE_CHOICE_KEEP

            def exec(self):
                return 1

        with patch(
            "moduly.rizeni_rizik.ui.hazard_inventory_widget.HazardCatalogInstanceUpdateOfferDialog",
            _FakeOfferDialog,
        ):
            widget._maybe_offer_master_update(
                hazard_inventory_item_service.get_by_id(self.catalog_item.id)
            )

        self.assertIn(self.catalog_item.id, widget._dismissed_master_update_offers)

        reloaded = hazard_inventory_item_service.get_by_id(self.catalog_item.id)
        assert reloaded is not None
        self.assertEqual(reloaded.source_template_version, self.template_version_at_apply)


if __name__ == "__main__":
    unittest.main()
