"""R21 – jeden zdroj pravdy: nové zdroje vznikají jen v Katalogu."""

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
        HAZARD_LIBRARY_SAVE_TO_LIBRARY_BUTTON,
        HAZARD_LIBRARY_SCOPE_MANUAL,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
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
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        HazardLibraryTemplateError,
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryOneMasterR21TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

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
            name="Provoz R21",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R21",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")

    def _patch_info(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        )

    def test_save_to_library_button_removed(self) -> None:
        widget = HazardInventoryWidget()
        self.assertFalse(hasattr(widget, "save_to_library_btn"))
        labels = []
        for i in range(widget.toolbar.count()):
            item = widget.toolbar.itemAt(i)
            if item is not None and item.widget() is not None:
                text = getattr(item.widget(), "text", lambda: "")()
                if text:
                    labels.append(text)
        self.assertNotIn(HAZARD_LIBRARY_SAVE_TO_LIBRARY_BUTTON, labels)

    def test_add_new_saves_catalog_and_applies_to_identification(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None

        catalog = HazardLibraryTemplateDialog(
            dialog.inventory_widget,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            on_template_persisted=dialog.inventory_widget._on_catalog_template_persisted,
        )
        catalog.name.setText("Montážní jáma")
        with self._patch_info():
            self.assertTrue(catalog._save_all())

        templates = hazard_library_template_service.repository.get_all(include_inactive=False)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, "Montážní jáma")

        wc_items = dialog._identification_store.get_items()
        self.assertEqual(len(wc_items), 1)
        self.assertEqual(wc_items[0].name, "Montážní jáma")
        self.assertEqual(wc_items[0].source_template_id, templates[0].id)

        # Do DB ještě ne – jen WC.
        self.assertEqual(
            len(
                hazard_inventory_item_service.get_for_identification(
                    self.identification.id,
                ),
            ),
            0,
        )
        catalog._closing = True
        catalog.close()
        dialog._closing = True
        dialog.close()

    def test_cancel_catalog_creates_nothing(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        catalog = HazardLibraryTemplateDialog(
            dialog.inventory_widget,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            on_template_persisted=dialog.inventory_widget._on_catalog_template_persisted,
        )
        catalog.name.setText("Nedokončený")
        catalog._closing = True
        catalog.reject()

        self.assertEqual(
            len(hazard_library_template_service.repository.get_all(include_inactive=True)),
            0,
        )
        self.assertEqual(len(dialog._identification_store.get_items()), 0)
        dialog._closing = True
        dialog.close()

    def test_edit_master_syncs_identification_wc(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        template = hazard_library_template_service.create_template(
            name="Jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        dialog._identification_store.apply_from_template(template.id)
        item = dialog._identification_store.get_items()[0]

        catalog = HazardLibraryTemplateDialog(
            dialog.inventory_widget,
            template=template,
            on_template_persisted=lambda saved: dialog.inventory_widget._on_master_edited(
                item.id,
                saved,
            ),
        )
        catalog.name.setText("Jeřáb mostový")
        with self._patch_info():
            self.assertTrue(catalog._save_all())

        synced = dialog._identification_store.get_item(item.id)
        assert synced is not None
        self.assertEqual(synced.name, "Jeřáb mostový")
        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Jeřáb mostový")
        catalog._closing = True
        catalog.close()
        dialog._closing = True
        dialog.close()

    def test_no_new_local_sources_via_add_item_path(self) -> None:
        """Přidat nový musí jít přes katalogový dialog, ne InventoryItemDialog."""
        dialog = HazardIdentificationDialog(identification=self.identification)
        opened = {"catalog": False}

        def fake_exec(self_dialog):
            opened["catalog"] = True
            return 0

        with patch.object(HazardLibraryTemplateDialog, "exec", fake_exec):
            with patch(
                "moduly.rizeni_rizik.ui.hazard_inventory_widget.exec_maximized",
                side_effect=lambda d: fake_exec(d),
            ):
                dialog.inventory_widget.add_item()

        self.assertTrue(opened["catalog"])
        self.assertEqual(
            len(
                hazard_inventory_item_service.get_for_identification(
                    self.identification.id,
                ),
            ),
            0,
        )
        dialog._closing = True
        dialog.close()

    def test_duplicate_name_prompt_open_existing(self) -> None:
        existing = hazard_library_template_service.create_template(
            name="Vrtačka",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        dialog = HazardIdentificationDialog(identification=self.identification)
        catalog = HazardLibraryTemplateDialog(
            dialog.inventory_widget,
            on_template_persisted=dialog.inventory_widget._on_catalog_template_persisted,
        )
        catalog.name.setText("Vrtačka")
        with patch.object(catalog, "_prompt_duplicate_name", return_value="open"):
            self.assertTrue(catalog._save_all())

        self.assertEqual(catalog.template.id, existing.id)
        items = dialog._identification_store.get_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_template_id, existing.id)
        self.assertEqual(
            len(hazard_library_template_service.repository.get_all(include_inactive=True)),
            1,
        )
        catalog._closing = True
        catalog.close()
        dialog._closing = True
        dialog.close()

    def test_duplicate_name_create_new_allowed_after_confirm(self) -> None:
        hazard_library_template_service.create_template(
            name="Vrtačka",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.create_template(
                name="Vrtačka",
                category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            )
        second = hazard_library_template_service.create_template(
            name="Vrtačka",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            allow_duplicate_name=True,
        )
        self.assertIsNotNone(second.id)
        self.assertEqual(
            len(hazard_library_template_service.repository.get_all(include_inactive=False)),
            2,
        )

    def test_legacy_local_item_still_editable(self) -> None:
        local = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Starý lokální",
        )
        self.assertIsNone(local.source_template_id)
        dialog = HazardIdentificationDialog(identification=self.identification)
        item = dialog._identification_store.get_item(local.id)
        assert item is not None
        self.assertIsNone(item.source_template_id)
        dialog._closing = True
        dialog.close()


if __name__ == "__main__":
    unittest.main()
