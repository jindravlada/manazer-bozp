"""RISK-AI-12: AI oponentura – revize Zásad a Navazujících opatření."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-12-"))
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
        AI_MEASURE_REC_EDIT_EXISTING,
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_NEW_REQUIRED,
        AI_MEASURE_REC_NO_CHANGE,
        AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_PENDING,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.prompt_builder import (
        MEASURE_REVIEW_ORDER_HEADING,
        build_catalog_source_ai_peer_review_prompt,
    )
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
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
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


class RiskAi12PromptAndSchemaTestCase(unittest.TestCase):
    def test_catalog_prompt_has_measure_review_order(self) -> None:
        prompt = build_catalog_source_ai_peer_review_prompt()
        self.assertIn(MEASURE_REVIEW_ORDER_HEADING, prompt)
        self.assertIn(
            "Nejprve posuď stávající kontrolní otázky pro revizi rizik.",
            prompt,
        )
        self.assertIn("Následně posuď Zásady bezpečné práce.", prompt)
        self.assertIn(
            "Nenavrhuj novou kontrolní otázku, pokud lze stejné ověření pokrýt",
            prompt,
        )
        self.assertIn(
            "Pokud jsou stávající zásady a kontrolní otázky dostatečné",
            prompt,
        )
        self.assertIn("measure_recommendations", prompt)
        self.assertNotIn("Neměň existující položky.", prompt)

    def test_schema_2_0_defines_measure_recommendations(self) -> None:
        schema = AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0
        self.assertIn("measure_recommendations", schema["properties"])
        defs = schema["$defs"]["measure_recommendation"]
        self.assertIn("beze_zmen", defs["properties"]["typ"]["enum"])
        self.assertIn(
            "upravit_navazujici_opatreni",
            defs["properties"]["typ"]["enum"],
        )


class RiskAi12ParseAndImportTestCase(unittest.TestCase):
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

        self.group = _ensure_exposed_group("Obsluha RISK-AI-12")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj RISK-AI-12",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Testovací zdroj pro revizi opatření.",
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
        self.export_dir = Path(tempfile.mkdtemp(prefix="risk-ai-12-export-"))
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.export = self.provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(),
        )
        self.export_id_map = json.loads(self.review.export_id_map_json or "{}")
        self.reference = catalog_source_reference(self.template.id)

    def _export_id_for(self, kind: str, entity_id: int) -> str:
        for export_id, meta in self.export_id_map.items():
            if meta.get("kind") == kind and int(meta.get("id")) == int(entity_id):
                return export_id
        self.fail(f"Export ID pro {kind}/{entity_id} nenalezeno")

    def test_export_contains_zasady_and_navazujici(self) -> None:
        self.assertIn("Zásady bezpečné práce", self.export.data_text)
        self.assertIn("Kontrolní otázky pro revizi rizik", self.export.data_text)
        self.assertIn("Používejte OOPP při manipulaci.", self.export.data_text)
        self.assertIn("Kontrolujte uchycení břemene.", self.export.data_text)
        dumped = json.dumps(self.export.zadani_json, ensure_ascii=False)
        self.assertIn("EXISTING-MEASURE-", dumped)
        self.assertIn("REQUIRED-MEASURE-", dumped)

    def test_parse_measure_recommendations_only(self) -> None:
        existing_export = self._export_id_for("existing_measure", self.existing.id)
        required_export = self._export_id_for("required_measure", self.required.id)
        assessment_export = self._export_id_for("assessment", self.assessment_id)
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "proposal_packages": [],
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-001",
                    "typ": AI_MEASURE_REC_NO_CHANGE,
                    "reasoning": "Stávající opatření pokrývají riziko pádu.",
                },
                {
                    "recommendation_id": "MR-002",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": required_export,
                    "proposed_text": (
                        "Před zdvihem zkontrolujte uchycení břemene a závěsy."
                    ),
                    "reasoning": "Stávající formulace je příliš obecná.",
                },
                {
                    "recommendation_id": "MR-003",
                    "typ": AI_MEASURE_REC_EDIT_EXISTING,
                    "target_export_id": existing_export,
                    "proposed_text": (
                        "Při manipulaci s břemenem používejte ochrannou přilbu "
                        "a bezpečnostní obuv."
                    ),
                    "reasoning": "Doplnění konkrétních OOPP.",
                },
                {
                    "recommendation_id": "MR-004",
                    "typ": AI_MEASURE_REC_NEW_REQUIRED,
                    "target_export_id": assessment_export,
                    "proposed_text": "Nevstupujte pod zavěšené břemeno.",
                    "reasoning": "Chybí zákaz vstupu pod břemeno.",
                },
            ],
        }
        result = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=self.reference,
        )
        self.assertEqual(len(result.packages), 4)
        types = {pkg.package_type for pkg in result.packages}
        self.assertEqual(
            types,
            {
                AI_MEASURE_REC_NO_CHANGE,
                AI_MEASURE_REC_EDIT_REQUIRED,
                AI_MEASURE_REC_EDIT_EXISTING,
                AI_MEASURE_REC_NEW_REQUIRED,
            },
        )

        parsed = ai_peer_review_service.parse_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_identification_number=self.reference,
            require_proposal_packages=True,
        )
        self.assertEqual(len(parsed.packages), 4)

    def test_import_creates_pending_only_then_manual_accept(self) -> None:
        required_export = self._export_id_for("required_measure", self.required.id)
        assessment_export = self._export_id_for("assessment", self.assessment_id)
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-EDIT",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": required_export,
                    "proposed_text": "Před zdvihem ověřte uchycení břemene.",
                    "reasoning": "Upřesnění kontroly.",
                },
                {
                    "recommendation_id": "MR-NEW",
                    "typ": AI_MEASURE_REC_NEW_REQUIRED,
                    "target_export_id": assessment_export,
                    "proposed_text": "Nevstupujte pod zavěšené břemeno.",
                    "reasoning": "Chybějící zákaz.",
                },
            ],
        }
        packages = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=self.reference,
        ).packages

        before_required = [
            m.description
            for m in hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        ]
        ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text=json.dumps(payload, ensure_ascii=False),
            ai_model="test-model",
            accepted=list(packages),
            rejected=[],
        )
        after_required = [
            m.description
            for m in hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        ]
        self.assertEqual(before_required, after_required)

        pending = [
            r
            for r in ai_peer_review_service.get_packages_for_review(self.review.id)
            if r.status == PACKAGE_STATUS_PENDING
        ]
        self.assertEqual(len(pending), 2)

        edit_record = next(r for r in pending if r.package_id == "MR-EDIT")
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=int(edit_record.id),
        )
        updated = hazard_library_template_required_measure_service.get_by_id(
            self.required.id
        )
        assert updated is not None
        self.assertEqual(
            updated.description,
            "Před zdvihem ověřte uchycení břemene.",
        )

        pending_after = [
            r
            for r in ai_peer_review_service.get_packages_for_review(self.review.id)
            if r.status == PACKAGE_STATUS_PENDING
        ]
        new_record = next(r for r in pending_after if r.package_id == "MR-NEW")
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=int(new_record.id),
        )
        required_now = [
            m.description
            for m in hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        ]
        self.assertIn("Nevstupujte pod zavěšené břemeno.", required_now)

    def test_accept_edit_zasady_and_reject_keeps_data(self) -> None:
        existing_export = self._export_id_for("existing_measure", self.existing.id)
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-ZASADY",
                    "typ": AI_MEASURE_REC_EDIT_EXISTING,
                    "target_export_id": existing_export,
                    "proposed_text": "Při manipulaci používejte ochrannou přilbu.",
                    "reasoning": "Konkretizace OOPP.",
                },
                {
                    "recommendation_id": "MR-SKIP",
                    "typ": AI_MEASURE_REC_NEW_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "assessment",
                        self.assessment_id,
                    ),
                    "proposed_text": "Nepotřebné nové opatření.",
                    "reasoning": "Test zamítnutí.",
                },
            ],
        }
        packages = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=self.reference,
        ).packages
        ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text=json.dumps(payload, ensure_ascii=False),
            ai_model="test-model",
            accepted=list(packages),
            rejected=[],
        )
        records = {
            r.package_id: r
            for r in ai_peer_review_service.get_packages_for_review(self.review.id)
        }
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=int(records["MR-ZASADY"].id),
        )
        hazard_catalog_package_incorporate_service.reject_package(
            int(records["MR-SKIP"].id),
        )
        existing = hazard_library_template_existing_measure_service.get_by_id(
            self.existing.id
        )
        assert existing is not None
        self.assertEqual(
            existing.description,
            "Při manipulaci používejte ochrannou přilbu.",
        )
        required = [
            m.description
            for m in hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        ]
        self.assertNotIn("Nepotřebné nové opatření.", required)


if __name__ == "__main__":
    unittest.main()
