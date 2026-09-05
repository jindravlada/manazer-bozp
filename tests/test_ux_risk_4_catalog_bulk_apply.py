"""UX-RISK-4 – hromadné převzetí zdrojů rizika z katalogu."""

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
        HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE,
        HAZARD_LIBRARY_SCOPE_MANUAL,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_apply_to_inventory_dialog import (
        HazardLibraryApplyToInventoryDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryBulkApplyUxRisk4TestCase(unittest.TestCase):
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
            name="Provoz UX-RISK-4",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna UX-RISK-4",
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
    ):
        template = hazard_library_template_service.create_template(
            name=name,
            category=category,
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

    def _open_dialog(self) -> HazardLibraryApplyToInventoryDialog:
        return HazardLibraryApplyToInventoryDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )

    def _list_names(self, dialog: HazardLibraryApplyToInventoryDialog) -> set[str]:
        return {
            dialog.sources_list.item(i).text().split(" (", 1)[0]
            for i in range(dialog.sources_list.count())
        }

    def _item_by_name(self, dialog: HazardLibraryApplyToInventoryDialog, name: str):
        for index in range(dialog.sources_list.count()):
            item = dialog.sources_list.item(index)
            if item.text().split(" (", 1)[0] == name:
                return item
        self.fail(f"Zdroj {name!r} není v nabídce.")

    def _check_by_name(self, dialog: HazardLibraryApplyToInventoryDialog, name: str) -> None:
        from PySide6.QtCore import Qt

        self._item_by_name(dialog, name).setCheckState(Qt.CheckState.Checked)

    def _set_category(
        self,
        dialog: HazardLibraryApplyToInventoryDialog,
        category: str | None,
    ) -> None:
        index = dialog.category_filter.findData(category)
        self.assertGreaterEqual(index, 0)
        dialog.category_filter.setCurrentIndex(index)

    def _inventory_template_ids(self) -> list[int]:
        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
            include_inactive=True,
        )
        return [item.source_template_id for item in items if item.source_template_id]

    def test_items_have_checkboxes_without_select_all(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QPushButton

        self._create_template(name="Vrtačka")
        dialog = self._open_dialog()
        try:
            self.assertGreater(dialog.sources_list.count(), 0)
            item = dialog.sources_list.item(0)
            self.assertTrue(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            self.assertEqual(item.checkState(), Qt.CheckState.Unchecked)
            texts = [button.text() for button in dialog.findChildren(QPushButton)]
            for forbidden in ("Vybrat vše", "Označit vše"):
                self.assertFalse(any(forbidden in text for text in texts))
        finally:
            dialog.close()

    def test_apply_three_sources_at_once(self) -> None:
        first = self._create_template(name="Vrtačka")
        second = self._create_template(name="Fréza")
        third = self._create_template(name="Lis")
        dialog = self._open_dialog()
        try:
            self._check_by_name(dialog, "Vrtačka")
            self._check_by_name(dialog, "Fréza")
            self._check_by_name(dialog, "Lis")
            self.assertEqual(
                dialog.selected_count_label.text(),
                HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE.format(selected=3),
            )
            self.assertTrue(dialog.apply_button.isEnabled())
            dialog.accept()
            self.assertEqual(len(dialog.results), 3)
            self.assertIsNotNone(dialog.result)
        finally:
            dialog.close()

        applied = set(self._inventory_template_ids())
        self.assertEqual(applied, {first.id, second.id, third.id})
        self.assertEqual(len(self._inventory_template_ids()), 3)

    def test_applied_sources_hidden_on_next_open(self) -> None:
        first = self._create_template(name="Vrtačka")
        self._create_template(name="Fréza")
        self._create_template(name="Lis")
        dialog = self._open_dialog()
        try:
            self._check_by_name(dialog, "Vrtačka")
            self._check_by_name(dialog, "Fréza")
            self._check_by_name(dialog, "Lis")
            dialog.accept()
        finally:
            dialog.close()

        dialog2 = self._open_dialog()
        try:
            self.assertEqual(self._list_names(dialog2), set())
            self.assertEqual(dialog2.sources_list.count(), 0)
            item = dialog2.sources_list.item(0)
            self.assertIsNone(item)
        finally:
            dialog2.close()

        remaining = self._create_template(name="Jeřáb")
        dialog3 = self._open_dialog()
        try:
            self.assertEqual(self._list_names(dialog3), {"Jeřáb"})
            self.assertNotIn("Vrtačka", self._list_names(dialog3))
            self.assertNotEqual(remaining.id, first.id)
        finally:
            dialog3.close()

    def test_category_filter_preserves_checks_from_other_category(self) -> None:
        from PySide6.QtCore import Qt

        equipment = self._create_template(name="Vrtačka")
        structure = self._create_template(
            name="Montážní jáma",
            category=HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        )
        dialog = self._open_dialog()
        try:
            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
            self._check_by_name(dialog, "Vrtačka")
            self.assertEqual(dialog.selected_template_ids(), [equipment.id])

            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_STRUCTURE)
            self.assertEqual(self._list_names(dialog), {"Montážní jáma"})
            self.assertEqual(
                self._item_by_name(dialog, "Montážní jáma").checkState(),
                Qt.CheckState.Unchecked,
            )
            self.assertEqual(dialog.selected_template_ids(), [equipment.id])
            self.assertEqual(
                dialog.selected_count_label.text(),
                HAZARD_LIBRARY_APPLY_SELECTED_COUNT_TEMPLATE.format(selected=1),
            )

            self._check_by_name(dialog, "Montážní jáma")
            self.assertEqual(
                dialog.selected_template_ids(),
                [equipment.id, structure.id],
            )

            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
            self.assertEqual(
                self._item_by_name(dialog, "Vrtačka").checkState(),
                Qt.CheckState.Checked,
            )
            self.assertEqual(
                dialog.selected_template_ids(),
                [equipment.id, structure.id],
            )

            dialog.accept()
            self.assertEqual(
                {result.item.source_template_id for result in dialog.results},
                {equipment.id, structure.id},
            )
        finally:
            dialog.close()

        self.assertEqual(
            set(self._inventory_template_ids()),
            {equipment.id, structure.id},
        )

    def test_cancel_does_not_apply(self) -> None:
        self._create_template(name="Vrtačka")
        self._create_template(name="Fréza")
        dialog = self._open_dialog()
        try:
            self._check_by_name(dialog, "Vrtačka")
            self._check_by_name(dialog, "Fréza")
            dialog.reject()
            self.assertEqual(dialog.results, [])
            self.assertIsNone(dialog.result)
        finally:
            dialog.close()
        self.assertEqual(self._inventory_template_ids(), [])

    def test_apply_without_selection_creates_nothing(self) -> None:
        self._create_template(name="Vrtačka")
        dialog = self._open_dialog()
        try:
            self.assertFalse(dialog.apply_button.isEnabled())
            self.assertEqual(dialog.selected_template_ids(), [])
            dialog.accept()
            self.assertEqual(dialog.results, [])
            self.assertIsNone(dialog.result)
        finally:
            dialog.close()
        self.assertEqual(self._inventory_template_ids(), [])

    def test_row_selection_and_double_click_do_not_apply(self) -> None:
        self._create_template(name="Vrtačka")
        dialog = self._open_dialog()
        try:
            item = self._item_by_name(dialog, "Vrtačka")
            dialog.sources_list.setCurrentRow(0)
            dialog.sources_list.itemDoubleClicked.emit(item)
            self.assertFalse(dialog.apply_button.isEnabled())
            self.assertEqual(dialog.results, [])
            self.assertIsNone(dialog.result)
        finally:
            dialog.close()
        self.assertEqual(self._inventory_template_ids(), [])

    def test_no_duplicate_sources_after_bulk_apply(self) -> None:
        first = self._create_template(name="Vrtačka")
        second = self._create_template(name="Fréza")
        third = self._create_template(name="Lis")
        dialog = self._open_dialog()
        try:
            self._check_by_name(dialog, "Vrtačka")
            self._check_by_name(dialog, "Fréza")
            self._check_by_name(dialog, "Lis")
            dialog.accept()
        finally:
            dialog.close()

        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
        )
        ids = [item.source_template_id for item in items]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(set(ids), {first.id, second.id, third.id})

        for template_id in (first.id, second.id, third.id):
            with self.assertRaises(HazardLibraryTemplateApplyError):
                hazard_library_template_apply_service.apply_template(
                    hazard_identification_id=self.identification.id,
                    template_id=template_id,
                )

        dialog2 = self._open_dialog()
        try:
            self.assertEqual(self._list_names(dialog2), set())
        finally:
            dialog2.close()


if __name__ == "__main__":
    unittest.main()
