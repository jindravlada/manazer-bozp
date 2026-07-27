"""RISK-UX-6: společný výběr ohrožených skupin z funkcí/rolí a číselníku rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ux-6-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        SOURCE_TYPE_ROLE,
        ExposedTargetRef,
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
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskUx6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz UX6",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna UX6",
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
            name="Jeřáb UX6",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pád břemene UX6",
        )
        self.group = ensure_exposed_group("Dodavatelé UX6")
        roles = responsibility_role_service.get_all(include_inactive=False)
        self.assertTrue(roles)
        self.role = roles[0]

    def test_schema_has_source_type(self) -> None:
        columns = _table_columns("hazard_risk_assessment_exposed_groups")
        self.assertIn("source_type", columns)
        template_columns = _table_columns(
            "hazard_library_template_assessment_exposed_groups"
        )
        self.assertIn("source_type", template_columns)

    def test_create_with_role_and_hazard_group(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            target_refs=[
                ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id),
                ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id),
            ],
            severity=RISK_SEVERITY_MODERATE,
        )
        refs = hazard_risk_assessment_service.get_target_refs(assessment.id)
        self.assertEqual(
            [(ref.source_type, ref.source_id) for ref in refs],
            [
                (SOURCE_TYPE_ROLE, self.role.id),
                (SOURCE_TYPE_HAZARD_GROUP, self.group.id),
            ],
        )
        display = hazard_risk_assessment_service.get_exposed_group_display_name(assessment)
        self.assertIn(self.role.name, display)
        self.assertIn(self.group.name, display)
        self.assertNotIn("role", display.casefold())
        self.assertNotIn("hazard_group", display.casefold())

    def test_rename_role_updates_display(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id)],
            severity=RISK_SEVERITY_MODERATE,
        )
        new_name = f"{self.role.name} vlečky UX6"
        responsibility_role_service.update_role(
            self.role.id,
            name=new_name,
            description=self.role.description or "",
            active=True,
        )
        reloaded = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded is not None
        display = hazard_risk_assessment_service.get_exposed_group_display_name(reloaded)
        self.assertEqual(display, new_name)

    def test_selector_lists_both_sections(self) -> None:
        from core.widgets.exposed_target_selector import ExposedTargetSelector
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
            SECTION_LABEL_HAZARD_GROUPS,
            SECTION_LABEL_ROLES,
        )

        selector = ExposedTargetSelector()
        labels = [selector.itemText(i) for i in range(selector.count())]
        self.assertIn(SECTION_LABEL_ROLES, labels)
        self.assertIn(SECTION_LABEL_HAZARD_GROUPS, labels)
        self.assertTrue(any(self.role.name == label for label in labels))
        self.assertTrue(any(self.group.name == label for label in labels))

    def test_multi_selector_returns_refs(self) -> None:
        from core.widgets.multi_exposed_target_selector import MultiExposedTargetSelector

        widget = MultiExposedTargetSelector()
        widget.set_refs(
            [
                ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id),
                ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id),
            ]
        )
        refs = widget.selected_refs()
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0].source_type, SOURCE_TYPE_ROLE)
        self.assertEqual(refs[1].source_type, SOURCE_TYPE_HAZARD_GROUP)


if __name__ == "__main__":
    unittest.main()
