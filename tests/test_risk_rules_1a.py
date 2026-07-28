"""RISK-RULES-1a: našeptávače a odrážkový výstup PBP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-rules-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        SOURCE_TYPE_ROLE,
        ExposedTargetRef,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class RiskRules1aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group_a = ensure_exposed_group("RULES1a skupina A")
        self.group_b = ensure_exposed_group("RULES1a skupina B")
        self.role_a = responsibility_role_service.create_role(name="RULES1a Strojvedoucí")
        self.role_b = responsibility_role_service.create_role(name="RULES1a Jeřábník")
        self.person = person_service.create_person(first_name="Rules", last_name="OneA")
        self.operation = settings_service.save_workplace(
            name="RULES1a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="RULES1a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _seed(
        self,
        *,
        description: str,
        target_refs: list[ExposedTargetRef],
        event_name: str,
    ) -> HazardExistingMeasure:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            responsible_person_id=self.person.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name=f"Položka {event_name}",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=event_name,
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            target_refs=target_refs,
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_add_one_role_via_selector(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.roles.selector.set_role_id(self.role_a.id)
        dialog.roles.add_current()
        self.assertEqual(dialog.selected_role_ids(), [self.role_a.id])
        self.assertEqual(dialog.roles_list.count(), 1)

    def test_add_multiple_roles(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.roles.selector.set_role_id(self.role_a.id)
        dialog.roles.add_current()
        dialog.roles.selector.set_role_id(self.role_b.id)
        dialog.roles.add_current()
        self.assertEqual(
            dialog.selected_role_ids(),
            [self.role_a.id, self.role_b.id],
        )

    def test_add_multiple_groups(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.groups.selector.set_group_id(self.group_a.id)
        dialog.groups.add_current()
        dialog.groups.selector.set_group_id(self.group_b.id)
        dialog.groups.add_current()
        self.assertEqual(
            dialog.selected_group_ids(),
            [self.group_a.id, self.group_b.id],
        )

    def test_combine_roles_and_groups(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.roles.selector.set_role_id(self.role_a.id)
        dialog.roles.add_current()
        dialog.groups.selector.set_group_id(self.group_a.id)
        dialog.groups.add_current()
        self.assertEqual(dialog.selected_role_ids(), [self.role_a.id])
        self.assertEqual(dialog.selected_group_ids(), [self.group_a.id])

    def test_duplicate_role_not_added_twice(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.roles.selector.set_role_id(self.role_a.id)
        dialog.roles.add_current()
        dialog.roles.selector.set_role_id(self.role_a.id)
        dialog.roles.add_current()
        self.assertEqual(dialog.selected_role_ids(), [self.role_a.id])
        self.assertEqual(dialog.roles_list.count(), 1)

    def test_remove_selected_role(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.set_selected_role_ids([self.role_a.id, self.role_b.id])
        dialog.roles_list.setCurrentRow(0)
        dialog.roles.remove_selected()
        self.assertEqual(dialog.selected_role_ids(), [self.role_b.id])

    def test_generate_union_from_dialog_selection(self) -> None:
        self._seed(
            description="Pravidlo role",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id)],
            event_name="DlgRole",
        )
        self._seed(
            description="Pravidlo skupina",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id)],
            event_name="DlgGroup",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            role_ids=[self.role_a.id],
            endangered_group_ids=[self.group_a.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(
            {rule.text for rule in rules},
            {"Pravidlo role.", "Pravidlo skupina."},
        )

    def test_odt_heading_bullets_and_profession_label(self) -> None:
        self._seed(
            description="Používej helmu",
            target_refs=[
                ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id),
                ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id),
            ],
            event_name="Out",
        )
        path = pravidla_bezpecne_prace_service.export_document(
            role_ids=[self.role_a.id],
            endangered_group_ids=[self.group_a.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)
        assert path is not None
        content = _odt_content(path)
        self.assertIn("DODRŽUJTE TATO PRAVIDLA", content)
        self.assertNotIn("PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE", content)
        self.assertIn("• Používej helmu.", content)
        self.assertNotRegex(content.split("DODRŽUJTE TATO PRAVIDLA", 1)[1], r"\d+\.\s")
        self.assertIn('text:style-name="PbpRuleBullet"', content)
        self.assertIn("Profese", content)
        self.assertNotIn(">Cíl<", content)
        # Jedno opatření = jedna odrážka (ne duplicita).
        self.assertEqual(content.count("• Používej helmu."), 1)


if __name__ == "__main__":
    unittest.main()
