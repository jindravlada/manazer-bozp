"""HOTFIX R20c.1 – MultiExposedGroupSelector musí vracet vybraná ID."""

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

    from core.widgets.multi_exposed_group_selector import MultiExposedGroupSelector
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
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
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import (
        HazardRiskAssessmentDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class MultiExposedGroupSelectorR20c1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group_a = ensure_exposed_group("Zaměstnanci pracoviště")
        self.group_b = ensure_exposed_group("Návštěvy")

        operation = settings_service.save_workplace(
            name="Provoz R20c.1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště R20c.1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=item.id,
            name="Přejetí osoby",
        )

    def test_selected_group_ids_includes_combo_selection_without_add(self) -> None:
        widget = MultiExposedGroupSelector()
        widget.selector.set_group_id(self.group_a.id)
        ids = widget.selected_group_ids()
        self.assertEqual(ids, [self.group_a.id])
        self.assertEqual(widget.list_widget.count(), 1)

    def test_select_two_groups_returns_two_ids(self) -> None:
        widget = MultiExposedGroupSelector()
        widget.selector.set_group_id(self.group_a.id)
        widget.add_current()
        widget.selector.set_group_id(self.group_b.id)
        ids = widget.selected_group_ids()
        self.assertEqual(ids, [self.group_a.id, self.group_b.id])

    def test_dialog_save_gets_two_group_ids_without_validation_error(self) -> None:
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event.id,
        )
        dialog.exposed_groups.selector.set_group_id(self.group_a.id)
        dialog.exposed_groups.add_current()
        dialog.exposed_groups.selector.set_group_id(self.group_b.id)
        # Druhá skupina zůstane jen v selectoru (bez kliknutí na Přidat).
        data = dialog.get_data()
        self.assertEqual(
            data["exposed_group_ids"],
            [self.group_a.id, self.group_b.id],
        )
        self.assertTrue(data["exposed_group_ids"])

        dialog.accept()
        rows = hazard_risk_assessment_service.get_for_identification(
            self.identification.id,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            hazard_risk_assessment_service.get_group_ids(rows[0].assessment.id),
            [self.group_a.id, self.group_b.id],
        )


if __name__ == "__main__":
    unittest.main()
