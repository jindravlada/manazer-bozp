"""HOTFIX R18e.1 – nevolat aktualizaci z Masteru u ručně založených zdrojů."""

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
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
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
    from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
        HazardCatalogInstanceUpdateError,
        hazard_catalog_instance_update_service,
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
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogManualItemUpdateGuardR18e1TestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R18e.1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18e.1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        template_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=template_event.id,
            exposed_group_id=self.group.id,
            severity="moderate",
        )
        self.catalog_item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        ).item
        self.manual_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
        )
        self.widget = HazardInventoryWidget()
        self.widget.set_identification(
            self.identification.id,
            read_only=False,
            identification_status=self.identification.status,
        )

    def test_manual_item_selection_does_not_raise(self) -> None:
        self.widget._maybe_offer_master_update(self.manual_item)

    def test_manual_item_does_not_call_get_update_offer(self) -> None:
        with patch.object(
            hazard_catalog_instance_update_service,
            "get_update_offer",
            side_effect=AssertionError("get_update_offer must not be called"),
        ) as mocked:
            self.widget._maybe_offer_master_update(self.manual_item)
            mocked.assert_not_called()

    def test_manual_item_disables_compare_with_master(self) -> None:
        self.widget._selected_item_id = self.manual_item.id
        self.widget._update_compare_with_master_enabled()
        self.assertFalse(self.widget.compare_with_master_btn.isEnabled())

    def test_catalog_item_still_checks_update_offer(self) -> None:
        bump_template_content_version(self.template.id)
        with patch.object(
            hazard_catalog_instance_update_service,
            "get_update_offer",
            return_value=None,
        ) as mocked:
            self.widget._maybe_offer_master_update(
                hazard_inventory_item_service.get_by_id(self.catalog_item.id),
            )
            mocked.assert_called_once_with(self.catalog_item.id)

    def test_update_error_from_service_is_silently_ignored(self) -> None:
        with patch.object(
            hazard_catalog_instance_update_service,
            "get_update_offer",
            side_effect=HazardCatalogInstanceUpdateError("Test"),
        ):
            self.widget._maybe_offer_master_update(
                hazard_inventory_item_service.get_by_id(self.catalog_item.id),
            )
