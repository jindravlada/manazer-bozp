"""RISK-RULES-1: vícevýběr rolí a ohrožených skupin pro PBP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-rules-1-"))
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
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
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


class RiskRules1TestCase(unittest.TestCase):
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

        self.group_a = ensure_exposed_group("RULES1 skupina A")
        self.group_b = ensure_exposed_group("RULES1 skupina B")
        for group in (self.group_a, self.group_b):
            if not group.active:
                exposed_group_service.activate(group.id)
                group.active = True

        self.role_a = responsibility_role_service.create_role(name="RULES1 Strojvedoucí")
        self.role_b = responsibility_role_service.create_role(name="RULES1 Jeřábník")
        self.person = person_service.create_person(first_name="Rules", last_name="One")
        self.operation = settings_service.save_workplace(
            name="RULES1 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="RULES1 pracoviště",
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

    def test_single_role(self) -> None:
        self._seed(
            description="Používej výstražnou vestu",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id)],
            event_name="RoleA",
        )
        self._seed(
            description="Používej helmu",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_b.id)],
            event_name="RoleB",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            role_ids=[self.role_a.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual([rule.text for rule in rules], ["Používej výstražnou vestu."])

    def test_multiple_roles(self) -> None:
        self._seed(
            description="Používej vestu",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id)],
            event_name="MultiRoleA",
        )
        self._seed(
            description="Používej helmu",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_b.id)],
            event_name="MultiRoleB",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            role_ids=[self.role_a.id, self.role_b.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        texts = {rule.text for rule in rules}
        self.assertEqual(texts, {"Používej vestu.", "Používej helmu."})

    def test_single_group(self) -> None:
        self._seed(
            description="Používej brýle",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id)],
            event_name="GroupA",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual([rule.text for rule in rules], ["Používej brýle."])

    def test_multiple_groups(self) -> None:
        self._seed(
            description="Pravidlo A",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id)],
            event_name="GroupsA",
        )
        self._seed(
            description="Pravidlo B",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_b.id)],
            event_name="GroupsB",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_ids=[self.group_a.id, self.group_b.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual({rule.text for rule in rules}, {"Pravidlo A.", "Pravidlo B."})

    def test_role_and_group_combination(self) -> None:
        self._seed(
            description="Pravidlo role",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id)],
            event_name="ComboRole",
        )
        self._seed(
            description="Pravidlo skupina",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id)],
            event_name="ComboGroup",
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

    def test_same_measure_for_multiple_targets_once(self) -> None:
        measure = self._seed(
            description="Společné pravidlo",
            target_refs=[
                ExposedTargetRef(SOURCE_TYPE_ROLE, self.role_a.id),
                ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id),
            ],
            event_name="Shared",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            role_ids=[self.role_a.id],
            endangered_group_ids=[self.group_a.id],
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].measure_id, measure.id)
        self.assertEqual(rules[0].text, "Společné pravidlo.")

    def test_inactive_targets_hidden_in_dialog(self) -> None:
        responsibility_role_service.deactivate(self.role_b.id)
        exposed_group_service.deactivate(self.group_b.id)

        dialog = PravidlaBezpecnePraceDialog()
        role_ids = [
            int(dialog.roles_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(dialog.roles_list.count())
        ]
        group_ids = [
            int(dialog.groups_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(dialog.groups_list.count())
        ]
        self.assertIn(self.role_a.id, role_ids)
        self.assertNotIn(self.role_b.id, role_ids)
        self.assertIn(self.group_a.id, group_ids)
        self.assertNotIn(self.group_b.id, group_ids)

    def test_dialog_requires_at_least_one_target(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.operation.setCurrentIndex(dialog.operation.findData(self.operation.id))
        with patch(
            "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.QMessageBox.warning"
        ) as warn:
            dialog._generate()
        self.assertIn(
            "alespoň jednu profesi, roli nebo ohroženou skupinu",
            warn.call_args.args[2],
        )

    def test_legacy_single_group_unchanged(self) -> None:
        self._seed(
            description="Legacy skupina",
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group_a.id)],
            event_name="Legacy",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual([rule.text for rule in rules], ["Legacy skupina."])


if __name__ == "__main__":
    unittest.main()
