"""Fáze R20c – více ohrožených skupin, bez pole consequence."""

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

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageEvent,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.proposal_package_parser import (
        parse_ai_proposal_packages_response,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
        RISK_SEVERITY_SERIOUS,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        HazardRiskAssessmentError,
        hazard_risk_assessment_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class MultiExposedGroupsR20cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def setUp(self) -> None:
        from sqlalchemy import delete, select

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R20c",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R20c",
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
        self.group_a = ensure_exposed_group("Zaměstnanci")
        self.group_b = ensure_exposed_group("Dodavatelé")

    def _join_rows(self, assessment_id: int) -> list[HazardRiskAssessmentExposedGroup]:
        from sqlalchemy import select

        from core.database.session import get_session

        with get_session() as session:
            return list(
                session.scalars(
                    select(HazardRiskAssessmentExposedGroup)
                    .where(HazardRiskAssessmentExposedGroup.assessment_id == assessment_id)
                    .order_by(HazardRiskAssessmentExposedGroup.sort_order)
                ).all()
            )

    def test_schema_has_join_table_without_consequence(self) -> None:
        assessment_columns = _table_columns("hazard_risk_assessments")
        self.assertNotIn("consequence", assessment_columns)
        join_columns = _table_columns("hazard_risk_assessment_exposed_groups")
        self.assertIn("assessment_id", join_columns)
        self.assertIn("exposed_group_id", join_columns)
        self.assertIn("sort_order", join_columns)

    def test_create_assessment_with_multiple_groups(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_ids=[self.group_a.id, self.group_b.id],
            severity=RISK_SEVERITY_MODERATE,
            note="Poznámka R20c",
            conclusion="Závěr R20c",
        )
        self.assertEqual(
            hazard_risk_assessment_service.get_group_ids(assessment.id),
            [self.group_a.id, self.group_b.id],
        )
        self.assertEqual(
            hazard_risk_assessment_service.get_exposed_group_display_name(assessment),
            "Zaměstnanci, Dodavatelé",
        )
        self.assertEqual(assessment.note, "Poznámka R20c")
        self.assertEqual(assessment.conclusion, "Závěr R20c")

        join_rows = self._join_rows(assessment.id)
        self.assertEqual(len(join_rows), 2)
        self.assertEqual(
            [row.exposed_group_id for row in join_rows],
            [self.group_a.id, self.group_b.id],
        )

    def test_reject_overlapping_active_groups_on_same_event(self) -> None:
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=self.group_a.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        with self.assertRaises(HazardRiskAssessmentError):
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=self.identification.id,
                hazard_event_id=self.event.id,
                exposed_group_ids=[self.group_b.id, self.group_a.id],
                severity=RISK_SEVERITY_SERIOUS,
            )

    def test_update_preserves_note_and_conclusion_without_consequence(self) -> None:
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=self.group_a.id,
            severity=RISK_SEVERITY_MODERATE,
            note="Původní poznámka",
            conclusion="Původní závěr",
        )
        updated = hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_ids=[self.group_a.id, self.group_b.id],
            severity=RISK_SEVERITY_SERIOUS,
            note="Aktualizovaná poznámka",
            conclusion="Aktualizovaný závěr",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.note, "Aktualizovaná poznámka")
        self.assertEqual(updated.conclusion, "Aktualizovaný závěr")
        self.assertEqual(updated.severity, RISK_SEVERITY_SERIOUS)
        self.assertEqual(
            hazard_risk_assessment_service.get_group_ids(updated.id),
            [self.group_a.id, self.group_b.id],
        )

    def test_parse_json_package_with_multiple_exposed_groups(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": "SOURCE-001",
            "proposal_packages": [
                {
                    "package_id": "PKG-MULTI",
                    "package_type": "new_event",
                    "event": {"name": "Výbuch"},
                    "assessments": [
                        {
                            "exposed_groups": ["Zaměstnanci", "Dodavatelé"],
                            "severity": RISK_SEVERITY_MODERATE,
                        },
                    ],
                },
            ],
        }
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(len(result.packages), 1)
        assessment = result.packages[0].assessments[0]
        self.assertEqual(assessment.exposed_groups, ("Zaměstnanci", "Dodavatelé"))
        self.assertEqual(assessment.severity, RISK_SEVERITY_MODERATE)

    def test_parse_text_package_with_multiple_exposed_group_lines(self) -> None:
        text = """
BALÍK: PACKAGE-MULTI-TEXT
TYP: Nová událost

UDÁLOST:
Výbuch

POSOUZENÍ:
Ohrožená skupina: Zaměstnanci
Ohrožená skupina: Dodavatelé
Možný následek: Ignorovaný řádek
Závažnost: moderate

ZDŮVODNĚNÍ:
Test více skupin.
"""
        result = parse_ai_proposal_packages_response(text)
        self.assertEqual(len(result.packages), 1)
        assessment = result.packages[0].assessments[0]
        self.assertEqual(assessment.exposed_groups, ("Zaměstnanci", "Dodavatelé"))

    def test_incorporate_package_with_multiple_groups(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Zdroj R20c",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        provider = hazard_catalog_source_peer_review_provider
        export_result = ai_peer_review_service.export_package(
            provider,
            template.id,
            Path(tempfile.mkdtemp()) / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        package = AiProposalPackage(
            package_id="PACKAGE-MULTI-INC",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Kontakt s rotující částí"),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci",
                    exposed_groups=("Zaměstnanci", "Dodavatelé"),
                    severity=RISK_SEVERITY_MODERATE,
                ),
            ),
            reasoning="Více ohrožených skupin.",
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=provider,
            source_id=template.id,
            review_id=export_result.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        stored = ai_peer_review_service.get_packages_for_review(updated.id)
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=template.id,
            package_record_id=stored[0].id,
        )
        self.assertEqual(result.assessment_count, 1)
        events = hazard_library_template_event_service.get_for_template(
            template.id,
            include_inactive=False,
        )
        assessments = hazard_library_template_assessment_service.get_for_event(
            events[0].id,
            include_inactive=False,
        )
        self.assertEqual(len(assessments), 1)
        group_ids = hazard_library_template_assessment_service.get_group_ids(
            assessments[0].assessment.id,
        )
        self.assertEqual(group_ids, [self.group_a.id, self.group_b.id])


if __name__ == "__main__":
    unittest.main()
