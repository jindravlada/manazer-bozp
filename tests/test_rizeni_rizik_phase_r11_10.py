"""Fáze R11.10 – import odpovědi AI ve formátu JSON."""

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
        AI_PEER_REVIEW_FORMAT_TEXT,
        AI_PEER_REVIEW_PARSE_NO_PROPOSALS,
        AI_PEER_REVIEW_SCHEMA_VERSION,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.ai_peer_review_service import (
        AiPeerReviewError,
        ai_peer_review_service,
    )
    from core.ai_oponentni.sluzby.response_parser import (
        AiPeerReviewParseError,
        parse_ai_peer_review_response,
        parse_ai_peer_review_text_response,
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
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
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
Zdůvodnění: Test textového importu.
"""


def _json_payload(
    *,
    identification_number: str,
    proposals: list[dict] | None = None,
    schema_version: str = AI_PEER_REVIEW_SCHEMA_VERSION,
) -> dict:
    return {
        "schema_version": schema_version,
        "source_identification_number": identification_number,
        "generated_at": "2026-07-14T22:00:00",
        "proposals": proposals
        if proposals is not None
        else [
            {
                "proposal_id": "P-001",
                "area": "Nežádoucí událost",
                "name": "Pád břemene",
                "parent_export_id": "ITEM-001",
                "reasoning": "Typické riziko jeřábu.",
            },
            {
                "proposal_id": "P-002",
                "area": "Analýza pracoviště",
                "name": "Odkládací plocha",
                "parent_export_id": None,
                "reasoning": "Chybí odkládací prostor.",
            },
        ],
    }


class AiPeerReviewJsonImportR1110TestCase(unittest.TestCase):
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
            name="Provoz R1110",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R1110",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        self.provider = hazard_identification_peer_review_provider
        self.number = self.identification.identification_number
        self.export_dir = Path(tempfile.mkdtemp())

    def test_successful_json_1_1_import_and_field_mapping(self) -> None:
        payload = _json_payload(identification_number=self.number)
        result = parse_ai_peer_review_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_identification_number=self.number,
        )
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_JSON_1_1)
        self.assertEqual(len(result.proposals), 2)
        first = result.proposals[0]
        self.assertEqual(first.proposal_id, "P-001")
        self.assertEqual(first.area, "Nežádoucí událost")
        self.assertEqual(first.name, "Pád břemene")
        self.assertEqual(first.parent_export_id, "ITEM-001")
        self.assertEqual(first.reasoning, "Typické riziko jeřábu.")
        self.assertIsNone(result.proposals[1].parent_export_id)
        self.assertEqual(result.proposals[1].proposal_id, "P-002")

    def test_parent_export_id_null(self) -> None:
        payload = _json_payload(
            identification_number=self.number,
            proposals=[
                {
                    "proposal_id": "P-NULL",
                    "area": "Analýza pracoviště",
                    "name": "Nový zdroj",
                    "parent_export_id": None,
                    "reasoning": "Bez rodiče.",
                }
            ],
        )
        result = parse_ai_peer_review_response(
            json.dumps(payload),
            expected_source_identification_number=self.number,
        )
        self.assertEqual(len(result.proposals), 1)
        self.assertIsNone(result.proposals[0].parent_export_id)

    def test_reject_unsupported_schema_version(self) -> None:
        payload = _json_payload(
            identification_number=self.number,
            schema_version="9.9",
        )
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                json.dumps(payload),
                expected_source_identification_number=self.number,
            )
        self.assertIn("Nepodporovaná verze schématu", str(ctx.exception))

        with self.assertRaises(AiPeerReviewError) as service_ctx:
            ai_peer_review_service.parse_response(
                json.dumps(payload),
                expected_source_identification_number=self.number,
            )
        self.assertIn("Nepodporovaná verze schématu", str(service_ctx.exception))

    def test_reject_different_identification_number(self) -> None:
        payload = _json_payload(identification_number="2099-9999")
        with self.assertRaises(AiPeerReviewParseError) as ctx:
            parse_ai_peer_review_response(
                json.dumps(payload),
                expected_source_identification_number=self.number,
            )
        self.assertIn("neodpovídá otevřené identifikaci", str(ctx.exception))

    def test_partially_invalid_proposals_are_skipped(self) -> None:
        payload = _json_payload(
            identification_number=self.number,
            proposals=[
                {
                    "proposal_id": "P-OK",
                    "area": "Nežádoucí událost",
                    "name": "OK",
                    "parent_export_id": "ITEM-001",
                    "reasoning": "platný",
                },
                {
                    "proposal_id": "P-BAD",
                    "area": "Událost",
                    # chybí name
                    "parent_export_id": "ITEM-001",
                    "reasoning": "neplatný",
                },
                "jen-retezec",
                {
                    "proposal_id": "P-BAD2",
                    "area": "Událost",
                    "name": "X",
                    "parent_export_id": 123,
                    "reasoning": "špatný typ rodiče",
                },
            ],
        )
        result = parse_ai_peer_review_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_identification_number=self.number,
        )
        self.assertEqual(len(result.proposals), 1)
        self.assertEqual(result.proposals[0].name, "OK")
        self.assertEqual(result.skipped_count, 3)
        self.assertTrue(any("chybí povinná pole" in reason for reason in result.skip_reasons))
        self.assertTrue(any("není objekt" in reason for reason in result.skip_reasons))
        self.assertTrue(
            any("parent_export_id musí být string nebo null" in reason for reason in result.skip_reasons)
        )

    def test_unassigned_on_invalid_parent_with_json_import(self) -> None:
        target = self.export_dir / "export.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        payload = _json_payload(
            identification_number=self.number,
            proposals=[
                {
                    "proposal_id": "P-ORPHAN",
                    "area": "Nežádoucí událost",
                    "name": "Orphan",
                    "parent_export_id": "ITEM-999",
                    "reasoning": "Neexistující rodič",
                }
            ],
        )
        proposals = ai_peer_review_service.parse_response(
            json.dumps(payload),
            expected_source_identification_number=self.number,
        ).proposals
        before = len(
            hazard_event_service.get_for_identification(
                self.identification.id,
                include_inactive=False,
            )
        )
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.identification.id,
            review_id=export_result.review.id,
            response_text=json.dumps(payload),
            ai_model="Claude",
            accepted=proposals,
            rejected=[],
        )
        self.assertEqual(updated.accepted_count, 0)
        self.assertEqual(updated.unassigned_count, 1)
        after = hazard_event_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertEqual(len(after), before)
        unassigned = ai_peer_review_service.get_unassigned_for_review(
            export_result.review.id
        )
        self.assertEqual(len(unassigned), 1)
        self.assertEqual(unassigned[0].name, "Orphan")

    def test_text_import_preserved(self) -> None:
        result = parse_ai_peer_review_response(TEXT_RESPONSE)
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_TEXT)
        self.assertEqual(len(result.proposals), 1)
        self.assertIsNone(result.proposals[0].parent_export_id)
        self.assertEqual(
            parse_ai_peer_review_text_response(TEXT_RESPONSE)[0].name,
            "Přimáčknutí",
        )

    def test_invalid_json_falls_back_to_text_parser(self) -> None:
        # Neplatný JSON, ale platný textový blok
        mixed = "{not-json\n\n" + TEXT_RESPONSE
        result = parse_ai_peer_review_response(mixed)
        self.assertEqual(result.format_label, AI_PEER_REVIEW_FORMAT_TEXT)
        self.assertEqual(len(result.proposals), 1)
        self.assertEqual(result.proposals[0].name, "Přimáčknutí")

    def test_generic_error_when_no_proposals(self) -> None:
        with self.assertRaises(AiPeerReviewError) as ctx:
            ai_peer_review_service.parse_response("žádný návrh tu není")
        self.assertEqual(str(ctx.exception), AI_PEER_REVIEW_PARSE_NO_PROPOSALS)

    def test_file_dialog_accepts_json_and_txt(self) -> None:
        import inspect

        source_text = inspect.getsource(AiPeerReviewResponseDialog._load_from_file)
        self.assertIn("*.json", source_text)
        self.assertIn("*.txt", source_text)

    def test_accept_reject_workflow_unchanged_for_json(self) -> None:
        target = self.export_dir / "flow.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        payload = _json_payload(identification_number=self.number)
        proposals = ai_peer_review_service.parse_response(
            json.dumps(payload),
            expected_source_identification_number=self.number,
        ).proposals
        self.assertEqual(len(proposals), 2)
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.identification.id,
            review_id=export_result.review.id,
            response_text=json.dumps(payload),
            ai_model="ChatGPT",
            accepted=[proposals[0]],
            rejected=[proposals[1]],
        )
        self.assertEqual(updated.ai_model, "ChatGPT")
        self.assertEqual(updated.accepted_count, 1)
        self.assertEqual(updated.rejected_count, 1)
        events = hazard_event_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertTrue(any(row.event.name == "Pád břemene" for row in events))


if __name__ == "__main__":
    unittest.main()
