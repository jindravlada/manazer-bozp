"""RISK-AI-SINGLE-FILE-EXPORT-1: katalogový export jediného JSON bez režimů."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-single-file-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QRadioButton

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_JSON_FILE_FILTER,
        AI_PEER_REVIEW_NOT_AI_RESPONSE,
        AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
        AI_PEER_REVIEW_ZIP_FILE_FILTER,
        AI_REVIEW_REQUEST_FILENAME_PREFIX,
        AI_REVIEW_REQUEST_USER_INSTRUCTION,
        AI_REVIEW_RESPONSE_FILENAME,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.parse_errors import AiPeerReviewParseError
    from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import (
        AiPeerReviewExportOptionsDialog,
        catalog_peer_review_export_dialog_config,
    )
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
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        catalog_source_reference,
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
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
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group

_FORBIDDEN_KEYS = {
    "request_mode",
    "legal_document_id",
    "legal_requirement_id",
    "application_version",
    "template_id",
    "export_id_map",
}

_REQUIRED_ROOT_KEYS = (
    "schema_version",
    "user_instruction",
    "ai_instruction",
    "processing",
    "response_schema",
    "source_data",
)


def _collect_keys(value) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


class RiskAiSingleFileExport1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.provider = hazard_catalog_source_peer_review_provider
        self.group = ensure_exposed_group("Zaměstnanci SINGLE-FILE")
        self.export_dir = Path(tempfile.mkdtemp(prefix="risk-ai-sf-export-"))
        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            number="262",
            year=2006,
            title="Zákoník práce",
            short_title="ZP",
        )

    def _create_empty_template(self):
        return hazard_library_template_service.create_template(
            name="Prázdný zdroj",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis prázdného zdroje",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )

    def _create_filled_template(self):
        template = hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis zdroje",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=template.id,
            legal_document_id=self.document.id,
            note="Vazba na ZP",
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Pád břemene",
            description="Popis události",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Nutná opatření",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Ochranné zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Doplnit zábradlí",
        )
        return template

    def _export(self, template, filename: str) -> tuple[Path, dict]:
        target = self.export_dir / filename
        result = ai_peer_review_service.export_package(
            self.provider,
            template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        self.assertTrue(target.is_file())
        self.assertFalse(zipfile.is_zipfile(target))
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertIsNotNone(result.review.id)
        self.assertTrue(result.review.export_id_map_json)
        return target, payload

    def _assert_common_request(self, payload: dict) -> None:
        for key in _REQUIRED_ROOT_KEYS:
            self.assertIn(key, payload)
        self.assertEqual(payload["schema_version"], AI_PEER_REVIEW_SCHEMA_VERSION_2_0)
        self.assertEqual(payload["user_instruction"], AI_REVIEW_REQUEST_USER_INSTRUCTION)
        self.assertEqual(
            payload["processing"],
            {"output_filename": AI_REVIEW_RESPONSE_FILENAME, "language": "cs"},
        )
        self.assertNotIn("request_mode", payload)
        self.assertNotIn("request_mode", payload["processing"])
        instruction = payload["ai_instruction"]
        self.assertEqual(instruction["role"], "experienced_safety_technician")
        self.assertEqual(instruction["role_label"], "Zkušený bezpečnostní technik")
        self.assertIsInstance(instruction["goal"], list)
        self.assertIsInstance(instruction["rules"], list)
        rules_text = "\n".join(instruction["rules"])
        self.assertIn("žádné nežádoucí události", rules_text)
        self.assertIn("první odborný návrh", rules_text)
        self.assertIn("oponenturu", rules_text)
        self.assertIn("Prázdný katalog je legitimní", rules_text)
        self.assertIn("new_event", rules_text)
        self.assertIn("bez Markdownu", rules_text)
        dumped = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("request_mode", dumped)
        keys = _collect_keys(payload)
        self.assertTrue(_FORBIDDEN_KEYS.isdisjoint(keys), keys & _FORBIDDEN_KEYS)
        source_data = payload["source_data"]
        self.assertEqual(set(source_data), {"catalog_source", "risk_source", "counts"})
        self.assertNotIn("export_id_map", payload)
        schema = payload["response_schema"]
        self.assertEqual(schema["schema_version"], AI_PEER_REVIEW_SCHEMA_VERSION_2_0)
        self.assertIn("proposal_packages", schema["properties"])
        self.assertIn("proposal_package", schema["$defs"])

    def test_empty_and_filled_catalog_use_the_same_export_path(self) -> None:
        empty = self._create_empty_template()
        filled = self._create_filled_template()
        empty_path, empty_payload = self._export(
            empty,
            f"{AI_REVIEW_REQUEST_FILENAME_PREFIX}_empty.json",
        )
        filled_path, filled_payload = self._export(
            filled,
            f"{AI_REVIEW_REQUEST_FILENAME_PREFIX}_filled.json",
        )
        self._assert_common_request(empty_payload)
        self._assert_common_request(filled_payload)
        self.assertEqual(empty_payload["source_data"]["counts"]["events"], 0)
        self.assertEqual(empty_payload["source_data"]["risk_source"]["events"], [])
        self.assertGreater(filled_payload["source_data"]["counts"]["events"], 0)
        self.assertEqual(
            filled_payload["source_data"]["risk_source"]["events"][0]["export_id"],
            "EVENT-001",
        )
        legal_ref = filled_payload["source_data"]["risk_source"]["legal_links"][0][
            "reference"
        ]
        self.assertTrue(
            "262" in legal_ref or "Zákoník" in legal_ref or "ZP" in legal_ref,
            legal_ref,
        )
        siblings = {path.name for path in self.export_dir.iterdir()}
        self.assertEqual(siblings, {empty_path.name, filled_path.name})

    def test_default_filename_and_filter_are_json(self) -> None:
        template = self._create_empty_template()
        label = catalog_source_reference(template.id)
        filename = ai_peer_review_service.default_export_filename(
            label,
            datetime.now(),
            provider=self.provider,
        )
        self.assertEqual(
            filename,
            f"{AI_REVIEW_REQUEST_FILENAME_PREFIX}_{label}.json",
        )
        self.assertEqual(
            ai_peer_review_service.export_file_filter(self.provider),
            AI_PEER_REVIEW_JSON_FILE_FILTER,
        )
        self.assertEqual(
            ai_peer_review_service.export_file_filter(
                hazard_identification_peer_review_provider,
            ),
            AI_PEER_REVIEW_ZIP_FILE_FILTER,
        )
        self.assertTrue(self.provider.exports_single_request_json)
        self.assertFalse(
            getattr(
                hazard_identification_peer_review_provider,
                "exports_single_request_json",
                False,
            )
        )

    def test_export_dialog_has_no_mode_choice(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog(
            dialog_config=catalog_peer_review_export_dialog_config(),
        )
        labels = [radio.text() for radio in dialog.findChildren(QRadioButton)]
        joined = " ".join(labels).casefold()
        self.assertNotIn("první návrh", joined)
        self.assertNotIn("request_mode", joined)
        self.assertNotIn("starter", joined)

    def test_request_json_is_not_imported_as_response(self) -> None:
        template = self._create_empty_template()
        _path, payload = self._export(
            template,
            f"{AI_REVIEW_REQUEST_FILENAME_PREFIX}_not_response.json",
        )
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                json.dumps(payload, ensure_ascii=False),
                expected_source_identification_number=catalog_source_reference(
                    template.id,
                ),
                require_proposal_packages=True,
            )
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

    def test_schema_2_0_response_still_parses_after_single_file_export(self) -> None:
        template = self._create_filled_template()
        self._export(template, f"{AI_REVIEW_REQUEST_FILENAME_PREFIX}_compat.json")
        response = {
            "schema_version": "2.0",
            "source_reference": catalog_source_reference(template.id),
            "generated_at": "2026-09-04T18:00:00",
            "proposal_packages": [
                {
                    "package_id": "PKG-001",
                    "package_type": "new_event",
                    "target_event_export_id": None,
                    "event": {"name": "Pád z výšky", "description": "", "note": ""},
                    "assessments": [
                        {
                            "exposed_group": "Obsluha",
                            "exposed_groups": ["Obsluha"],
                            "severity": "moderate",
                            "conclusion": "Riziko",
                            "existing_measures": [],
                            "required_measures": [],
                        }
                    ],
                    "legal_links": [],
                    "reasoning": "Chybí událost.",
                }
            ],
            "measure_recommendations": [],
        }
        parsed = parse_ai_peer_review_response(
            json.dumps(response, ensure_ascii=False),
            expected_source_identification_number=catalog_source_reference(
                template.id,
            ),
            require_proposal_packages=True,
        )
        self.assertEqual(len(parsed.packages), 1)
        self.assertEqual(parsed.packages[0].package_type, "new_event")


if __name__ == "__main__":
    unittest.main()
