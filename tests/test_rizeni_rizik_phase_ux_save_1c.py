"""UX-SAVE-1c – odložené ukládání editoru Identifikace rizik."""

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
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_MANUAL
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
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
        HazardIdentificationWorkingCopy,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_apply_to_inventory_dialog import (
        HazardLibraryApplyToInventoryDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardIdentificationUxSave1cTestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz UX-SAVE-1c",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna UX-SAVE-1c",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = self._create_template(name="Portálový jeřáb")
        self.other_template = self._create_template(name="Vrtačka")

    def _create_template(self, *, name: str):
        template = hazard_library_template_service.create_template(
            name=name,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            operation_ids=[],
        )
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

    def _patch_info(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        )

    def _patch_question_yes(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        )

    def _db_item_count(self) -> int:
        return len(
            hazard_inventory_item_service.get_for_identification(
                self.identification.id,
                include_inactive=True,
            ),
        )

    def test_save_persists_manual_item_and_clears_dirty(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Ruční zdroj",
            description="Popis",
        )
        dialog._update_save_enabled()
        self.assertTrue(dialog.is_dirty())
        self.assertTrue(dialog.save_button.isEnabled())
        self.assertEqual(self._db_item_count(), 0)

        with self._patch_info():
            self.assertTrue(dialog._save_all())

        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.save_button.isEnabled())
        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Ruční zdroj")
        dialog._closing = True
        dialog.close()

    def test_cancel_discards_without_db_write(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Dočasný zdroj",
        )
        self.assertTrue(dialog.is_dirty())

        with self._patch_question_yes():
            dialog._on_cancel_clicked()

        self.assertEqual(self._db_item_count(), 0)

    def test_apply_from_catalog_into_wc_visible_then_cancel_drops(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        result = dialog._identification_store.apply_from_template(self.template.id)
        self.assertEqual(result.item.name, "Portálový jeřáb")
        self.assertGreater(result.event_count, 0)
        self.assertEqual(self._db_item_count(), 0)
        self.assertTrue(dialog.is_dirty())

        names = {item.name for item in dialog._identification_store.get_items()}
        self.assertIn("Portálový jeřáb", names)

        dialog._discard_working_copy()
        self.assertEqual(self._db_item_count(), 0)
        self.assertEqual(len(dialog._identification_store.get_items()), 0)
        dialog._closing = True
        dialog.close()

    def test_apply_save_persists_tree(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.apply_from_template(self.template.id)
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_template_id, self.template.id)
        events = hazard_event_service.get_for_inventory_item(items[0].id)
        self.assertEqual(len(events), 1)
        dialog._closing = True
        dialog.close()

    def test_apply_dialog_uses_working_copy(self) -> None:
        from PySide6.QtCore import Qt

        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        apply_dialog = HazardLibraryApplyToInventoryDialog(
            dialog.inventory_widget,
            hazard_identification_id=self.identification.id,
        )
        self.assertGreater(apply_dialog.sources_list.count(), 0)
        apply_dialog.sources_list.item(0).setCheckState(Qt.CheckState.Checked)
        with self._patch_info():
            apply_dialog.accept()
        self.assertIsNotNone(apply_dialog.result)
        self.assertEqual(self._db_item_count(), 0)
        self.assertTrue(dialog._identification_store.is_dirty)
        apply_dialog.close()
        dialog._closing = True
        dialog.close()

    def test_applied_hidden_in_offer_from_wc(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.apply_from_template(self.template.id)

        apply_dialog = HazardLibraryApplyToInventoryDialog(
            dialog.inventory_widget,
            hazard_identification_id=self.identification.id,
        )
        names = {
            apply_dialog.sources_list.item(i).text().split(" (", 1)[0]
            for i in range(apply_dialog.sources_list.count())
        }
        self.assertNotIn("Portálový jeřáb", names)
        self.assertIn("Vrtačka", names)
        apply_dialog.close()
        dialog._closing = True
        dialog.close()

    def test_activate_deactivate_on_wc_only(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        item = dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zdroj",
            active=True,
        )
        dialog._identification_store.deactivate_item(item.id)
        self.assertFalse(dialog._identification_store.get_item(item.id).active)
        self.assertEqual(self._db_item_count(), 0)

        with self._patch_info():
            dialog._save_all()
        saved = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
            include_inactive=True,
        )
        self.assertEqual(len(saved), 1)
        self.assertFalse(saved[0].active)
        dialog._closing = True
        dialog.close()

    def test_close_prompt_cancel_keeps_dirty(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zůstat",
        )
        with patch.object(dialog, "_prompt_unsaved_close", return_value="cancel"):
            from PySide6.QtGui import QCloseEvent

            event = QCloseEvent()
            dialog.closeEvent(event)
            self.assertFalse(event.isAccepted())
        self.assertTrue(dialog.is_dirty())
        self.assertEqual(self._db_item_count(), 0)
        dialog._closing = True
        dialog.close()

    def test_close_prompt_discard_drops_changes(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zahodit",
        )
        with patch.object(dialog, "_prompt_unsaved_close", return_value="discard"):
            from PySide6.QtGui import QCloseEvent

            event = QCloseEvent()
            dialog.closeEvent(event)
        self.assertEqual(self._db_item_count(), 0)

    def test_close_prompt_save_persists(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        assert dialog._identification_store is not None
        dialog._identification_store.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Uložit při zavření",
        )
        with self._patch_info():
            with patch.object(dialog, "_prompt_unsaved_close", return_value="save"):
                from PySide6.QtGui import QCloseEvent

                event = QCloseEvent()
                dialog.closeEvent(event)
        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Uložit při zavření")

    def test_working_copy_direct_commit_roundtrip(self) -> None:
        wc = HazardIdentificationWorkingCopy.load(self.identification.id)
        wc.create_item(
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="WC roundtrip",
        )
        event = wc.create_event(
            inventory_item_id=wc.items[0].id,
            name="Událost",
        )
        wc.create_assessment(
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="OK",
        )
        self.assertEqual(self._db_item_count(), 0)
        wc.commit()
        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
        )
        self.assertEqual(len(items), 1)
        events = hazard_event_service.get_for_inventory_item(items[0].id)
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
