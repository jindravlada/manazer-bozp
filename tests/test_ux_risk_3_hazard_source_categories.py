"""UX-RISK-3 – editovatelný číselník kategorií zdrojů rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _seed_and_migrate_hazard_source_categories,
        initialize_database,
    )
    from core.database.session import get_session

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        DEFAULT_HAZARD_SOURCE_CATEGORIES,
        HAZARD_INVENTORY_CATEGORIES,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        HAZARD_INVENTORY_CATEGORY_OTHER,
        LEGACY_HAZARD_SOURCE_CATEGORY_NAMES,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
        HazardSourceCategoryError,
        hazard_source_category_service,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_item_dialog import (
        HazardInventoryItemDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_source_category_combo import (
        populate_hazard_source_category_combo,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class UxRisk3HazardSourceCategoriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        operation = settings_service.save_workplace(
            name="Provoz UX-RISK-3",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště UX-RISK-3",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        cls.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        cls.exposed_group = ensure_exposed_group("Zaměstnanci UX-RISK-3")

    def test_seeds_nine_default_categories_with_new_names(self) -> None:
        by_code = {
            item.code: item
            for item in hazard_source_category_service.get_all(include_inactive=True)
        }
        for code, name, _description, sort_order in DEFAULT_HAZARD_SOURCE_CATEGORIES:
            self.assertIn(code, by_code)
            self.assertEqual(by_code[code].name, name)
            self.assertEqual(by_code[code].sort_order, sort_order)
            self.assertTrue(by_code[code].active)
        self.assertEqual(
            [code for code, *_rest in DEFAULT_HAZARD_SOURCE_CATEGORIES],
            list(HAZARD_INVENTORY_CATEGORIES),
        )

    def test_migrates_legacy_names_without_changing_codes(self) -> None:
        equipment = hazard_source_category_service.get_by_code(
            HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        assert equipment is not None
        legacy = LEGACY_HAZARD_SOURCE_CATEGORY_NAMES[HAZARD_INVENTORY_CATEGORY_EQUIPMENT]
        with get_session() as session:
            session.execute(
                text(
                    """
                    UPDATE hazard_source_categories
                    SET name = :name
                    WHERE code = :code
                    """
                ),
                {"name": legacy, "code": HAZARD_INVENTORY_CATEGORY_EQUIPMENT},
            )
            session.commit()

        _seed_and_migrate_hazard_source_categories()
        migrated = hazard_source_category_service.get_by_code(
            HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        assert migrated is not None
        self.assertEqual(migrated.id, equipment.id)
        self.assertEqual(migrated.code, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(migrated.name, "Stroje a technická zařízení")

    def test_rename_keeps_source_links(self) -> None:
        category = hazard_source_category_service.get_by_code(
            HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        assert category is not None
        template = hazard_library_template_service.create_template(
            name="Jeřáb UX-RISK-3 rename",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb na pracovišti UX-RISK-3",
        )

        hazard_source_category_service.update_category(
            category.id,
            name="Stroje přejmenované UX-RISK-3",
            description=category.description or "",
            active=True,
            sort_order=category.sort_order,
        )

        reloaded_template = hazard_library_template_service.get_by_id(template.id)
        reloaded_item = hazard_inventory_item_service.get_by_id(item.id)
        assert reloaded_template is not None
        assert reloaded_item is not None
        self.assertEqual(reloaded_template.category, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(reloaded_item.category, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(
            hazard_source_category_service.label_for(HAZARD_INVENTORY_CATEGORY_EQUIPMENT),
            "Stroje přejmenované UX-RISK-3",
        )

        # Obnovení výchozího názvu pro další testy.
        hazard_source_category_service.update_category(
            category.id,
            name="Stroje a technická zařízení",
            description=category.description or "",
            active=True,
            sort_order=category.sort_order,
        )

    def test_duplicate_name_rejected(self) -> None:
        with self.assertRaises(HazardSourceCategoryError):
            hazard_source_category_service.create_category(
                name="  stroje a TECHNICKÁ zařízení  ",
            )
        other = hazard_source_category_service.get_by_code(
            HAZARD_INVENTORY_CATEGORY_OTHER,
        )
        assert other is not None
        with self.assertRaises(HazardSourceCategoryError):
            hazard_source_category_service.update_category(
                other.id,
                name="Stroje a technická zařízení",
                description="",
                active=True,
                sort_order=other.sort_order,
            )

    def test_cannot_deactivate_category_with_active_source(self) -> None:
        category = hazard_source_category_service.create_category(
            name="Dočasná kategorie s aktivním zdrojem",
            description="",
            sort_order=90,
        )
        template = hazard_library_template_service.create_template(
            name="Zdroj v dočasné kategorii",
            category=category.code,
        )
        with self.assertRaises(HazardSourceCategoryError) as raised:
            hazard_source_category_service.deactivate(category.id)
        message = str(raised.exception)
        self.assertIn("Kategorie obsahuje", message)
        self.assertIn("zdroj", message.casefold())
        self.assertIn("přesuňte", message.casefold())

        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)
        self.assertEqual(reloaded.category, category.code)

    def test_can_deactivate_empty_category(self) -> None:
        category = hazard_source_category_service.create_category(
            name="Prázdná kategorie UX-RISK-3",
            description="",
            sort_order=91,
        )
        self.assertTrue(hazard_source_category_service.deactivate(category.id))
        reloaded = hazard_source_category_service.get_by_id(category.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

    def test_deactivate_does_not_change_sources_or_risks(self) -> None:
        category = hazard_source_category_service.create_category(
            name="Kategorie pro bezpečnou deaktivaci",
            description="",
            sort_order=92,
        )
        template = hazard_library_template_service.create_template(
            name="Zdroj před deaktivací kategorie",
            category=category.code,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=category.code,
            name="Položka před deaktivací kategorie",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=item.id,
            name="Událost před deaktivací",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=event.id,
            exposed_group_id=self.exposed_group.id,
            severity=RISK_SEVERITY_MODERATE,
        )

        hazard_library_template_service.deactivate(template.id)
        hazard_inventory_item_service.deactivate_item(item.id)
        self.assertTrue(hazard_source_category_service.deactivate(category.id))

        reloaded_template = hazard_library_template_service.get_by_id(template.id)
        reloaded_item = hazard_inventory_item_service.get_by_id(item.id)
        reloaded_event = hazard_event_service.get_by_id(event.id)
        reloaded_assessment = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded_template is not None
        assert reloaded_item is not None
        assert reloaded_event is not None
        assert reloaded_assessment is not None
        self.assertEqual(reloaded_template.category, category.code)
        self.assertEqual(reloaded_item.category, category.code)
        self.assertFalse(reloaded_template.active)
        self.assertFalse(reloaded_item.active)
        self.assertTrue(reloaded_event.active)
        self.assertEqual(reloaded_event.inventory_item_id, item.id)
        self.assertEqual(reloaded_assessment.hazard_event_id, event.id)

    def test_inactive_category_hidden_when_creating_new_source(self) -> None:
        category = hazard_source_category_service.create_category(
            name="Neaktivní pro nové zdroje",
            description="",
            sort_order=93,
        )
        hazard_source_category_service.deactivate(category.id)

        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        populate_hazard_source_category_combo(combo, current_code=None)
        codes = [combo.itemData(index) for index in range(combo.count())]
        self.assertNotIn(category.code, codes)

        dialog = HazardLibraryTemplateDialog(None)
        try:
            dialog_codes = [
                dialog.category.itemData(index)
                for index in range(dialog.category.count())
            ]
            self.assertNotIn(category.code, dialog_codes)
        finally:
            dialog.close()

        item_dialog = HazardInventoryItemDialog(
            None,
            hazard_identification_id=self.identification.id,
        )
        try:
            item_codes = [
                item_dialog.category.itemData(index)
                for index in range(item_dialog.category.count())
            ]
            self.assertNotIn(category.code, item_codes)
        finally:
            item_dialog.close()

    def test_inactive_category_kept_for_existing_record(self) -> None:
        category = hazard_source_category_service.create_category(
            name="Neaktivní u existujícího záznamu",
            description="",
            sort_order=94,
        )
        template = hazard_library_template_service.create_template(
            name="Existující zdroj s neaktivní kategorií",
            category=category.code,
        )
        # Deaktivace kategorie je povolena až po deaktivaci aktivních zdrojů.
        hazard_library_template_service.deactivate(template.id)
        hazard_source_category_service.deactivate(category.id)

        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        dialog = HazardLibraryTemplateDialog(None, template=reloaded)
        try:
            self.assertEqual(dialog.category.currentData(), category.code)
            self.assertIn("neaktivní", dialog.category.currentText().casefold())
        finally:
            dialog.close()

    def test_categories_are_sorted_by_sort_order(self) -> None:
        first = hazard_source_category_service.create_category(
            name="Řazení A UX-RISK-3",
            sort_order=200,
        )
        second = hazard_source_category_service.create_category(
            name="Řazení B UX-RISK-3",
            sort_order=100,
        )
        ordered = hazard_source_category_service.get_all(include_inactive=True)
        codes = [item.code for item in ordered]
        self.assertLess(codes.index(second.code), codes.index(first.code))

        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        populate_hazard_source_category_combo(combo)
        active_codes = [combo.itemData(index) for index in range(combo.count())]
        self.assertLess(
            active_codes.index(second.code),
            active_codes.index(first.code),
        )

    def test_move_source_category_preserves_links(self) -> None:
        source_category = hazard_source_category_service.create_category(
            name="Zdrojová kategorie přesunu",
            sort_order=95,
        )
        target_category = hazard_source_category_service.create_category(
            name="Cílová kategorie přesunu",
            sort_order=96,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=source_category.code,
            name="Položka k přesunu kategorie",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=item.id,
            name="Událost u přesunu",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=event.id,
            exposed_group_id=self.exposed_group.id,
            severity=RISK_SEVERITY_MODERATE,
        )

        updated = hazard_inventory_item_service.update_item(
            item.id,
            category=target_category.code,
            name=item.name,
            description=item.description or "",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.category, target_category.code)

        reloaded_event = hazard_event_service.get_by_id(event.id)
        reloaded_assessment = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded_event is not None
        assert reloaded_assessment is not None
        self.assertEqual(reloaded_event.inventory_item_id, item.id)
        self.assertEqual(reloaded_assessment.hazard_event_id, event.id)


if __name__ == "__main__":
    unittest.main()
