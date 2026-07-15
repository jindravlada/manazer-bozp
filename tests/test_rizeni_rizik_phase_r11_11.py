"""Fáze R11.11 – import odpovědi AI ze ZIP."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
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
        AI_PEER_REVIEW_FORMAT_TEXT,
        AI_PEER_REVIEW_PARSE_NO_PROPOSALS,
        AI_PEER_REVIEW_SCHEMA_VERSION,
        AI_PEER_REVIEW_ZIP_CORRUPT,
        AI_PEER_REVIEW_ZIP_NO_RESPONSE,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.ai_peer_review_service import (
        AiPeerReviewError,
        ai_peer_review_service,
    )
    from core.ai_oponentni.sluzby.response_zip_loader import (
        AiPeerReviewZipLoadError,
        discover_zip_response_entries,
        load_response_from_zip,
    )
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewResponseDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )


TEXT_RESPONSE = """\
Oblast: Nežádoucí událost
Návrh: Přimáčknutí
Rodič: —
Zdůvodnění: Test textového importu ze ZIP.
"""


def _json_payload(
    *,
    identification_number: str,
    proposals: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION,
        "source_identification_number": identification_number,
        "generated_at": "2026-07-15T05:00:00",
        "proposals": proposals
        if proposals is not None
        else [
            {
                "proposal_id": "P-ZIP",
                "area": "Nežádoucí událost",
                "name": "Pád břemene",
                "parent_export_id": "ITEM-001",
                "reasoning": "Import ze ZIP.",
            }
        ],
    }


def _write_zip(target: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


class AiPeerReviewZipImportR1111TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R1111",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R1111",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        self.number = self.identification.identification_number
        self.export_dir = Path(tempfile.mkdtemp())

    def test_zip_with_single_valid_json(self) -> None:
        payload = _json_payload(identification_number=self.number)
        zip_path = self.export_dir / "single_json.zip"
        _write_zip(
            zip_path,
            {"odpoved_AI.json": json.dumps(payload, ensure_ascii=False)},
        )

        result = load_response_from_zip(zip_path)
        parsed = ai_peer_review_service.parse_response(
            result.text,
            expected_source_identification_number=self.number,
        )
        self.assertEqual(result.entry_name, "odpoved_AI.json")
        self.assertEqual(parsed.format_label, AI_PEER_REVIEW_FORMAT_JSON_1_1)
        self.assertEqual(parsed.proposals[0].name, "Pád břemene")

    def test_zip_with_single_valid_txt(self) -> None:
        zip_path = self.export_dir / "single_txt.zip"
        _write_zip(zip_path, {"odpoved.txt": TEXT_RESPONSE})

        result = load_response_from_zip(zip_path)
        parsed = ai_peer_review_service.parse_response(result.text)
        self.assertEqual(result.entry_name, "odpoved.txt")
        self.assertEqual(parsed.format_label, AI_PEER_REVIEW_FORMAT_TEXT)
        self.assertEqual(parsed.proposals[0].name, "Přimáčknutí")

    def test_zip_with_multiple_responses_requires_selection(self) -> None:
        zip_path = self.export_dir / "multi.zip"
        _write_zip(
            zip_path,
            {
                "a/odpoved_a.json": json.dumps(
                    _json_payload(
                        identification_number=self.number,
                        proposals=[
                            {
                                "proposal_id": "P-A",
                                "area": "Nežádoucí událost",
                                "name": "A",
                                "parent_export_id": None,
                                "reasoning": "A",
                            }
                        ],
                    )
                ),
                "b/odpoved_b.json": json.dumps(
                    _json_payload(
                        identification_number=self.number,
                        proposals=[
                            {
                                "proposal_id": "P-B",
                                "area": "Nežádoucí událost",
                                "name": "B",
                                "parent_export_id": None,
                                "reasoning": "B",
                            }
                        ],
                    )
                ),
            },
        )

        discovery = discover_zip_response_entries(zip_path)
        self.assertIsNone(discovery.auto_entry)
        self.assertEqual(len(discovery.entries), 2)

        with self.assertRaises(AiPeerReviewZipLoadError) as ctx:
            load_response_from_zip(zip_path)
        self.assertTrue(getattr(ctx.exception, "selection_required", False))

        selected = load_response_from_zip(
            zip_path,
            entry_name="b/odpoved_b.json",
        )
        parsed = ai_peer_review_service.parse_response(
            selected.text,
            expected_source_identification_number=self.number,
        )
        self.assertEqual(parsed.proposals[0].name, "B")

    def test_prefers_odpoved_ai_json(self) -> None:
        zip_path = self.export_dir / "prefer.zip"
        preferred_payload = _json_payload(
            identification_number=self.number,
            proposals=[
                {
                    "proposal_id": "P-PREF",
                    "area": "Nežádoucí událost",
                    "name": "Preferovaný",
                    "parent_export_id": None,
                    "reasoning": "Preferovaný soubor",
                }
            ],
        )
        other_payload = _json_payload(
            identification_number=self.number,
            proposals=[
                {
                    "proposal_id": "P-OTHER",
                    "area": "Nežádoucí událost",
                    "name": "Jiný",
                    "parent_export_id": None,
                    "reasoning": "Jiný soubor",
                }
            ],
        )
        _write_zip(
            zip_path,
            {
                "odpoved.json": json.dumps(other_payload, ensure_ascii=False),
                "odpoved_AI.json": json.dumps(preferred_payload, ensure_ascii=False),
            },
        )

        result = load_response_from_zip(zip_path)
        parsed = ai_peer_review_service.parse_response(
            result.text,
            expected_source_identification_number=self.number,
        )
        self.assertEqual(result.entry_name, "odpoved_AI.json")
        self.assertEqual(parsed.proposals[0].name, "Preferovaný")

    def test_zip_without_supported_files(self) -> None:
        zip_path = self.export_dir / "empty.zip"
        _write_zip(
            zip_path,
            {
                "readme.md": "jen markdown",
                "nested.zip": "fake",
                "image.png": "binary",
            },
        )

        with self.assertRaises(AiPeerReviewZipLoadError) as ctx:
            discover_zip_response_entries(zip_path)
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_ZIP_NO_RESPONSE)

    def test_corrupted_zip(self) -> None:
        zip_path = self.export_dir / "broken.zip"
        zip_path.write_bytes(b"not-a-zip-archive")

        with self.assertRaises(AiPeerReviewZipLoadError) as ctx:
            load_response_from_zip(zip_path)
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_ZIP_CORRUPT)

    def test_path_traversal_entries_are_ignored(self) -> None:
        zip_path = self.export_dir / "traversal.zip"
        payload = _json_payload(identification_number=self.number)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../../../etc/passwd.json", json.dumps(payload))
            zf.writestr("/absolute/path.json", json.dumps(payload))
            zf.writestr("safe/odpoved_AI.json", json.dumps(payload))

        result = load_response_from_zip(zip_path)
        self.assertEqual(result.entry_name, "safe/odpoved_AI.json")

    def test_json_and_txt_direct_import_preserved(self) -> None:
        payload = _json_payload(identification_number=self.number)
        json_parsed = ai_peer_review_service.parse_response(
            json.dumps(payload),
            expected_source_identification_number=self.number,
        )
        self.assertEqual(json_parsed.format_label, AI_PEER_REVIEW_FORMAT_JSON_1_1)

        text_parsed = ai_peer_review_service.parse_response(TEXT_RESPONSE)
        self.assertEqual(text_parsed.format_label, AI_PEER_REVIEW_FORMAT_TEXT)

    def test_zip_entry_without_valid_proposals(self) -> None:
        zip_path = self.export_dir / "no_proposals.zip"
        _write_zip(zip_path, {"odpoved.txt": "žádný návrh tu není"})

        result = load_response_from_zip(zip_path)
        with self.assertRaises(AiPeerReviewError) as ctx:
            ai_peer_review_service.parse_response(result.text)
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_PARSE_NO_PROPOSALS)

    def test_file_dialog_accepts_json_txt_and_zip(self) -> None:
        import inspect

        source_text = inspect.getsource(AiPeerReviewResponseDialog._load_from_file)
        self.assertIn("*.json", source_text)
        self.assertIn("*.txt", source_text)
        self.assertIn("*.zip", source_text)


if __name__ == "__main__":
    unittest.main()
