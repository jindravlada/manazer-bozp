"""Fáze R11.2 – oponentní posouzení AI (obecný modul + adaptér Registru rizik)."""

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

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_TAB_TITLE,
        AI_PEER_REVIEW_ZIP_FILES,
        DEFAULT_AI_PEER_REVIEW_PROMPT,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import (
        UNASSIGNED_PROPOSAL_STATUS_LABEL,
        AiUnassignedProposal,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import (
        AiPeerReviewError,
        ai_peer_review_service,
    )
    from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
    from core.ai_oponentni.types import AiPeerReviewExportOptions, AiProposal
    from core.ai_oponentni.ui.ai_peer_review_widget import (
        AiPeerReviewExportOptionsDialog,
        AiPeerReviewWidget,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        SOURCE_TYPE_HAZARD_IDENTIFICATION,
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
        identified_hazard_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog


SAMPLE_RESPONSE = """\
Oblast: Nebezpečí
Návrh: Přimáčknutí mezi vozy
Rodič: ITEM-001
Zdůvodnění:
Typické riziko při spojování a rozpojování kolejových vozidel.

Oblast: OOPP
Návrh: Ochranná obuv s ocelovou špicí
Rodič: ASSESSMENT-001
Zdůvodnění: Ochrana nohou při manipulaci s spojovacím materiálem.
"""


class AiPeerReviewPhaseR112TestCase(unittest.TestCase):
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
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(IdentifiedHazard))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Jan", last_name="Novák")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
            note="Testovací poznámka",
        )
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
            description="Posunová lokomotiva",
        )
        inactive_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Neaktivní zařízení",
        )
        hazard_inventory_item_service.deactivate_item(inactive_item.id)

        self.hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pohyb kolejového vozidla",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard.id,
            name="Sražení s osobou",
        )
        self.assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group="Posunovač",
            consequence="Zranění končetiny",
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Výstražný signál",
        )
        hazard_required_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Instalace zábran",
        )
        self.export_dir = Path(tempfile.mkdtemp())
        self.provider = hazard_identification_peer_review_provider

    def test_ai_peer_reviews_table_exists(self) -> None:
        columns = _table_columns("ai_peer_reviews")
        self.assertIn("source_type", columns)
        self.assertIn("source_id", columns)
        self.assertIn("prompt_text", columns)
        self.assertIn("response_text", columns)
        self.assertIn("ai_model", columns)
        self.assertIn("accepted_count", columns)
        self.assertIn("rejected_count", columns)
        self.assertIn("export_id_map_json", columns)
        self.assertIn("unassigned_count", columns)
        self.assertIn("export_scope", columns)
        self.assertIn("batch_count", columns)
        self.assertIn("selected_source_count", columns)
        self.assertIn("total_object_count", columns)
        unassigned_columns = _table_columns("ai_unassigned_proposals")
        self.assertIn("ai_peer_review_id", unassigned_columns)
        self.assertIn("parent_export_id", unassigned_columns)
        self.assertIn("status", unassigned_columns)
        batch_columns = _table_columns("ai_peer_review_batches")
        self.assertIn("ai_peer_review_id", batch_columns)
        self.assertIn("batch_number", batch_columns)

    def test_export_saved_identification(self) -> None:
        target = self.export_dir / "export.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        self.assertTrue(target.exists())
        self.assertEqual(result.review.source_type, SOURCE_TYPE_HAZARD_IDENTIFICATION)
        self.assertIn("Jsi zkušený odborník BOZP", result.review.prompt_text)

    def test_reject_unsaved_identification(self) -> None:
        with self.assertRaises(AiPeerReviewError):
            ai_peer_review_service.export_package(
                self.provider,
                None,
                self.export_dir / "fail.zip",
            )

    def test_export_only_active_records_in_data(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("Lokomotiva", content.data_text)
        self.assertNotIn("Neaktivní zařízení", content.data_text)
        self.assertIn("Pohyb kolejového vozidla", content.data_text)

    def test_zip_contains_hierarchical_export_files(self) -> None:
        target = self.export_dir / "balicek.zip"
        ai_peer_review_service.export_package(self.provider, self.identification.id, target)
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
            prompt = zf.read("pokyn_pro_AI.txt").decode("utf-8")
            data = zf.read("data.txt").decode("utf-8")
            zadani = json.loads(zf.read("zadani.json").decode("utf-8"))
            schema = json.loads(zf.read("schema_odpovedi.json").decode("utf-8"))
        self.assertIn("Jsi zkušený odborník BOZP", prompt)
        self.assertIn("ITEM-001", data)
        self.assertIn("HAZARD-001", data)
        self.assertEqual(zadani["schema_version"], "1.1")
        self.assertEqual(zadani["export_scope"], "full")
        self.assertEqual(zadani["batch_number"], 1)
        self.assertEqual(zadani["batch_count"], 1)
        self.assertEqual(schema["schema_version"], "1.1")
        self.assertIn("parent_export_id", schema["$defs"]["proposal"]["properties"])

    def test_batch_export_metadata_defaults(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertEqual(content.export_scope, "full")
        self.assertEqual(content.batch_number, 1)
        self.assertEqual(content.batch_count, 1)
        assert content.zadani_json is not None
        self.assertEqual(content.zadani_json["export_scope"], "full")
        self.assertEqual(content.zadani_json["batch_number"], 1)
        self.assertEqual(content.zadani_json["batch_count"], 1)
        self.assertEqual(content.zadani_json["source_count"], 1)
        self.assertGreaterEqual(content.zadani_json["object_count"], 1)
        self.assertFalse(content.zadani_json["recommended_limit_exceeded"])

    def test_change_tracking_metadata_defaults(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertEqual(
            content.change_tracking,
            {"mode": "full", "base_export": None, "changed_objects": []},
        )
        assert content.zadani_json is not None
        self.assertEqual(
            content.zadani_json["change_tracking"],
            {"mode": "full", "base_export": None, "changed_objects": []},
        )

    def test_hierarchical_zadani_json(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        assert content.zadani_json is not None
        tree = content.zadani_json["workplace_analysis"]
        self.assertEqual(len(tree), 1)
        item = tree[0]
        self.assertEqual(item["export_id"], "ITEM-001")
        self.assertEqual(item["name"], "Lokomotiva")
        self.assertEqual(item["hazards"][0]["export_id"], "HAZARD-001")
        self.assertEqual(item["hazards"][0]["events"][0]["export_id"], "EVENT-001")
        assessment = item["hazards"][0]["events"][0]["assessments"][0]
        self.assertEqual(assessment["export_id"], "ASSESSMENT-001")
        self.assertEqual(assessment["exposed_group"], "Posunovač")
        self.assertEqual(assessment["existing_measures"][0]["description"], "Výstražný signál")
        self.assertEqual(assessment["required_measures"][0]["description"], "Instalace zábran")

    def test_hierarchical_data_txt_nesting(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("Zdroj analýzy [ITEM-001]", content.data_text)
        self.assertIn("Nebezpečí", content.data_text)
        self.assertIn("[HAZARD-001]", content.data_text)
        self.assertIn("Událost", content.data_text)
        self.assertIn("[EVENT-001]", content.data_text)
        self.assertIn("Posouzení", content.data_text)
        self.assertIn("[ASSESSMENT-001]", content.data_text)
        self.assertIn("Existující opatření", content.data_text)
        self.assertIn("Potřebná opatření", content.data_text)
        # Neaktivní položka nesmí být v hierarchii
        self.assertNotIn("Neaktivní zařízení", content.data_text)

    def test_no_internal_database_ids_in_export(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        dumped = json.dumps(content.zadani_json, ensure_ascii=False)
        for forbidden in (
            "hazard_identification_id",
            "inventory_item_id",
            "identified_hazard_id",
            "hazard_event_id",
            "hazard_risk_assessment_id",
        ):
            self.assertNotIn(forbidden, dumped)
        # Stabilní exportní ID mají být přítomna
        self.assertIn("ITEM-001", dumped)
        self.assertIn("HAZARD-001", dumped)

    def test_responsible_person_excluded_by_default(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(include_responsible_person=False),
        )
        self.assertNotIn("Odpovědná osoba:", content.data_text)

    def test_responsible_person_optional_include(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(include_responsible_person=True),
        )
        self.assertIn("Novák", content.data_text)

    def test_creates_peer_review_record(self) -> None:
        target = self.export_dir / "evidence.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        rows = ai_peer_review_service.get_for_source(
            SOURCE_TYPE_HAZARD_IDENTIFICATION,
            self.identification.id,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, result.review.id)
        self.assertEqual(rows[0].prompt_text.strip(), DEFAULT_AI_PEER_REVIEW_PROMPT.strip())

    def test_no_db_record_on_failed_export(self) -> None:
        target = self.export_dir / "selhani.zip"
        with patch(
            "core.ai_oponentni.sluzby.ai_peer_review_service.zipfile.ZipFile",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(AiPeerReviewError):
                ai_peer_review_service.export_package(
                    self.provider,
                    self.identification.id,
                    target,
                )
        self.assertEqual(
            ai_peer_review_service.get_for_source(
                SOURCE_TYPE_HAZARD_IDENTIFICATION,
                self.identification.id,
            ),
            [],
        )

    def test_parse_response_format(self) -> None:
        proposals = parse_ai_peer_review_response(SAMPLE_RESPONSE)
        self.assertEqual(len(proposals), 2)
        self.assertEqual(proposals[0].area, "Nebezpečí")
        self.assertEqual(proposals[0].name, "Přimáčknutí mezi vozy")
        self.assertEqual(proposals[0].parent_export_id, "ITEM-001")
        self.assertIn("spojování", proposals[0].reasoning)
        self.assertEqual(proposals[1].parent_export_id, "ASSESSMENT-001")

    def test_import_accept_reject_and_apply(self) -> None:
        target = self.export_dir / "import.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        proposals = ai_peer_review_service.parse_response(SAMPLE_RESPONSE)
        accepted = [proposals[0]]
        rejected = [proposals[1]]

        before_hazards = len(
            identified_hazard_service.get_for_identification(
                self.identification.id,
                include_inactive=False,
            )
        )
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.identification.id,
            review_id=export_result.review.id,
            response_text=SAMPLE_RESPONSE,
            ai_model="ChatGPT",
            accepted=accepted,
            rejected=rejected,
        )
        self.assertEqual(updated.ai_model, "ChatGPT")
        self.assertEqual(updated.accepted_count, 1)
        self.assertEqual(updated.rejected_count, 1)
        self.assertEqual(updated.unassigned_count, 0)
        self.assertIn("Přimáčknutí mezi vozy", updated.response_text)

        after_hazards = identified_hazard_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertEqual(len(after_hazards), before_hazards + 1)
        linked = next(
            row for row in after_hazards if row.hazard.name == "Přimáčknutí mezi vozy"
        )
        self.assertEqual(linked.hazard.inventory_item_id, self.item.id)

    def test_import_missing_parent_becomes_unassigned(self) -> None:
        target = self.export_dir / "unassigned.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        proposal = AiProposal(
            area="Nebezpečí",
            name="Orphan hazard",
            reasoning="Bez platného rodiče",
            parent_export_id="ITEM-999",
        )
        before_hazards = len(
            identified_hazard_service.get_for_identification(
                self.identification.id,
                include_inactive=False,
            )
        )
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.identification.id,
            review_id=export_result.review.id,
            response_text="test",
            ai_model="Claude",
            accepted=[proposal],
            rejected=[],
        )
        self.assertEqual(updated.accepted_count, 0)
        self.assertEqual(updated.unassigned_count, 1)
        after_hazards = identified_hazard_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertEqual(len(after_hazards), before_hazards)
        unassigned = ai_peer_review_service.get_unassigned_for_review(export_result.review.id)
        self.assertEqual(len(unassigned), 1)
        self.assertEqual(unassigned[0].name, "Orphan hazard")
        self.assertEqual(unassigned[0].parent_export_id, "ITEM-999")
        self.assertEqual(UNASSIGNED_PROPOSAL_STATUS_LABEL, "Nezařazený návrh")

    def test_import_never_attaches_to_first_item(self) -> None:
        """Bez parent_export_id se nebezpečí nesmí přilepit k prvnímu zdroji."""
        target = self.export_dir / "no_fallback.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        proposal = AiProposal(
            area="Nebezpečí",
            name="Bez rodiče",
            reasoning="Nesmí použít první položku",
            parent_export_id=None,
        )
        before = len(
            identified_hazard_service.get_for_identification(
                self.identification.id,
                include_inactive=False,
            )
        )
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.identification.id,
            review_id=export_result.review.id,
            response_text="test",
            ai_model="X",
            accepted=[proposal],
            rejected=[],
        )
        self.assertEqual(updated.accepted_count, 0)
        self.assertEqual(updated.unassigned_count, 1)
        after = identified_hazard_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertEqual(len(after), before)

    def test_export_stores_id_map(self) -> None:
        target = self.export_dir / "idmap.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        mapping = json.loads(result.review.export_id_map_json)
        self.assertEqual(mapping["ITEM-001"]["kind"], "item")
        self.assertEqual(mapping["ITEM-001"]["id"], self.item.id)
        self.assertEqual(mapping["HAZARD-001"]["id"], self.hazard.id)
        self.assertEqual(mapping["EVENT-001"]["id"], self.event.id)
        self.assertEqual(mapping["ASSESSMENT-001"]["id"], self.assessment.id)

    def test_dialog_has_peer_review_tab(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertIn(AI_PEER_REVIEW_TAB_TITLE, labels)
        self.assertTrue(dialog.tabs.isTabEnabled(5))
        self.assertTrue(dialog.ai_peer_review_widget.export_btn.isEnabled())
        self.assertTrue(dialog.ai_peer_review_widget.import_btn.isEnabled())

    def test_widget_lists_history(self) -> None:
        target = self.export_dir / "historie.zip"
        ai_peer_review_service.export_package(self.provider, self.identification.id, target)
        widget = AiPeerReviewWidget(
            provider=self.provider,
            show_responsible_person_option=True,
        )
        widget.set_source(self.identification.id)
        self.assertEqual(widget.table.rowCount(), 1)

    def test_options_dialog_default_unchecked(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog(show_responsible_person=True)
        self.assertFalse(dialog.include_responsible_person.isChecked())
        self.assertTrue(dialog.scope_full.isChecked())

    def test_provider_is_generic_source_type(self) -> None:
        self.assertEqual(self.provider.source_type, "hazard_identification")
        self.assertTrue(hasattr(self.provider, "build_export_content"))
        self.assertTrue(hasattr(self.provider, "apply_proposals"))


if __name__ == "__main__":
    unittest.main()
