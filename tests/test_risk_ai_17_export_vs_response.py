"""RISK-AI-17: rozlišení ZIP zadání a JSON odpovědi AI."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_NOT_AI_RESPONSE,
    AI_PEER_REVIEW_ZIP_FILES,
)
from core.ai_oponentni.sluzby.parse_errors import AiPeerReviewParseError
from core.ai_oponentni.sluzby.proposal_package_parser import (
    _looks_like_export_or_response_schema,
    _looks_like_package_schema_response,
    parse_ai_proposal_packages_response,
)
from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
from core.ai_oponentni.sluzby.response_zip_loader import (
    AiPeerReviewZipLoadError,
    discover_zip_response_entries,
    load_response_from_zip,
)

_USB_ZIP = Path("/run/media/vjm/USB Flash/AI_oponentura_KZR-0001_2026-07-29_0631.zip")
_USB_RESPONSE = Path(
    "/run/media/vjm/USB Flash/AI_oponentura_KZR-0001_2026-07-29_0631_odpoved.json"
)

_SAMPLE_RESPONSE = {
    "schema_version": "2.0",
    "source_reference": "KZR-0001",
    "generated_at": "2026-07-29T06:31:00",
    "proposal_packages": [
        {
            "package_id": "PKG-001",
            "package_type": "new_event",
            "target_event_export_id": None,
            "event": {"name": "Pád břemene", "description": "", "note": ""},
            "assessments": [
                {
                    "exposed_group": "Obsluha",
                    "exposed_groups": ["Obsluha"],
                    "severity": "moderate",
                    "conclusion": "Riziko",
                    "existing_measures": [],
                    "required_measures": [
                        {"description": "Kontrola úvazků.", "note": ""},
                    ],
                }
            ],
            "legal_links": [],
            "reasoning": "Chybí událost v katalogu.",
        }
    ],
    "measure_recommendations": [
        {
            "recommendation_id": "REC-001",
            "typ": "beze_zmen",
            "reasoning": "Stávající opatření jsou dostatečná.",
        }
    ],
}

_SAMPLE_SCHEMA_ODPOVEDI = {
    "schema_version": "2.0",
    "description": "Schéma odpovědi AI",
    "type": "object",
    "required": ["schema_version", "source_reference"],
    "properties": {
        "schema_version": {"type": "string"},
        "source_reference": {"type": "string"},
        "proposal_packages": {"type": "array"},
        "measure_recommendations": {"type": "array"},
    },
    "$defs": {},
}

_SAMPLE_ZADANI = {
    "schema_version": "2.0",
    "response_schema_version": "2.0",
    "export_type": "hazard_catalog_source_ai_peer_review",
    "catalog_source": {"reference": "KZR-0001"},
    "hierarchy": {},
}

_SAMPLE_REQUEST = {
    "schema_version": "2.0",
    "user_instruction": "Zpracuj dle instrukcí.",
    "ai_instruction": {
        "role": "experienced_safety_technician",
        "role_label": "Zkušený bezpečnostní technik",
        "goal": [],
        "rules": [],
    },
    "processing": {
        "output_filename": "AI_REVIEW_RESPONSE.json",
        "language": "cs",
    },
    "response_schema": _SAMPLE_SCHEMA_ODPOVEDI,
    "source_data": {
        "catalog_source": {"reference": "KZR-0001"},
        "risk_source": {"export_id": "SOURCE-001", "events": []},
        "counts": {"events": 0},
    },
}


class RiskAi17ExportVsResponseTestCase(unittest.TestCase):
    def test_looks_like_rejects_schema_and_zadani(self) -> None:
        self.assertFalse(_looks_like_package_schema_response(_SAMPLE_SCHEMA_ODPOVEDI))
        self.assertFalse(_looks_like_package_schema_response(_SAMPLE_ZADANI))
        self.assertTrue(_looks_like_export_or_response_schema(_SAMPLE_SCHEMA_ODPOVEDI))
        self.assertTrue(_looks_like_export_or_response_schema(_SAMPLE_ZADANI))
        self.assertTrue(_looks_like_export_or_response_schema(_SAMPLE_REQUEST))
        self.assertTrue(_looks_like_package_schema_response(_SAMPLE_RESPONSE))
        self.assertFalse(_looks_like_export_or_response_schema(_SAMPLE_RESPONSE))

    def test_schema_odpovedi_is_not_ai_response(self) -> None:
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_proposal_packages_response(
                json.dumps(_SAMPLE_SCHEMA_ODPOVEDI, ensure_ascii=False),
                expected_source_reference="KZR-0001",
            )
        message = str(ctx.exception)
        self.assertEqual(message, AI_PEER_REVIEW_NOT_AI_RESPONSE)
        self.assertNotIn("chybí pole source_reference", message.casefold())

    def test_zadani_json_is_not_ai_response(self) -> None:
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                json.dumps(_SAMPLE_ZADANI, ensure_ascii=False),
                expected_source_identification_number="KZR-0001",
                require_proposal_packages=True,
            )
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

    def test_review_request_json_is_not_ai_response(self) -> None:
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                json.dumps(_SAMPLE_REQUEST, ensure_ascii=False),
                expected_source_identification_number="KZR-0001",
                require_proposal_packages=True,
            )
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

    def test_export_zip_is_not_recognized_as_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "export.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for name in AI_PEER_REVIEW_ZIP_FILES:
                    if name.endswith(".json"):
                        payload = (
                            _SAMPLE_SCHEMA_ODPOVEDI
                            if name == "schema_odpovedi.json"
                            else _SAMPLE_ZADANI
                        )
                        zf.writestr(name, json.dumps(payload, ensure_ascii=False))
                    else:
                        zf.writestr(name, f"obsah {name}")

            with self.assertRaises(AiPeerReviewZipLoadError) as ctx:
                discover_zip_response_entries(zip_path)
            self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

            with self.assertRaises(AiPeerReviewZipLoadError) as ctx2:
                load_response_from_zip(zip_path)
            self.assertEqual(str(ctx2.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

    def test_valid_response_json_imports(self) -> None:
        result = parse_ai_peer_review_response(
            json.dumps(_SAMPLE_RESPONSE, ensure_ascii=False),
            expected_source_identification_number="KZR-0001",
            require_proposal_packages=True,
        )
        self.assertEqual(result.source_reference, "KZR-0001")
        self.assertGreaterEqual(len(result.packages), 2)

    def test_export_files_ignored_when_real_response_in_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "mixed.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for name in AI_PEER_REVIEW_ZIP_FILES:
                    zf.writestr(name, "{}")
                zf.writestr(
                    "odpoved_AI.json",
                    json.dumps(_SAMPLE_RESPONSE, ensure_ascii=False),
                )

            discovery = discover_zip_response_entries(zip_path)
            self.assertEqual(discovery.entries, ("odpoved_AI.json",))
            self.assertEqual(discovery.auto_entry, "odpoved_AI.json")
            loaded = load_response_from_zip(zip_path)
            parsed = parse_ai_peer_review_response(
                loaded.text,
                expected_source_identification_number="KZR-0001",
                require_proposal_packages=True,
            )
            self.assertEqual(parsed.source_reference, "KZR-0001")

    @unittest.skipUnless(_USB_ZIP.is_file() and _USB_RESPONSE.is_file(), "USB fixtures")
    def test_attached_usb_export_and_response(self) -> None:
        with self.assertRaises(AiPeerReviewZipLoadError) as ctx:
            discover_zip_response_entries(_USB_ZIP)
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_NOT_AI_RESPONSE)

        text = _USB_RESPONSE.read_text(encoding="utf-8")
        parsed = parse_ai_peer_review_response(
            text,
            expected_source_identification_number="KZR-0001",
            require_proposal_packages=True,
        )
        self.assertEqual(parsed.source_reference, "KZR-0001")
        self.assertGreater(len(parsed.packages), 0)


if __name__ == "__main__":
    unittest.main()
