"""RISK-IMPORT-1b: načtení a statistiky oponentury JSON 2.0."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-import-1b-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "AI_oponentura_KZR-0001_2026-07-28_odpoved.json"
)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import (
        AI_MEASURE_REC_EDIT_EXISTING,
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_NEW_REQUIRED,
        AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
        AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_PENDING,
        PACKAGE_STATUS_REJECTED,
        AiProposalPackageRecord,
    )
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
    from moduly.rizeni_rizik.sluzby.catalog_editor_session import CatalogEditorSession
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from sqlalchemy import delete


def _ensure_exposed_group(name: str):
    for group in exposed_group_service.get_all(include_inactive=False):
        if group.name == name:
            return group
    return exposed_group_service.create_group(name=name)


class RiskImport1bTestCase(unittest.TestCase):
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

        self.group = _ensure_exposed_group("Obsluha RISK-IMPORT-1b")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj RISK-IMPORT-1b",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Testovací zdroj pro import JSON 2.0.",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
            description="Nežádoucí událost pro test.",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Stávající opatření k ověření.",
        )
        self.assessment_id = int(assessment.id)
        self.existing = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.assessment_id,
            description="Používejte OOPP při manipulaci.",
        )
        self.required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.assessment_id,
            description="Kontrolujte uchycení břemene.",
        )
        self.provider = hazard_catalog_source_peer_review_provider
        self.reference = catalog_source_reference(self.template.id)
        export_dir = Path(tempfile.mkdtemp(prefix="risk-import-1b-export-"))
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.export_id_map = json.loads(self.review.export_id_map_json or "{}")

    def _export_id_for(self, kind: str, entity_id: int) -> str:
        for export_id, meta in self.export_id_map.items():
            if meta.get("kind") == kind and int(meta.get("id")) == int(entity_id):
                return export_id
        self.fail(f"Export ID pro {kind}/{entity_id} nenalezeno")

    def _fixture_payload(self) -> dict:
        data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        data["source_reference"] = self.reference
        return data

    def test_fixture_counts(self) -> None:
        data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "2.0")
        self.assertEqual(len(data["proposal_packages"]), 7)
        self.assertEqual(len(data["measure_recommendations"]), 10)

    def test_json_2_0_proposal_packages_only(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "proposal_packages": [
                {
                    "package_id": "PKG-ONLY-1",
                    "package_type": AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                    "target_event_export_id": None,
                    "event": {
                        "name": "Nová událost A",
                        "description": "Popis",
                        "note": "",
                    },
                    "assessments": [
                        {
                            "exposed_group": self.group.name,
                            "exposed_groups": [self.group.name],
                            "severity": RISK_SEVERITY_MODERATE,
                            "conclusion": "Závěr",
                            "existing_measures": [],
                            "required_measures": [],
                        }
                    ],
                    "legal_links": [],
                    "reasoning": "Důvod A",
                },
                {
                    "package_id": "PKG-ONLY-2",
                    "package_type": AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
                    "target_event_export_id": self._export_id_for("event", self.event.id),
                    "event": None,
                    "assessments": [
                        {
                            "exposed_group": self.group.name,
                            "exposed_groups": [self.group.name],
                            "severity": RISK_SEVERITY_MODERATE,
                            "conclusion": "Doplnění",
                            "existing_measures": [],
                            "required_measures": [],
                        }
                    ],
                    "legal_links": [],
                    "reasoning": "Důvod B",
                },
            ],
            "measure_recommendations": [],
        }
        text = json.dumps(payload, ensure_ascii=False)
        parsed = ai_peer_review_service.parse_response(
            text,
            expected_source_identification_number=self.reference,
            require_proposal_packages=True,
        )
        self.assertEqual(len(parsed.packages), 2)
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text=text,
            ai_model="test",
            accepted=list(parsed.packages),
            rejected=[],
            loaded_packages_count=len(parsed.packages),
        )
        self.assertEqual(updated.loaded_proposals_count, 2)
        self.assertEqual(updated.pending_proposals_count, 2)
        self.assertEqual(updated.rejected_count, 0)
        pending = [
            r
            for r in ai_peer_review_service.get_packages_for_review(self.review.id)
            if r.status == PACKAGE_STATUS_PENDING
        ]
        self.assertEqual(len(pending), 2)

    def test_json_2_0_measure_recommendations_only(self) -> None:
        required_export = self._export_id_for("required_measure", self.required.id)
        existing_export = self._export_id_for("existing_measure", self.existing.id)
        assessment_export = self._export_id_for("assessment", self.assessment_id)
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "proposal_packages": [],
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-A",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": required_export,
                    "proposed_text": "Upravené navazující.",
                    "reasoning": "Důvod 1",
                },
                {
                    "recommendation_id": "MR-B",
                    "typ": AI_MEASURE_REC_EDIT_EXISTING,
                    "target_export_id": existing_export,
                    "proposed_text": "Upravené zásady.",
                    "reasoning": "Důvod 2",
                },
                {
                    "recommendation_id": "MR-C",
                    "typ": AI_MEASURE_REC_NEW_REQUIRED,
                    "target_export_id": assessment_export,
                    "proposed_text": "Nové navazující.",
                    "reasoning": "Důvod 3",
                },
            ],
        }
        text = json.dumps(payload, ensure_ascii=False)
        parsed = ai_peer_review_service.parse_response(
            text,
            expected_source_identification_number=self.reference,
            require_proposal_packages=True,
        )
        self.assertEqual(len(parsed.packages), 3)
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text=text,
            ai_model="test",
            accepted=list(parsed.packages),
            rejected=[],
            loaded_packages_count=len(parsed.packages),
        )
        self.assertEqual(updated.loaded_proposals_count, 3)
        self.assertEqual(updated.pending_proposals_count, 3)
        self.assertEqual(updated.rejected_count, 0)

    def test_combined_fixture_session_import_stats(self) -> None:
        payload = self._fixture_payload()
        text = json.dumps(payload, ensure_ascii=False)
        parsed = ai_peer_review_service.parse_response(
            text,
            expected_source_identification_number=self.reference,
            require_proposal_packages=True,
        )
        self.assertEqual(len(parsed.packages), 17)
        self.assertEqual(parsed.skipped_count, 0)

        session = CatalogEditorSession.load(self.template.id)
        result = session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(parsed.packages),
            response_text=text,
            ai_model="fixture-model",
        )
        self.assertEqual(result.loaded_count, 17)
        self.assertEqual(result.duplicate_count, 0)
        updated = session.sync_review_stats(
            self.review.id,
            loaded_packages_count=result.loaded_count,
        )
        assert updated is not None
        self.assertEqual(updated.loaded_proposals_count, 17)
        self.assertEqual(updated.pending_proposals_count, 17)
        self.assertEqual(updated.rejected_count, 0)
        self.assertEqual(len(session.list_pending_packages(self.review.id)), 17)

    def test_manual_accept_decreases_pending(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-ACC",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "required_measure",
                        self.required.id,
                    ),
                    "proposed_text": "Převzatý text.",
                    "reasoning": "Důvod převzetí.",
                },
                {
                    "recommendation_id": "MR-KEEP",
                    "typ": AI_MEASURE_REC_EDIT_EXISTING,
                    "target_export_id": self._export_id_for(
                        "existing_measure",
                        self.existing.id,
                    ),
                    "proposed_text": "Zůstane pending.",
                    "reasoning": "Kontrola pending.",
                },
            ],
        }
        text = json.dumps(payload, ensure_ascii=False)
        packages = parse_ai_proposal_packages_response(
            text,
            expected_source_reference=self.reference,
        ).packages
        session = CatalogEditorSession.load(self.template.id)
        session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=text,
            ai_model="test",
        )
        session.sync_review_stats(self.review.id, loaded_packages_count=2)
        pending_item = next(
            item
            for item in session.list_pending_packages(self.review.id)
            if item.package.package_id == "MR-ACC"
        )
        session.stage_for_incorporation(pending_item.local_id)
        updated = session.sync_review_stats(self.review.id)
        assert updated is not None
        self.assertEqual(updated.pending_proposals_count, 1)
        self.assertEqual(updated.accepted_count, 1)
        self.assertEqual(len(session.list_pending_packages(self.review.id)), 1)

    def test_manual_reject_updates_counts(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-REJ",
                    "typ": AI_MEASURE_REC_NEW_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "assessment",
                        self.assessment_id,
                    ),
                    "proposed_text": "Zamítnout.",
                    "reasoning": "Důvod zamítnutí.",
                },
                {
                    "recommendation_id": "MR-STAY",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "required_measure",
                        self.required.id,
                    ),
                    "proposed_text": "Zůstane.",
                    "reasoning": "Kontrola.",
                },
            ],
        }
        text = json.dumps(payload, ensure_ascii=False)
        packages = parse_ai_proposal_packages_response(
            text,
            expected_source_reference=self.reference,
        ).packages
        session = CatalogEditorSession.load(self.template.id)
        session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=text,
            ai_model="test",
        )
        session.sync_review_stats(self.review.id, loaded_packages_count=2)
        reject_item = next(
            item
            for item in session.list_pending_packages(self.review.id)
            if item.package.package_id == "MR-REJ"
        )
        self.assertTrue(session.reject_package(reject_item.local_id))
        updated = session.sync_review_stats(self.review.id)
        assert updated is not None
        self.assertEqual(updated.pending_proposals_count, 1)
        self.assertEqual(updated.rejected_count, 1)

    def test_repeated_import_deduplicates(self) -> None:
        payload = self._fixture_payload()
        text = json.dumps(payload, ensure_ascii=False)
        packages = parse_ai_proposal_packages_response(
            text,
            expected_source_reference=self.reference,
        ).packages
        session = CatalogEditorSession.load(self.template.id)
        first = session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=text,
            ai_model="test",
        )
        self.assertEqual(first.loaded_count, 17)
        second = session.import_packages(
            review_id=self.review.id,
            source_type=self.provider.source_type,
            packages=list(packages),
            response_text=text,
            ai_model="test",
        )
        self.assertEqual(second.loaded_count, 0)
        self.assertEqual(second.duplicate_count, 17)
        self.assertEqual(len(session.list_pending_packages(self.review.id)), 17)

    def test_unknown_measure_type_is_reported(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "proposal_packages": [],
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-BAD",
                    "typ": "neznamy_typ_xyz",
                    "target_export_id": self._export_id_for(
                        "required_measure",
                        self.required.id,
                    ),
                    "proposed_text": "Text",
                    "reasoning": "Důvod",
                },
                {
                    "recommendation_id": "MR-OK",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "required_measure",
                        self.required.id,
                    ),
                    "proposed_text": "Platný text.",
                    "reasoning": "Platný důvod.",
                },
            ],
        }
        result = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=self.reference,
        )
        self.assertEqual(len(result.packages), 1)
        self.assertEqual(result.packages[0].package_id, "MR-OK")
        self.assertEqual(len(result.skip_reasons), 1)
        self.assertIn("neznámý typ doporučení", result.skip_reasons[0])
        self.assertIn("neznamy_typ_xyz", result.skip_reasons[0])


if __name__ == "__main__":
    unittest.main()
