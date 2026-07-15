"""HOTFIX R19.1 – průvodce ručním dokončením zapracování AI návrhů."""

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

    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import (
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
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
        CatalogIncorporateResult,
        hazard_catalog_proposal_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )


class HazardCatalogManualCompletionR19_1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

        self.template = hazard_library_template_service.create_template(
            name="Zdroj R19.1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.requirement = legal_requirement_service.create_requirement(
            title="BOZP školení",
            process_code="P-911",
        )
        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="911",
            year=2001,
            title="BOZP školení předpis",
        )
        self.export_dir = Path(tempfile.mkdtemp())
        self.provider = hazard_catalog_source_peer_review_provider
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        ).review

    def _store_pending(self, proposals: list[AiProposal]) -> list[AiUnassignedProposal]:
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

    def test_incorporate_result_lists_manual_decision_proposal_ids(self) -> None:
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
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={},
            pending_proposal_ids=plan.pending_proposal_ids,
        )
        self.assertEqual(result.requires_manual_decision_count, 1)
        self.assertEqual(result.manual_decision_proposal_ids, [stored[0].id])

    def test_list_legal_requirement_candidates_contains_active_process(self) -> None:
        candidates = hazard_catalog_proposal_incorporate_service.list_legal_requirement_candidates()
        self.assertTrue(any(item[0] == self.document.id for item in candidates))

    def test_merge_incorporate_results_aggregates_counts(self) -> None:
        first = CatalogIncorporateResult(
            incorporated_count=1,
            newly_incorporated_count=1,
            used_existing_count=0,
            skipped_count=0,
            requires_manual_decision_count=1,
            manual_decision_proposal_ids=[10],
            merged_count=0,
            new_revision_number=2,
        )
        second = CatalogIncorporateResult(
            incorporated_count=1,
            newly_incorporated_count=1,
            used_existing_count=0,
            skipped_count=0,
            requires_manual_decision_count=0,
            manual_decision_proposal_ids=[],
            merged_count=0,
            new_revision_number=3,
        )
        merged = hazard_catalog_proposal_incorporate_service.merge_incorporate_results(
            first,
            second,
        )
        self.assertEqual(merged.incorporated_count, 2)
        self.assertEqual(merged.newly_incorporated_count, 2)
        self.assertEqual(merged.new_revision_number, 3)


if __name__ == "__main__":
    unittest.main()
