"""UX-RISK-7: vícesouborový ZIP export podkladů AI pro katalog zdrojů rizik."""

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

_TMP = Path(tempfile.mkdtemp(prefix="ux-risk-7-"))
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
        AI_PEER_REVIEW_NOT_AI_RESPONSE,
        AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
        AI_PEER_REVIEW_ZIP_FILE_FILTER,
        AI_PEER_REVIEW_ZIP_FILES,
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

_FORBIDDEN_USER_PHRASE = "Navazující opatření"
_CONTROL_QUESTIONS = "Kontrolní otázky pro revizi posouzení rizik"


def _read_zip_texts(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path, "r") as zf:
        return {
            name: zf.read(name).decode("utf-8")
            for name in zf.namelist()
        }


class UxRisk7CatalogAiZipExportTestCase(unittest.TestCase):
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
        self.group = ensure_exposed_group("Zaměstnanci UX-RISK-7")
        self.group_visitors = ensure_exposed_group("Návštěvy UX-RISK-7")
        self.export_dir = Path(tempfile.mkdtemp(prefix="ux-risk-7-export-"))
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
        event2 = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Pád z výšky",
            description="Druhá událost",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Nutná opatření",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event2.id,
            exposed_group_id=self.group_visitors.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Ohrožené návštěvy",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Ochranné zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Je břemeno před zdvihem řádně uchyceno?",
        )
        return template

    def _export(self, template, filename: str) -> tuple[Path, dict[str, str]]:
        target = self.export_dir / filename
        result = ai_peer_review_service.export_package(
            self.provider,
            template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        self.assertTrue(target.is_file())
        self.assertTrue(zipfile.is_zipfile(target))
        self.assertIsNotNone(result.review.id)
        self.assertTrue(result.review.export_id_map_json)
        files = _read_zip_texts(target)
        self.assertEqual(set(files), set(AI_PEER_REVIEW_ZIP_FILES))
        for name, text in files.items():
            self.assertTrue(text.strip(), f"{name} je prázdný")
        return target, files

    def _assert_current_methodology(self, files: dict[str, str]) -> None:
        joined = "\n".join(files[name] for name in ("pokyn_pro_AI.txt", "data.txt", "prehled.txt"))
        self.assertIn(_CONTROL_QUESTIONS, files["pokyn_pro_AI.txt"])
        self.assertIn(_CONTROL_QUESTIONS, files["data.txt"])
        self.assertIn(_CONTROL_QUESTIONS, files["prehled.txt"])
        self.assertIn("reálně existujícího na pracovišti", files["pokyn_pro_AI.txt"])
        self.assertIn("mechanismus úrazu", files["pokyn_pro_AI.txt"])
        self.assertIn("ANO / NE / NETÝKÁ SE", files["pokyn_pro_AI.txt"])
        self.assertIn("schema 2.0", files["pokyn_pro_AI.txt"].casefold())
        self.assertIn("proposal_packages", files["pokyn_pro_AI.txt"])
        self.assertNotIn(_FORBIDDEN_USER_PHRASE, joined)
        zadani = json.loads(files["zadani.json"])
        self.assertNotIn(_FORBIDDEN_USER_PHRASE, json.dumps(zadani, ensure_ascii=False))
        schema = json.loads(files["schema_odpovedi.json"])
        self.assertEqual(schema["schema_version"], AI_PEER_REVIEW_SCHEMA_VERSION_2_0)
        self.assertIn("proposal_package", schema["$defs"])

    def test_empty_and_filled_catalog_export_multifile_zip(self) -> None:
        empty = self._create_empty_template()
        filled = self._create_filled_template()
        empty_path, empty_files = self._export(empty, "empty.zip")
        filled_path, filled_files = self._export(filled, "filled.zip")
        self._assert_current_methodology(empty_files)
        self._assert_current_methodology(filled_files)

        empty_zadani = json.loads(empty_files["zadani.json"])
        filled_zadani = json.loads(filled_files["zadani.json"])
        self.assertEqual(empty_zadani["risk_source"]["events"], [])
        self.assertEqual(empty_zadani["object_count"], 1)
        self.assertIn("Prázdný zdroj", empty_files["data.txt"])
        self.assertIn("(žádná)", empty_files["data.txt"])

        self.assertGreaterEqual(len(filled_zadani["risk_source"]["events"]), 2)
        self.assertEqual(
            filled_zadani["risk_source"]["events"][0]["export_id"],
            "EVENT-001",
        )
        self.assertIn("Pád břemene", filled_files["data.txt"])
        self.assertIn("Pád z výšky", filled_files["data.txt"])
        self.assertIn("Zaměstnanci UX-RISK-7", filled_files["data.txt"])
        self.assertIn("Návštěvy UX-RISK-7", filled_files["data.txt"])
        self.assertIn("Portálový jeřáb", filled_files["data.txt"])
        legal_ref = filled_zadani["risk_source"]["legal_links"][0]["reference"]
        self.assertTrue(
            "262" in legal_ref or "Zákoník" in legal_ref or "ZP" in legal_ref,
            legal_ref,
        )
        self.assertNotIn("legal_document_id", json.dumps(filled_zadani, ensure_ascii=False))
        self.assertNotIn("export_id_map", filled_zadani)
        self.assertNotIn("source_data", filled_zadani)
        self.assertNotIn("user_instruction", filled_zadani)
        siblings = {path.name for path in self.export_dir.iterdir()}
        self.assertEqual(siblings, {empty_path.name, filled_path.name})

    def test_default_filename_and_filter_are_zip(self) -> None:
        template = self._create_empty_template()
        label = catalog_source_reference(template.id)
        filename = ai_peer_review_service.default_export_filename(
            label,
            datetime(2026, 9, 6, 13, 12),
            provider=self.provider,
        )
        self.assertEqual(filename, f"AI_oponentura_{label}_2026-09-06_1312.zip")
        self.assertEqual(
            ai_peer_review_service.export_file_filter(self.provider),
            AI_PEER_REVIEW_ZIP_FILE_FILTER,
        )
        self.assertEqual(
            ai_peer_review_service.export_file_filter(
                hazard_identification_peer_review_provider,
            ),
            AI_PEER_REVIEW_ZIP_FILE_FILTER,
        )
        self.assertFalse(
            getattr(self.provider, "exports_single_request_json", False)
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

    def test_export_zip_is_not_imported_as_response(self) -> None:
        template = self._create_empty_template()
        _path, files = self._export(template, "not_response.zip")
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                files["zadani.json"],
                expected_source_identification_number=catalog_source_reference(
                    template.id,
                ),
                require_proposal_packages=True,
            )
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

    def test_schema_2_0_response_still_parses_after_zip_export(self) -> None:
        template = self._create_filled_template()
        self._export(template, "compat.zip")
        response = {
            "schema_version": "2.0",
            "source_reference": catalog_source_reference(template.id),
            "generated_at": "2026-09-06T13:12:00",
            "proposal_packages": [
                {
                    "package_id": "PKG-001",
                    "package_type": "new_event",
                    "target_event_export_id": None,
                    "event": {"name": "Zachycení oděvu", "description": "", "note": ""},
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
