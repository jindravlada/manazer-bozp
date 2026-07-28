"""RISK-AI-14: doporučení beze_zmen nezobrazovat ve frontě ke zpracování."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-14-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import (
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_NO_CHANGE,
        AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE,
        AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_PENDING,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import AiProposalPackage
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.proposal_package_parser import (
        parse_ai_proposal_packages_response,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.database.session import get_session
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
        HazardLibraryTemplateAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.catalog_editor_session import (
        SESSION_PACKAGE_PENDING,
        CatalogEditorSession,
        CatalogSessionPackage,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        HazardCatalogPackageIncorporateError,
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        catalog_source_reference,
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )


def _ensure_exposed_group(name: str):
    for group in exposed_group_service.get_all(include_inactive=False):
        if group.name == name:
            return group
    return exposed_group_service.create_group(name=name)


class RiskAi14NoChangeQueueTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = _ensure_exposed_group("Obsluha RISK-AI-14")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj RISK-AI-14",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Testovací zdroj pro RISK-AI-14.",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
            description="Nežádoucí událost pro test.",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Stávající opatření k ověření.",
        )
        self.required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=int(assessment.id),
            description="Kontrolujte uchycení břemene.",
        )

        self.provider = hazard_catalog_source_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp(prefix="risk-ai-14-export-"))
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.export_id_map = json.loads(self.review.export_id_map_json or "{}")
        self.reference = catalog_source_reference(self.template.id)
        self.required_export = self._export_id_for("required_measure", self.required.id)

    def _export_id_for(self, kind: str, entity_id: int) -> str:
        for export_id, meta in self.export_id_map.items():
            if meta.get("kind") == kind and int(meta.get("id")) == int(entity_id):
                return export_id
        self.fail(f"Export ID pro {kind}/{entity_id} nenalezeno")

    def _payload(self, recommendations: list[dict]) -> str:
        return json.dumps(
            {
                "schema_version": "2.0",
                "source_reference": self.reference,
                "proposal_packages": [],
                "measure_recommendations": recommendations,
            },
            ensure_ascii=False,
        )

    def test_only_no_change_keeps_queue_empty(self) -> None:
        payload = self._payload(
            [
                {
                    "recommendation_id": "MR-NC",
                    "typ": AI_MEASURE_REC_NO_CHANGE,
                    "reasoning": "Stávající opatření stačí.",
                }
            ]
        )
        packages = parse_ai_proposal_packages_response(
            payload,
            expected_source_reference=self.reference,
        ).packages
        self.assertEqual(len(packages), 1)
        self.assertFalse(packages[0].requires_user_decision)

        session = CatalogEditorSession.load(self.template.id)
        result = session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=payload,
            ai_model="test",
        )
        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.no_change_count, 1)
        self.assertEqual(session.list_pending_packages(self.review.id), [])
        pending, rejected, staged = session.count_packages_by_status(self.review.id)
        self.assertEqual((pending, rejected, staged), (0, 0, 0))

        updated = session.sync_review_stats(self.review.id, loaded_packages_count=0)
        assert updated is not None
        self.assertEqual(updated.loaded_proposals_count, 0)
        self.assertEqual(updated.pending_proposals_count, 0)
        self.assertEqual(updated.rejected_count, 0)
        self.assertEqual(
            AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE,
            "AI nenašla žádné návrhy změn.",
        )

    def test_combined_json_queues_only_actionable(self) -> None:
        payload = self._payload(
            [
                {
                    "recommendation_id": "MR-NC",
                    "typ": AI_MEASURE_REC_NO_CHANGE,
                    "reasoning": "Část opatření je v pořádku.",
                },
                {
                    "recommendation_id": "MR-EDIT",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self.required_export,
                    "proposed_text": "Před zdvihem ověřte uchycení břemene.",
                    "reasoning": "Upřesnění kontroly.",
                },
            ]
        )
        packages = parse_ai_proposal_packages_response(
            payload,
            expected_source_reference=self.reference,
        ).packages
        session = CatalogEditorSession.load(self.template.id)
        result = session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=payload,
            ai_model="test",
        )
        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.no_change_count, 1)
        pending = session.list_pending_packages(self.review.id)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].package.package_type, AI_MEASURE_REC_EDIT_REQUIRED)

        updated = session.sync_review_stats(
            self.review.id,
            loaded_packages_count=result.loaded_count,
        )
        assert updated is not None
        self.assertEqual(updated.loaded_proposals_count, 1)
        self.assertEqual(updated.pending_proposals_count, 1)
        self.assertEqual(updated.rejected_count, 0)

    def test_finalize_path_skips_no_change(self) -> None:
        payload = self._payload(
            [
                {
                    "recommendation_id": "MR-NC",
                    "typ": AI_MEASURE_REC_NO_CHANGE,
                    "reasoning": "Bez změn.",
                },
                {
                    "recommendation_id": "MR-EDIT",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self.required_export,
                    "proposed_text": "Před zdvihem ověřte uchycení břemene.",
                    "reasoning": "Upřesnění.",
                },
            ]
        )
        packages = parse_ai_proposal_packages_response(
            payload,
            expected_source_reference=self.reference,
        ).packages
        accepted, duplicates = ai_peer_review_service.filter_new_packages_for_review(
            review_id=self.review.id,
            packages=list(packages),
        )
        self.assertEqual(duplicates, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].package_type, AI_MEASURE_REC_EDIT_REQUIRED)

        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text=payload,
            ai_model="test",
            accepted=accepted,
            rejected=[],
            loaded_packages_count=len(accepted),
        )
        self.assertEqual(updated.loaded_proposals_count, 1)
        self.assertEqual(updated.pending_proposals_count, 1)
        stored = ai_peer_review_service.get_packages_for_review(self.review.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].package_type, AI_MEASURE_REC_EDIT_REQUIRED)

    def test_cannot_accept_or_reject_no_change(self) -> None:
        no_change = AiProposalPackage(
            package_id="MR-NC",
            package_type=AI_MEASURE_REC_NO_CHANGE,
            target_event_export_id=None,
            event=None,
            assessments=(),
            reasoning="Bez změn.",
        )
        session = CatalogEditorSession.load(self.template.id)
        local_id = session._alloc_temp_id()
        session.packages[local_id] = CatalogSessionPackage(
            local_id=local_id,
            review_id=self.review.id,
            source_type=self.provider.source_type,
            source_id=self.template.id,
            package=no_change,
            session_status=SESSION_PACKAGE_PENDING,
            db_id=None,
            payload_dirty=True,
            is_new=True,
            original_status=PACKAGE_STATUS_PENDING,
        )
        self.assertEqual(session.list_pending_packages(self.review.id), [])
        self.assertFalse(session.reject_package(local_id))
        with self.assertRaises(ValueError):
            session.stage_for_incorporation(local_id)

        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service._incorporate_measure_recommendation_working_copy(
                None,
                editor_session=None,
                package_record_id=0,
                package=no_change,
                export_id_map={},
            )
        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service._apply_measure_recommendation_to_session(
                None,
                package=no_change,
                export_id_map={},
                template_id=self.template.id,
            )
        self.assertIn("Beze změn", AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE)


if __name__ == "__main__":
    unittest.main()
