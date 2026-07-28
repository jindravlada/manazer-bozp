"""RISK-AI-16: KeyError legal_requirement_label nesmí padat při AI oponentuře."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-16-"))
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

    from PySide6.QtWidgets import QApplication

    from core.ai_oponentni.constants import (
        AI_MEASURE_REC_EDIT_EXISTING,
        AI_MEASURE_REC_EDIT_REQUIRED,
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
    from core.ai_oponentni.sluzby.proposal_package_detail import (
        format_proposal_package_detail,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.database.session import get_session
    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_ZAKON
    from moduly.pravni_pozadavky.sluzby.legal_document_service import (
        legal_document_service,
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
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
        HazardLibraryTemplateAssessmentExposedGroup,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
        HazardCatalogAiPackageEditDialog,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskAi16LegalLabelKeyErrorTestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Obsluha RISK-AI-16")
        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            number="262",
            year=2006,
            title="Zákoník práce",
            short_title="ZP",
        )
        self.template = hazard_library_template_service.create_template(
            name="Zdroj RISK-AI-16",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_document_id=self.document.id,
            note="Testovací vazba",
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Závěr",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=int(assessment.id),
            description="Zásada OOPP",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=int(assessment.id),
            description="Kontrola uchycení",
        )
        self.provider = hazard_catalog_source_peer_review_provider
        self.reference = catalog_source_reference(self.template.id)

    def test_user_error_hides_raw_keyerror_field_name(self) -> None:
        from core.ai_oponentni.constants import (
            AI_PEER_REVIEW_INTERNAL_DATA_ERROR,
            format_ai_peer_review_user_error,
        )

        message = format_ai_peer_review_user_error(KeyError("legal_requirement_label"))
        self.assertEqual(message, AI_PEER_REVIEW_INTERNAL_DATA_ERROR)
        self.assertNotIn("legal_requirement_label", message)
        self.assertEqual(
            format_ai_peer_review_user_error(ValueError("Vyberte balík.")),
            "Vyberte balík.",
        )

        content = self.provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("Právní vazby", content.data_text)
        self.assertIn("LEGAL-LINK-001", content.data_text)
        self.assertNotIn("legal_requirement_label", content.data_text)
        # Label must come from legal_document_label (document short/title).
        self.assertTrue(
            "ZP" in content.data_text or "Zákoník práce" in content.data_text
            or "262" in content.data_text,
        )

    def test_hierarchy_text_tolerates_missing_legacy_label(self) -> None:
        text = self.provider._hierarchy_to_data_text(
            {
                "catalog_source": {
                    "reference": "KZR-0001",
                    "name": "Zdroj",
                    "category_label": "Zařízení",
                    "description": "",
                    "version_number": 1,
                    "note": "",
                },
                "risk_source": {
                    "export_id": "SOURCE-001",
                    "name": "Zdroj",
                    "category_label": "Zařízení",
                    "description": "",
                    "note": "",
                    "legal_links": [
                        {
                            "export_id": "LEGAL-LINK-001",
                            "legal_document_label": "NV 378/2001",
                            "note": "",
                        }
                    ],
                    "events": [],
                },
            },
        )
        self.assertIn("NV 378/2001", text)
        self.assertNotIn("legal_requirement_label", text)

    def test_open_all_fixture_package_types_without_keyerror(self) -> None:
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        review = export_result.review

        payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        payload["source_reference"] = self.reference
        text = json.dumps(payload, ensure_ascii=False)
        parsed = ai_peer_review_service.parse_response(
            text,
            expected_source_identification_number=self.reference,
            require_proposal_packages=True,
        )
        self.assertGreaterEqual(len(parsed.packages), 10)

        seen_types: set[str] = set()
        for package in parsed.packages:
            seen_types.add(package.package_type)
            # Detail musí jít sestavit pro všechny typy.
            detail = format_proposal_package_detail(package)
            self.assertIsInstance(detail, str)
            self.assertNotIn("legal_requirement_label", detail)

            if package.is_measure_recommendation:
                continue

            dialog = HazardCatalogAiPackageEditDialog(
                package=package,
                package_record_id=0,
                review_id=review.id,
            )
            try:
                summary = dialog.windowTitle()
                self.assertTrue(summary)
            finally:
                dialog.reject()

        expected = {
            AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            AI_MEASURE_REC_EDIT_REQUIRED,
            AI_MEASURE_REC_EDIT_EXISTING,
        }
        self.assertTrue(
            expected.issubset(seen_types),
            f"Chybí typy balíků: {expected - seen_types}; nalezeno {seen_types}",
        )
        # Právní vazby jsou součástí balíků (ne samostatný typ) – ověřit, že je lze otevřít.
        self.assertTrue(
            any(package.legal_links for package in parsed.packages),
            "Fixture musí obsahovat balík s právními vazbami",
        )

        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=review.id,
            response_text=text,
            ai_model="risk-ai-16",
            accepted=list(parsed.packages),
            rejected=[],
            loaded_packages_count=len(parsed.packages),
        )
        pending = [
            item
            for item in ai_peer_review_service.get_packages_for_review(updated.id)
            if item.status == PACKAGE_STATUS_PENDING
        ]
        self.assertEqual(len(pending), len(parsed.packages))

        # Zamítnutí nesmí spadnout na KeyError (regresní tok zpracování).
        first = pending[0]
        hazard_catalog_package_incorporate_service.reject_package(first.id)
        rejected = ai_peer_review_service.package_repository.get_by_id(first.id)
        assert rejected is not None
        self.assertEqual(rejected.status, PACKAGE_STATUS_REJECTED)


if __name__ == "__main__":
    unittest.main()
