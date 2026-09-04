"""Fáze R20a – AI oponentura jako ucelené návrhové balíky."""

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

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_FORMAT_JSON_1_1,
        AI_PEER_REVIEW_FORMAT_JSON_2_0,
        AI_PEER_REVIEW_FORMAT_TEXT_2_0,
        AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
        AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
        AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_PENDING,
        PACKAGE_STATUS_REJECTED,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.ai_peer_review_service import (
        AiPeerReviewError,
        ai_peer_review_service,
    )
    from core.ai_oponentni.sluzby.proposal_package_parser import (
        parse_ai_proposal_packages_response,
    )
    from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
    from core.ai_oponentni.types import AiPeerReviewExportOptions
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
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        catalog_source_reference,
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _base_package_payload(
    *,
    package_id: str = "PACKAGE-001",
    package_type: str = AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    target_event_export_id: str | None = None,
    event_name: str = "Pád z výšky",
    assessments: list[dict] | None = None,
    legal_links: list[dict] | None = None,
) -> dict:
    if assessments is None:
        assessments = [
            {
                "exposed_group": "Zaměstnanci",
                "severity": RISK_SEVERITY_MODERATE,
                "existing_measures": [{"description": "Zábradlí"}],
                "required_measures": [{"description": "Kontrola zábradlí"}],
            },
        ]
    return {
        "package_id": package_id,
        "package_type": package_type,
        "target_event_export_id": target_event_export_id,
        "event": {
            "name": event_name,
            "description": "Popis události",
        },
        "assessments": assessments,
        "legal_links": legal_links or [{"reference": "Nařízení vlády č. 378/2001 Sb."}],
        "reasoning": "Odborné zdůvodnění balíku.",
    }


def _response_payload(
    source_reference: str,
    packages: list[dict],
) -> dict:
    return {
        "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
        "source_reference": source_reference,
        "proposal_packages": packages,
    }


class AiProposalPackagesR20aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Testovací zdroj",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.source_reference = catalog_source_reference(self.template.id)
        self.provider = hazard_catalog_source_peer_review_provider

    def test_valid_new_event_package_json(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [_base_package_payload()],
        )
        result = parse_ai_proposal_packages_response(
            json.dumps(payload),
            expected_source_reference=self.source_reference,
        )
        self.assertEqual(len(result.packages), 1)
        package = result.packages[0]
        self.assertEqual(package.package_type, AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT)
        self.assertEqual(package.event_name, "Pád z výšky")
        self.assertEqual(package.assessment_count, 1)
        self.assertEqual(package.existing_measure_count, 1)
        self.assertEqual(package.required_measure_count, 1)
        self.assertEqual(package.legal_link_count, 1)

    def test_extend_existing_event_package(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(
                    package_id="PACKAGE-002",
                    package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
                    target_event_export_id="EVENT-001",
                    event_name="",
                ),
            ],
        )
        payload["proposal_packages"][0]["event"] = None
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        package = result.packages[0]
        self.assertEqual(package.package_type, AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT)
        self.assertEqual(package.target_event_export_id, "EVENT-001")

    def test_multiple_assessments_in_one_package(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(
                    assessments=[
                        {
                            "exposed_group": "Zaměstnanci",
                            "severity": RISK_SEVERITY_MODERATE,
                        },
                        {
                            "exposed_group": "Dodavatelé",
                            "severity": "minor",
                        },
                    ],
                ),
            ],
        )
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(result.packages[0].assessment_count, 2)

    def test_measures_bound_to_assessment(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [_base_package_payload()],
        )
        package = parse_ai_proposal_packages_response(json.dumps(payload)).packages[0]
        assessment = package.assessments[0]
        self.assertEqual(len(assessment.existing_measures), 1)
        self.assertEqual(len(assessment.required_measures), 1)
        self.assertEqual(assessment.existing_measures[0].description, "Zábradlí")

    def test_reject_package_without_assessment(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [_base_package_payload(assessments=[])],
        )
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(len(result.packages), 0)
        self.assertTrue(result.skip_reasons)

    def test_reject_assessment_without_exposed_group(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(
                    assessments=[
                        {
                            "exposed_group": "",
                            "severity": RISK_SEVERITY_MODERATE,
                        },
                    ],
                ),
            ],
        )
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(len(result.packages), 0)

    def test_reject_invalid_severity(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(
                    assessments=[
                        {
                            "exposed_group": "Zaměstnanci",
                            "severity": "extrémní",
                        },
                    ],
                ),
            ],
        )
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(len(result.packages), 0)

    def test_preserve_legal_links(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(
                    legal_links=[
                        {"reference": "Zákoník práce", "reasoning": "Obecná povinnost"},
                    ],
                ),
            ],
        )
        package = parse_ai_proposal_packages_response(json.dumps(payload)).packages[0]
        self.assertEqual(package.legal_links[0].reference, "Zákoník práce")
        self.assertEqual(package.legal_links[0].reasoning, "Obecná povinnost")

    def test_load_text_format_2_0(self) -> None:
        text = """
BALÍK: PACKAGE-010
TYP: Nová událost

UDÁLOST:
Výbuch

POSOUZENÍ:
Ohrožená skupina: Zaměstnanci
Závažnost: serious

EXISTUJÍCÍ OPATŘENÍ:
- Detekce plynu

POTŘEBNÁ OPATŘENÍ:
- Evakuační plán

PRÁVNÍ VAZBY:
- Nařízení vlády č. 378/2001 Sb.

ZDŮVODNĚNÍ:
Chybí kompletní scénář.
"""
        result = parse_ai_proposal_packages_response(text)
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_TEXT_2_0)
        self.assertEqual(len(result.packages), 1)
        package = result.packages[0]
        self.assertEqual(package.event_name, "Výbuch")
        self.assertEqual(package.required_measure_count, 1)

    def test_historical_schema_1_1_still_parses(self) -> None:
        payload = {
            "schema_version": "1.1",
            "source_identification_number": "ID-001",
            "generated_at": "2026-01-01T10:00:00",
            "proposals": [
                {
                    "proposal_id": "P-001",
                    "area": "Nežádoucí událost",
                    "name": "Historický návrh",
                    "parent_export_id": "SOURCE-001",
                    "reasoning": "Test",
                },
            ],
        }
        result = parse_ai_peer_review_response(json.dumps(payload))
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_JSON_1_1)
        self.assertEqual(len(result.proposals), 1)
        self.assertEqual(len(result.packages), 0)

    def test_catalog_export_uses_schema_2_0(self) -> None:
        export_dir = Path(tempfile.mkdtemp())
        target = export_dir / "export.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        self.assertTrue(target.is_file())
        payload = json.loads(target.read_text(encoding="utf-8"))
        schema = payload["response_schema"]
        self.assertEqual(schema["schema_version"], AI_PEER_REVIEW_SCHEMA_VERSION_2_0)
        self.assertEqual(payload["schema_version"], AI_PEER_REVIEW_SCHEMA_VERSION_2_0)
        self.assertNotIn("request_mode", payload)
        self.assertIn("proposal_package", schema["$defs"])
        self.assertIsNotNone(export_result.review.id)

    def test_catalog_rejects_schema_1_1_import(self) -> None:
        payload = {
            "schema_version": "1.1",
            "source_identification_number": self.source_reference,
            "generated_at": "2026-01-01T10:00:00",
            "proposals": [
                {
                    "proposal_id": "P-001",
                    "area": "Potřebné opatření",
                    "name": "Samostatné opatření",
                    "parent_export_id": "ASSESSMENT-001",
                    "reasoning": "Neplatné pro katalog",
                },
            ],
        }
        with self.assertRaises(AiPeerReviewError):
            ai_peer_review_service.parse_response(
                json.dumps(payload),
                expected_source_identification_number=self.source_reference,
                require_proposal_packages=True,
            )

    def test_finalize_package_import_stores_packages(self) -> None:
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        payload = _response_payload(self.source_reference, [_base_package_payload()])
        parse_result = ai_peer_review_service.parse_response(
            json.dumps(payload),
            expected_source_identification_number=self.source_reference,
            require_proposal_packages=True,
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text=json.dumps(payload),
            ai_model="Test AI",
            accepted=parse_result.packages,
            rejected=[],
        )
        stored = ai_peer_review_service.get_packages_for_review(updated.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].status, PACKAGE_STATUS_PENDING)
        package = ai_peer_review_service.package_repository.package_from_record(stored[0])
        self.assertEqual(package.package_id, "PACKAGE-001")

    def test_rejected_packages_stored_with_status(self) -> None:
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(package_id="PACKAGE-ACCEPT"),
                _base_package_payload(package_id="PACKAGE-REJECT"),
            ],
        )
        parse_result = ai_peer_review_service.parse_response(
            json.dumps(payload),
            expected_source_identification_number=self.source_reference,
            require_proposal_packages=True,
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text=json.dumps(payload),
            ai_model="Test AI",
            accepted=[parse_result.packages[0]],
            rejected=[parse_result.packages[1]],
            loaded_packages_count=2,
        )
        stored = ai_peer_review_service.get_packages_for_review(updated.id)
        statuses = {record.package_id: record.status for record in stored}
        self.assertEqual(statuses["PACKAGE-ACCEPT"], PACKAGE_STATUS_PENDING)
        self.assertEqual(statuses["PACKAGE-REJECT"], PACKAGE_STATUS_REJECTED)
        self.assertEqual(updated.loaded_proposals_count, 2)
        self.assertEqual(updated.pending_proposals_count, 1)
        self.assertEqual(updated.rejected_count, 1)

    def test_provider_uses_proposal_packages_flag(self) -> None:
        self.assertTrue(
            ai_peer_review_service.provider_uses_proposal_packages(self.provider),
        )

    def test_invalid_package_not_partially_imported(self) -> None:
        payload = _response_payload(
            self.source_reference,
            [
                _base_package_payload(package_id="PACKAGE-OK"),
                _base_package_payload(package_id="PACKAGE-BAD", assessments=[]),
            ],
        )
        result = parse_ai_proposal_packages_response(json.dumps(payload))
        self.assertEqual(len(result.packages), 1)
        self.assertEqual(result.packages[0].package_id, "PACKAGE-OK")
        self.assertEqual(len(result.skip_reasons), 1)

    def test_json_2_0_via_unified_parser(self) -> None:
        payload = _response_payload(self.source_reference, [_base_package_payload()])
        result = parse_ai_peer_review_response(
            json.dumps(payload),
            expected_source_identification_number=self.source_reference,
            require_proposal_packages=True,
        )
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_JSON_2_0)
        self.assertEqual(len(result.packages), 1)

    def test_catalog_prompt_requires_packages(self) -> None:
        from core.ai_oponentni.sluzby.prompt_builder import (
            build_catalog_source_ai_peer_review_prompt,
        )

        prompt = build_catalog_source_ai_peer_review_prompt()
        self.assertIn("izolovaná opatření", prompt.casefold())
        self.assertIn("BALÍK:", prompt)
        self.assertIn("schema 2.0", prompt.casefold())
