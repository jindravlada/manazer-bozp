"""HOTFIX R19.2.1 – dokončení workflow po ručním rozhodnutí."""

from __future__ import annotations

import importlib
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

    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import (
        PROPOSAL_STATUS_INCORPORATED,
        PROPOSAL_STATUS_PENDING,
        AiUnassignedProposal,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions, AiProposal
    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
        hazard_catalog_proposal_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogManualDecisionCompletionR19_2_1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj R19.2.1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="912",
            year=2001,
            title="BOZP školení předpis",
        )
        self.requirement = legal_requirement_service.create_requirement(
            title="BOZP školení",
            process_code=f"P-{self.template.id:03d}",
            legal_document_id=self.document.id,
        )
        self.provider = hazard_catalog_source_peer_review_provider
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export.zip",
            options=AiPeerReviewExportOptions(),
        ).review

    def _store_pending(self, proposals: list[AiProposal]):
        ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=proposals,
            rejected=[],
            loaded_proposals_count=len(proposals),
        )
        return [
            item
            for item in ai_peer_review_service.get_unassigned_for_review(self.review.id)
            if item.status == PROPOSAL_STATUS_PENDING
        ]

    def _pending_count(self) -> int:
        return len(
            [
                item
                for item in ai_peer_review_service.get_unassigned_for_review(self.review.id)
                if item.status == PROPOSAL_STATUS_PENDING
            ],
        )

    def test_assessment_selection_incorporates_measure_and_creates_master_object(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export2.zip",
            options=AiPeerReviewExportOptions(),
        ).review
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        assessment_export_id = next(
            export_id
            for export_id, payload in export_id_map.items()
            if payload.get("kind") == "assessment"
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Existující opatření",
                    name="Ochranné brýle",
                    parent_export_id="SOURCE-001",
                    reasoning="Opatření bez posouzení",
                ),
            ],
        )
        self.assertEqual(self._pending_count(), 1)

        hazard_catalog_proposal_incorporate_service.assign_proposal_assessment(
            stored[0].id,
            assessment_export_id,
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_single_proposal(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_id=stored[0].id,
        )

        self.assertEqual(result.newly_incorporated_count, 1)
        self.assertEqual(self._pending_count(), 0)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)
        measures = hazard_library_template_existing_measure_service.get_for_assessment(
            assessment.id,
            include_inactive=False,
        )
        self.assertEqual(len(measures), 1)
        self.assertEqual(measures[0].description, "Ochranné brýle")

    def test_legal_requirement_selection_incorporates_link_and_creates_master_object(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Právní vazba",
                    name="Neexistující právní požadavek",
                    parent_export_id="SOURCE-001",
                    reasoning="Bez shody",
                ),
            ],
        )
        self.assertEqual(self._pending_count(), 1)

        hazard_catalog_proposal_incorporate_service.assign_proposal_legal_requirement(
            stored[0].id,
            self.document.id,
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_single_proposal(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_id=stored[0].id,
        )

        self.assertEqual(result.newly_incorporated_count, 1)
        self.assertEqual(self._pending_count(), 0)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)
        links = hazard_library_template_legal_link_service.get_for_template(
            self.template.id,
            include_inactive=False,
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].legal_document_id, self.document.id)


if __name__ == "__main__":
    unittest.main()
