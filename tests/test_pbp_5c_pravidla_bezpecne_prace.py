"""PBP-5c: profese a jejich ohrožené skupiny."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-5c-"))
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
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
        PBP_EDITION_NO_ENDANGERED_GROUP,
        PravidlaBezpecnePraceEdition,
        PravidlaBezpecnePraceEditionRule,
    )
    from moduly.rizeni_rizik.modely.profession import Profession
    from moduly.rizeni_rizik.modely.profession_exposed_group import ProfessionExposedGroup
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
        pravidla_bezpecne_prace_edition_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.sluzby.profession_service import profession_service
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PravidlaBezpecnePracePhasePbp5cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(PravidlaBezpecnePraceEditionRule))
            session.execute(delete(PravidlaBezpecnePraceEdition))
            session.execute(delete(ProfessionExposedGroup))
            session.execute(delete(Profession))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group_a = ensure_exposed_group("PBP5c zaměstnanci")
        self.group_b = ensure_exposed_group("PBP5c obsluha")
        self.group_c = ensure_exposed_group("PBP5c dodavatelé")
        for group in (self.group_a, self.group_b, self.group_c):
            if not group.active:
                exposed_group_service.activate(group.id)
                group.active = True
        self.person = person_service.create_person(first_name="PBP5c", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP5c provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP5c pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.profession = profession_service.create_profession(
            name="Vlakvedoucí",
            note="PBP5c",
            exposed_group_ids=[self.group_a.id, self.group_b.id],
        )

    def _seed(
        self,
        *,
        description: str,
        severity: str,
        group_id: int,
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
            exposed_group_id=group_id,
            severity=severity,
        )
        return hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_profession_with_two_groups_unifies_rules(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="A1",
        )
        self._seed(
            description="Používej brýle",
            severity=RISK_SEVERITY_MINOR,
            group_id=self.group_b.id,
            event_name="B1",
        )

        rules = pravidla_bezpecne_prace_service.generate(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        texts = {rule.text for rule in rules}
        self.assertEqual(len(rules), 2)
        self.assertIn("Používej helmu.", texts)
        self.assertIn("Používej brýle.", texts)

    def test_dedupe_between_groups_keeps_highest_severity(self) -> None:
        measure_a = self._seed(
            description="Používej ochranné rukavice",
            severity=RISK_SEVERITY_MINOR,
            group_id=self.group_a.id,
            event_name="DupA",
        )
        measure_b = self._seed(
            description="Používej ochranné rukavice",
            severity=RISK_SEVERITY_CRITICAL,
            group_id=self.group_b.id,
            event_name="DupB",
        )

        rules = pravidla_bezpecne_prace_service.generate(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        self.assertEqual(rule.text, "Používej ochranné rukavice.")
        self.assertEqual(rule.severity, RISK_SEVERITY_CRITICAL)
        self.assertEqual(
            {source.measure_id for source in rule.sources},
            {measure_a.id, measure_b.id},
        )

    def test_direct_group_selection_still_works(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="DirectA",
        )
        self._seed(
            description="Používej brýle",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_b.id,
            event_name="DirectB",
        )

        only_a = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(len(only_a), 1)
        self.assertEqual(only_a[0].text, "Používej helmu.")

    def test_profession_and_group_histories_are_separate(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="Hist",
        )
        rules_group = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rules_prof = pravidla_bezpecne_prace_service.generate(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        group_edition = pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=rules_group,
            issued_at=datetime.now() - timedelta(hours=2),
        )
        prof_edition = pravidla_bezpecne_prace_edition_service.record_edition(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=rules_prof,
            issued_at=datetime.now() - timedelta(hours=1),
        )

        self.assertIsNone(group_edition.profession_id)
        self.assertEqual(group_edition.endangered_group_id, self.group_a.id)
        self.assertEqual(prof_edition.profession_id, self.profession.id)
        self.assertEqual(
            prof_edition.endangered_group_id,
            PBP_EDITION_NO_ENDANGERED_GROUP,
        )

        latest_group = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        latest_prof = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(latest_group.id, group_edition.id)
        self.assertEqual(latest_prof.id, prof_edition.id)

    def test_profession_group_change_appears_in_comparison(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="CmpA",
        )
        self._seed(
            description="Používej brýle",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_b.id,
            event_name="CmpB",
        )
        self._seed(
            description="Noste výstražnou vestu",
            severity=RISK_SEVERITY_MINOR,
            group_id=self.group_c.id,
            event_name="CmpC",
        )

        first_rules = pravidla_bezpecne_prace_service.generate(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        pravidla_bezpecne_prace_edition_service.record_edition(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=first_rules,
            issued_at=datetime.now() - timedelta(hours=1),
        )

        profession_service.set_exposed_groups(
            self.profession.id,
            [self.group_a.id, self.group_c.id],
        )
        current_rules = pravidla_bezpecne_prace_service.generate(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=current_rules,
        )
        self.assertTrue(comparison.has_changes)
        new_texts = {rule.text for rule in comparison.new_rules}
        removed_texts = {rule.display_text for rule in comparison.removed_rules}
        self.assertIn("Noste výstražnou vestu.", new_texts)
        self.assertIn("Používej brýle.", removed_texts)
        self.assertEqual(len(comparison.unchanged_rules), 1)
        self.assertEqual(comparison.unchanged_rules[0].text, "Používej helmu.")

    def test_inactive_profession_or_group_not_offered(self) -> None:
        from PySide6.QtCore import Qt

        from moduly.nastaveni.sluzby.responsibility_role_service import (
            responsibility_role_service,
        )

        role = responsibility_role_service.create_role(name="PBP5c role neaktivní")
        responsibility_role_service.deactivate(role.id)

        dialog = PravidlaBezpecnePraceDialog()
        listed_role_ids = [
            int(dialog.roles_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(dialog.roles_list.count())
        ]
        self.assertNotIn(role.id, listed_role_ids)
        self.assertEqual(dialog.selected_role_ids(), [])

        exposed_group_service.deactivate(self.group_b.id)
        dialog._reload_groups()
        listed_group_ids = [
            int(dialog.groups_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(dialog.groups_list.count())
        ]
        self.assertNotIn(self.group_b.id, listed_group_ids)
        self.assertIn(self.group_a.id, listed_group_ids)

        profession_service.deactivate(self.profession.id)
        active_ids = {item.id for item in profession_service.get_active_all()}
        self.assertNotIn(self.profession.id, active_ids)

    def test_odt_header_uses_profession_label(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="Hdr",
        )
        path = pravidla_bezpecne_prace_service.export_document(
            profession_id=self.profession.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)
        assert path is not None
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Profese", content)
        self.assertIn("Vlakvedoucí", content)
        self.assertNotIn("PBP5c zaměstnanci", content)
        self.assertNotIn("PBP5c obsluha", content)

    def test_odt_header_uses_group_label(self) -> None:
        self._seed(
            description="Používej helmu",
            severity=RISK_SEVERITY_MODERATE,
            group_id=self.group_a.id,
            event_name="HdrG",
        )
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)
        assert path is not None
        with zipfile.ZipFile(path) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Ohrožená skupina", content)
        self.assertIn("PBP5c zaměstnanci", content)


if __name__ == "__main__":
    unittest.main()
