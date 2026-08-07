"""Fáze R16 – číselník ohrožených skupin osob."""

from __future__ import annotations

import importlib
import json
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

    from core.ai_oponentni.types import AiProposal
    from moduly.nastaveni.modely.exposed_group import ExposedGroup
    from moduly.nastaveni.sluzby.exposed_group_service import (
        ExposedGroupError,
        ExposedGroupMatchKind,
        exposed_group_service,
    )
    from moduly.rizeni_rizik.constants import RISK_SEVERITY_MODERATE
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        HazardRiskAssessmentError,
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.exposed_group_proposal_resolution_dialog import (
        is_exposed_group_proposal,
    )
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group

class ExposedGroupCatalogR16TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete, text

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(ExposedGroup))
            session.commit()

        from core.database.database_initializer import _seed_exposed_groups

        _seed_exposed_groups()

        operation = settings_service.save_workplace(
            name="Provoz R16",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R16",
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
        self.provider = hazard_identification_peer_review_provider

    def test_default_catalog_is_seeded(self) -> None:
        groups = exposed_group_service.get_all(include_inactive=False)
        names = {group.name for group in groups}
        self.assertIn("Zaměstnanci daného pracoviště", names)
        self.assertIn("Dodavatelé", names)
        self.assertEqual(len(groups), 2)

    def test_create_new_group(self) -> None:
        group = exposed_group_service.create_group(name="Speciální skupina", note="Test")
        self.assertEqual(group.name, "Speciální skupina")
        self.assertEqual(group.note, "Test")
        self.assertTrue(group.active)

    def test_reject_empty_name(self) -> None:
        with self.assertRaises(ExposedGroupError):
            exposed_group_service.create_group(name="   ")

    def test_reject_active_duplicate_name(self) -> None:
        exposed_group_service.create_group(name="Technik")
        with self.assertRaises(ExposedGroupError):
            exposed_group_service.create_group(name="  technik ")

    def test_activate_and_deactivate(self) -> None:
        group = exposed_group_service.create_group(name="Dočasná skupina", active=True)
        self.assertTrue(exposed_group_service.deactivate(group.id))
        reloaded = exposed_group_service.get_by_id(group.id)
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertFalse(reloaded.active)
        self.assertTrue(exposed_group_service.activate(group.id))

    def test_migration_maps_existing_catalog_item(self) -> None:
        maintenance = ensure_exposed_group("Údržba")
        assessment = HazardRiskAssessment(
            hazard_event_id=self.event.id,
            exposed_group="  údržba ",
            exposed_group_id=None,
            severity=RISK_SEVERITY_MODERATE,
        )
        from moduly.rizeni_rizik.repository.hazard_risk_assessment_repository import (
            HazardRiskAssessmentRepository,
        )

        saved = HazardRiskAssessmentRepository().add(assessment)
        migrated = exposed_group_service.find_or_create_for_migration(saved.exposed_group)
        saved.exposed_group_id = migrated.id
        HazardRiskAssessmentRepository().update(saved)
        self.assertEqual(migrated.id, maintenance.id)

    def test_migration_creates_new_catalog_item(self) -> None:
        created = exposed_group_service.find_or_create_for_migration("Zaměstnanec údržby")
        self.assertEqual(created.name, "Zaměstnanec údržby")
        self.assertTrue(created.active)

    def test_existing_assessments_keep_group_after_migration(self) -> None:
        group = ensure_exposed_group("Posunovač")
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        reloaded = hazard_risk_assessment_service.get_by_id(assessment.id)
        assert reloaded is not None
        self.assertEqual(reloaded.exposed_group_id, group.id)
        self.assertEqual(
            hazard_risk_assessment_service.get_exposed_group_display_name(reloaded),
            "Posunovač",
        )

    def test_dialog_lists_only_active_groups(self) -> None:
        active = exposed_group_service.create_group(name="Aktivní test")
        inactive = exposed_group_service.create_group(name="Neaktivní test", active=True)
        exposed_group_service.deactivate(inactive.id)
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_hazard_event_id=self.event.id,
        )
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import SOURCE_TYPE_HAZARD_GROUP

        selector = dialog.exposed_groups.selector
        selector.reload()
        combo_ids = {
            data[1]
            for index in range(selector.count())
            if isinstance((data := selector.itemData(index)), tuple)
            and len(data) == 2
            and data[0] == SOURCE_TYPE_HAZARD_GROUP
        }
        self.assertIn(active.id, combo_ids)
        self.assertNotIn(inactive.id, combo_ids)

    def test_dialog_prefills_group_on_edit(self) -> None:
        group = ensure_exposed_group("Obsluha zařízení")
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        dialog = HazardRiskAssessmentDialog(
            None,
            hazard_identification_id=self.identification.id,
            assessment=assessment,
        )
        self.assertEqual(dialog.exposed_groups.selected_group_ids(), [group.id])

    def test_duplicate_assessment_by_exposed_group_id(self) -> None:
        group = ensure_exposed_group("Posunovač")
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_id=group.id,
                severity=RISK_SEVERITY_MODERATE,
            )

    def test_table_shows_group_name(self) -> None:
        group = ensure_exposed_group("Chodci")
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        rows = hazard_risk_assessment_service.get_for_identification(self.identification.id)
        self.assertEqual(rows[0].exposed_group_name, "Chodci")

    def test_ai_export_uses_catalog_name(self) -> None:
        group = ensure_exposed_group("Jeřábník")
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        content = self.provider.build_export_content(
            self.identification.id,
            options=__import__(
                "core.ai_oponentni.types",
                fromlist=["AiPeerReviewExportOptions"],
            ).AiPeerReviewExportOptions(),
        )
        assessment_node = content.batches[0].zadani_json["workplace_analysis"][0]["events"][0][
            "assessments"
        ][0]
        self.assertEqual(assessment_node["exposed_group"], "Jeřábník")

    def test_ai_proposal_active_match(self) -> None:
        group = ensure_exposed_group("Údržba")
        result = exposed_group_service.classify_name("údržba")
        self.assertEqual(result.kind, ExposedGroupMatchKind.ACTIVE)
        self.assertEqual(result.groups[0].id, group.id)

    def test_ai_proposal_inactive_match(self) -> None:
        group = ensure_exposed_group("Dočasná")
        exposed_group_service.deactivate(group.id)
        result = exposed_group_service.classify_name("Dočasná")
        self.assertEqual(result.kind, ExposedGroupMatchKind.INACTIVE)

    def test_ai_proposal_no_match(self) -> None:
        result = exposed_group_service.classify_name("Neznámá skupina XYZ")
        self.assertEqual(result.kind, ExposedGroupMatchKind.NONE)

    def test_apply_without_resolved_id_does_not_create_group(self) -> None:
        before = len(exposed_group_service.get_all(include_inactive=True))
        proposal = AiProposal(
            area="Ohrožená skupina",
            name="Nová skupina bez potvrzení",
            reasoning="Test",
            parent_export_id="EVENT-001",
        )
        result = self.provider.apply_proposals(
            self.identification.id,
            [proposal],
            review_id=1,
            export_id_map={"EVENT-001": {"kind": "event", "id": self.event.id}},
        )
        self.assertEqual(result.applied_count, 0)
        self.assertEqual(result.unassigned_count, 1)
        after = len(exposed_group_service.get_all(include_inactive=True))
        self.assertEqual(before, after)

    def test_is_exposed_group_proposal(self) -> None:
        self.assertTrue(
            is_exposed_group_proposal(
                AiProposal(area="Ohrožená skupina", name="X", reasoning="")
            )
        )
        self.assertFalse(
            is_exposed_group_proposal(
                AiProposal(area="Nežádoucí událost", name="X", reasoning="")
            )
        )


if __name__ == "__main__":
    unittest.main()
