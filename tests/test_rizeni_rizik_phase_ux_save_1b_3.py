"""UX-SAVE-1b.3 – aktuální a filtrovaná nabídka zdrojů z katalogu."""

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
        HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_MANUAL
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
        HazardLibraryTemplateApplyError,
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
    from moduly.rizeni_rizik.ui.hazard_library_apply_to_inventory_dialog import (
        HazardLibraryApplyToInventoryDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryApplyCatalogOfferUxSave1b3TestCase(unittest.TestCase):
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
            name="Provoz UX1b3",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna UX1b3",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")

    def _create_template(
        self,
        *,
        name: str,
        category: str = HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        active: bool = True,
    ):
        template = hazard_library_template_service.create_template(
            name=name,
            category=category,
            description="Popis",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            operation_ids=[],
        )
        if not active:
            hazard_library_template_service.deactivate(template.id)
            template = hazard_library_template_service.get_by_id(template.id)
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name=f"Událost {name}",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Závěr",
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
            hazard_library_template_existing_measure_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
            hazard_library_template_required_measure_service,
        )

        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Existující",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Potřebné",
        )
        return hazard_library_template_service.get_by_id(template.id)

    def _offer_names(
        self,
        *,
        category: str | None = HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        include_inactive: bool = False,
        inventory_items=None,
    ) -> set[str]:
        groups = hazard_library_template_apply_service.get_template_groups(
            operation_id=None,
            category=category,
            hazard_identification_id=self.identification.id,
            include_inactive=include_inactive,
            inventory_items=inventory_items,
        )
        return {template.name for template in list(groups.recommended) + list(groups.other)}

    def test_new_saved_catalog_source_appears_without_restart(self) -> None:
        existing = self._create_template(name="Vrtačka")
        before = self._offer_names()
        self.assertIn(existing.name, before)

        created = self._create_template(name="Montážní jáma")
        after = self._offer_names()
        self.assertIn("Montážní jáma", after)
        self.assertIn(existing.name, after)
        self.assertEqual(created.name, "Montážní jáma")

    def test_dialog_reload_shows_new_source(self) -> None:
        self._create_template(name="Původní zdroj")
        dialog = HazardLibraryApplyToInventoryDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        names_before = {
            dialog.sources_list.item(i).text().split(" (", 1)[0]
            for i in range(dialog.sources_list.count())
        }
        self.assertIn("Původní zdroj", names_before)
        dialog.close()

        self._create_template(name="Montážní jáma")
        dialog2 = HazardLibraryApplyToInventoryDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        names_after = {
            dialog2.sources_list.item(i).text().split(" (", 1)[0]
            for i in range(dialog2.sources_list.count())
        }
        self.assertIn("Montážní jáma", names_after)
        self.assertIn("Původní zdroj", names_after)
        dialog2.close()

    def test_applied_source_hidden_other_remains(self) -> None:
        first = self._create_template(name="Montážní jáma")
        second = self._create_template(name="Vrtačka")

        self.assertEqual(
            self._offer_names(),
            {"Montážní jáma", "Vrtačka"},
        )

        hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=first.id,
        )

        after = self._offer_names()
        self.assertNotIn("Montážní jáma", after)
        self.assertIn("Vrtačka", after)
        self.assertEqual(after, {second.name})

    def test_category_filter_still_works(self) -> None:
        self._create_template(
            name="Montážní jáma",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        self._create_template(
            name="Hluk",
            category=HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        )

        equipment = self._offer_names(category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        environment = self._offer_names(category=HAZARD_INVENTORY_CATEGORY_ENVIRONMENT)

        self.assertEqual(equipment, {"Montážní jáma"})
        self.assertEqual(environment, {"Hluk"})

    def test_inactive_catalog_source_only_with_checkbox(self) -> None:
        active = self._create_template(name="Aktivní zdroj", active=True)
        inactive = self._create_template(name="Neaktivní zdroj", active=False)

        without = self._offer_names(include_inactive=False)
        self.assertIn(active.name, without)
        self.assertNotIn(inactive.name, without)

        with_inactive = self._offer_names(include_inactive=True)
        self.assertIn(active.name, with_inactive)
        self.assertIn(inactive.name, with_inactive)

    def test_inactive_still_hidden_when_already_applied_active(self) -> None:
        template = self._create_template(name="Montážní jáma")
        hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        hazard_library_template_service.deactivate(template.id)

        self.assertNotIn(
            "Montážní jáma",
            self._offer_names(include_inactive=True),
        )

    def test_no_duplicate_active_instance_same_catalog_source(self) -> None:
        template = self._create_template(name="Montážní jáma")
        hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        with self.assertRaises(HazardLibraryTemplateApplyError):
            hazard_library_template_apply_service.apply_template(
                hazard_identification_id=self.identification.id,
                template_id=template.id,
            )
        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        matching = [
            item for item in items if item.source_template_id == template.id
        ]
        self.assertEqual(len(matching), 1)

    def test_working_copy_inventory_items_filter(self) -> None:
        """Příprava na deferred-save: filtr umí použít pracovní kopii."""
        template = self._create_template(name="Montážní jáma")
        other = self._create_template(name="Vrtačka")

        # V DB ještě není převzato.
        self.assertIn("Montážní jáma", self._offer_names())

        fake_wc_item = type(
            "WcItem",
            (),
            {
                "active": True,
                "source_template_id": template.id,
            },
        )()
        names = self._offer_names(inventory_items=[fake_wc_item])
        self.assertNotIn("Montážní jáma", names)
        self.assertIn(other.name, names)

    def test_inactive_instance_allows_offer_again(self) -> None:
        template = self._create_template(name="Montážní jáma")
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        hazard_inventory_item_service.deactivate_item(result.item.id)

        # Pouze neaktivní instance → zdroj lze nabídnout znovu.
        self.assertIn("Montážní jáma", self._offer_names())


if __name__ == "__main__":
    unittest.main()
