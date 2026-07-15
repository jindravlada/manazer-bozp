"""Fáze R16a – zjednodušení číselníku ohrožených skupin."""

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

    from core.database.database_initializer import _seed_exposed_groups, initialize_database

    initialize_database()

    from core.widgets.exposed_group_selector import (
        ADD_NEW_EXPOSED_GROUP,
        ExposedGroupSelector,
        add_new_exposed_group_label,
    )
    from moduly.nastaveni.modely.exposed_group import ExposedGroup
    from moduly.nastaveni.sluzby.exposed_group_service import (
        ExposedGroupError,
        ExposedGroupMatchKind,
        exposed_group_service,
    )
    from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class ExposedGroupCatalogR16aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(ExposedGroup))
            session.commit()

        _seed_exposed_groups()

        operation = settings_service.save_workplace(
            name="Provoz R16a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R16a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pád břemene",
        )

    def test_fresh_database_has_two_default_groups(self) -> None:
        groups = exposed_group_service.get_active_all()
        names = {group.name for group in groups}
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            names,
            {"Zaměstnanci daného pracoviště", "Dodavatelé"},
        )

    def test_seed_preserves_user_groups_on_subsequent_run(self) -> None:
        custom = exposed_group_service.create_group(name="Posunovač")
        count_before = len(exposed_group_service.get_all(include_inactive=True))
        _seed_exposed_groups()
        groups = exposed_group_service.get_all(include_inactive=True)
        names = {group.name for group in groups}
        self.assertEqual(len(groups), count_before)
        self.assertIn(custom.name, names)
        self.assertIn("Posunovač", names)

    def test_repeated_seed_leaves_catalog_unchanged(self) -> None:
        exposed_group_service.create_group(name="Externisté")
        before = {
            group.name
            for group in exposed_group_service.get_all(include_inactive=True)
        }
        _seed_exposed_groups()
        _seed_exposed_groups()
        after = {
            group.name
            for group in exposed_group_service.get_all(include_inactive=True)
        }
        self.assertEqual(after, before)
        self.assertNotIn("Obsluha zařízení", after)
        self.assertNotIn("Návštěvy", after)

    def test_selector_filters_groups_while_typing(self) -> None:
        ensure_exposed_group("Elektrikáři")
        ensure_exposed_group("Mechanici")
        selector = ExposedGroupSelector()
        selector.setCurrentText("elek")
        selector._rebuild_popup_items(selected_id=None)
        popup_names = {
            selector.itemText(index)
            for index in range(selector.count())
            if selector.itemData(index) is not ADD_NEW_EXPOSED_GROUP
        }
        self.assertIn("Elektrikáři", popup_names)
        self.assertNotIn("Mechanici", popup_names)

    def test_selector_selects_existing_group(self) -> None:
        group = ensure_exposed_group("Obsluha zařízení")
        selector = ExposedGroupSelector()
        selector.set_group_id(group.id)
        self.assertEqual(selector.current_group_id(), group.id)

    @patch("core.widgets.exposed_group_selector.QMessageBox.question")
    def test_selector_creates_new_group_from_search(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        mock_question.return_value = QMessageBox.StandardButton.Yes
        selector = ExposedGroupSelector()
        group_id = selector._resolve_name_to_group_id("Nová testovací skupina")
        self.assertIsNotNone(group_id)
        created = exposed_group_service.get_by_id(group_id)
        assert created is not None
        self.assertEqual(created.name, "Nová testovací skupina")

    def test_selector_has_no_one_time_use_option(self) -> None:
        selector = ExposedGroupSelector()
        selector.setCurrentText("Externí partneři")
        selector._rebuild_popup_items(selected_id=None)
        labels = [selector.itemText(index) for index in range(selector.count())]
        self.assertFalse(any("použít jednoráz" in label.casefold() for label in labels))
        self.assertTrue(
            any(label.startswith("Přidat novou skupinu") for label in labels),
        )

    def test_reject_active_duplicate_on_create(self) -> None:
        exposed_group_service.create_group(name="Technik")
        with self.assertRaises(ExposedGroupError):
            exposed_group_service.create_group(name="  technik ")

    @patch("core.widgets.exposed_group_selector.QMessageBox.question")
    def test_offer_activate_inactive_match_on_create(self, mock_question) -> None:
        from PySide6.QtWidgets import QMessageBox

        group = exposed_group_service.create_group(name="Dočasná skupina", active=True)
        exposed_group_service.deactivate(group.id)
        mock_question.return_value = QMessageBox.StandardButton.Yes

        selector = ExposedGroupSelector()
        resolved = selector._resolve_name_to_group_id("dočasná skupina")
        self.assertEqual(resolved, group.id)
        reloaded = exposed_group_service.get_by_id(group.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_management_table_shows_names_not_ids(self) -> None:
        group = ensure_exposed_group("Jeřábník")
        dialog = ExposedGroupsManagementDialog()
        dialog.refresh()
        visible_names = {
            dialog.table.item(row, 0).text()
            for row in range(dialog.table.rowCount())
            if dialog.table.item(row, 0) is not None
        }
        self.assertIn(group.name, visible_names)
        self.assertNotIn(str(group.id), visible_names)

    @patch("moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog.ExposedGroupsManagementDialog.exec")
    def test_dialog_refreshes_groups_after_management(self, mock_exec) -> None:
        mock_exec.return_value = 0
        active = ensure_exposed_group("Aktivní test")
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event.id,
        )
        before_count = dialog.exposed_group.count()
        exposed_group_service.create_group(name="Nová ze správy")
        dialog._open_groups_management()
        self.assertGreaterEqual(dialog.exposed_group.count(), before_count)
        dialog.exposed_group.set_group_id(active.id)
        self.assertEqual(dialog.exposed_group.current_group_id(), active.id)

    def test_assessment_can_be_created_with_new_group_from_selector(self) -> None:
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event.id,
        )
        group = ensure_exposed_group("Vrtačkář")
        dialog.exposed_group.set_group_id(group.id)
        dialog.consequence.setPlainText("Poranění ruky")
        severity_index = dialog.severity.findData(RISK_SEVERITY_MODERATE)
        dialog.severity.setCurrentIndex(severity_index)
        dialog.accept()

        rows = hazard_risk_assessment_service.get_for_identification(self.identification.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].assessment.exposed_group_id, group.id)

    def test_add_new_label_format(self) -> None:
        self.assertEqual(
            add_new_exposed_group_label("Strojníci"),
            'Přidat novou skupinu „Strojníci"',
        )

    def test_classify_name_for_ai_import(self) -> None:
        active = ensure_exposed_group("Údržba")
        result = exposed_group_service.classify_name("údržba")
        self.assertEqual(result.kind, ExposedGroupMatchKind.ACTIVE)
        self.assertEqual(result.groups[0].id, active.id)


if __name__ == "__main__":
    unittest.main()
