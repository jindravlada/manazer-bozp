"""Fáze R11.7 – dávkový export AI podle zdrojů analýzy."""

from __future__ import annotations

import importlib
import io
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
        AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
        AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
        AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH,
        AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH,
        AI_PEER_REVIEW_ZIP_FILES,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.ai_peer_review_service import (
        AiPeerReviewError,
        ai_peer_review_service,
    )
    from core.ai_oponentni.sluzby.batch_planner import (
        ExportBranch,
        count_hierarchy_objects,
        plan_export_batches,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewExportOptionsDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
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


class BatchPlannerUnitTestCase(unittest.TestCase):
    def _branch(self, source_id: int, objects: int, *, name: str | None = None) -> ExportBranch:
        return ExportBranch(
            source_id=source_id,
            source_name=name or f"Zdroj {source_id}",
            object_count=objects,
            node={"export_id": f"ITEM-{source_id:03d}", "name": name or f"Zdroj {source_id}"},
        )

    def test_ten_sources_one_batch(self) -> None:
        branches = [self._branch(index, 5) for index in range(1, 11)]
        plans = plan_export_batches(branches)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].source_count, 10)
        self.assertEqual(plans[0].batch_number, 1)

    def test_eleven_sources_two_batches(self) -> None:
        branches = [self._branch(index, 1) for index in range(1, 12)]
        plans = plan_export_batches(branches)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].source_count, 10)
        self.assertEqual(plans[1].source_count, 1)
        self.assertEqual(plans[0].batch_number, 1)
        self.assertEqual(plans[1].batch_number, 2)

    def test_object_limit_splits_batches(self) -> None:
        branches = [
            self._branch(1, 120),
            self._branch(2, 120),
        ]
        plans = plan_export_batches(branches, max_sources=10, max_objects=200)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].object_count, 120)
        self.assertEqual(plans[1].object_count, 120)

    def test_oversized_branch_stays_whole(self) -> None:
        big_node = {
            "export_id": "ITEM-001",
            "name": "Velký",
            "events": [{"assessments": []} for _ in range(250)],
        }
        self.assertEqual(count_hierarchy_objects(big_node), 251)
        branches = [
            ExportBranch(
                source_id=1,
                source_name="Velký",
                object_count=251,
                node=big_node,
            ),
            self._branch(2, 10),
        ]
        plans = plan_export_batches(branches, max_objects=200)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].source_count, 1)
        self.assertTrue(plans[0].recommended_limit_exceeded)
        self.assertEqual(plans[0].branches[0].node["events"].__len__(), 250)
        self.assertFalse(plans[1].recommended_limit_exceeded)

    def test_named_limit_constants(self) -> None:
        self.assertEqual(AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH, 10)
        self.assertEqual(AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH, 200)


class AiPeerReviewPhaseR117TestCase(unittest.TestCase):
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
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R117",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R117",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Eva", last_name="Testová")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.provider = hazard_identification_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp())

    def _create_items(self, count: int) -> list:
        items = []
        for index in range(1, count + 1):
            items.append(
                hazard_inventory_item_service.create_item(
                    hazard_identification_id=self.identification.id,
                    category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                    name=f"Zdroj {index:02d}",
                )
            )
        return items

    def test_schema_columns_for_batches(self) -> None:
        columns = _table_columns("ai_peer_reviews")
        self.assertIn("export_scope", columns)
        self.assertIn("batch_count", columns)
        self.assertIn("selected_source_count", columns)
        self.assertIn("total_object_count", columns)
        batch_columns = _table_columns("ai_peer_review_batches")
        self.assertIn("batch_number", batch_columns)
        self.assertIn("source_count", batch_columns)
        self.assertIn("object_count", batch_columns)
        self.assertIn("filename", batch_columns)

    def test_single_batch_for_at_most_ten_sources(self) -> None:
        self._create_items(10)
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertEqual(content.batch_count, 1)
        self.assertEqual(len(content.batches), 1)
        self.assertEqual(content.batches[0].source_count, 10)
        self.assertEqual(content.export_scope, AI_PEER_REVIEW_EXPORT_SCOPE_FULL)

        target = self.export_dir / "one.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
        self.assertEqual(result.review.batch_count, 1)
        self.assertEqual(result.batch_count, 1)

    def test_eleven_sources_split_into_two_batches(self) -> None:
        self._create_items(11)
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertEqual(content.batch_count, 2)
        self.assertEqual(content.batches[0].batch_number, 1)
        self.assertEqual(content.batches[1].batch_number, 2)
        self.assertEqual(content.batches[0].batch_number, 1)
        for batch in content.batches:
            self.assertEqual(batch.zadani_json["batch_count"], 2)
            self.assertEqual(batch.zadani_json["batch_number"], batch.batch_number)
            self.assertEqual(batch.zadani_json["export_scope"], "full")

        target = self.export_dir / "multi.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
        )
        with zipfile.ZipFile(target, "r") as zf:
            names = set(zf.namelist())
            self.assertEqual(
                names,
                {"davka_001.zip", "davka_002.zip", "prehled_davek.txt"},
            )
            overview = zf.read("prehled_davek.txt").decode("utf-8")
            self.assertIn(self.identification.identification_number, overview)
            self.assertIn("Celkový počet dávek: 2", overview)
            self.assertIn("Zdroj 01", overview)
            self.assertIn("Zdroj 11", overview)
            self.assertIn(str(AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH), overview)
            self.assertIn(str(AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH), overview)

            for batch_name in ("davka_001.zip", "davka_002.zip"):
                with zipfile.ZipFile(io.BytesIO(zf.read(batch_name)), "r") as inner:
                    self.assertEqual(set(inner.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
                    zadani = json.loads(inner.read("zadani.json").decode("utf-8"))
                    self.assertEqual(zadani["batch_count"], 2)
                    self.assertIn("source_count", zadani)
                    self.assertIn("object_count", zadani)
                    self.assertIn("recommended_limit_exceeded", zadani)

        reviews = ai_peer_review_service.get_for_source(
            SOURCE_TYPE_HAZARD_IDENTIFICATION,
            self.identification.id,
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].id, result.review.id)
        self.assertEqual(reviews[0].batch_count, 2)
        batches = ai_peer_review_service.get_batches_for_review(result.review.id)
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0].filename, "davka_001.zip")
        self.assertEqual(batches[1].filename, "davka_002.zip")

    def test_export_ids_unique_across_batches(self) -> None:
        self._create_items(11)
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        ids_batch1 = {
            item["export_id"] for item in content.batches[0].zadani_json["workplace_analysis"]
        }
        ids_batch2 = {
            item["export_id"] for item in content.batches[1].zadani_json["workplace_analysis"]
        }
        self.assertTrue(ids_batch1.isdisjoint(ids_batch2))
        self.assertIn("ITEM-001", ids_batch1)
        self.assertIn("ITEM-011", ids_batch2)
        # Mapa obsahuje všechny exportní ID z obou dávek
        for export_id in ids_batch1 | ids_batch2:
            self.assertIn(export_id, content.export_id_map)

    def test_hierarchy_branch_kept_in_one_batch(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Kořen",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=item.id,
            name="Událost větve",
        )
        # doplnit dalších 10 prázdných zdrojů → dvě dávky, větev musí zůstat beze změny
        self._create_items(10)
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertEqual(content.batch_count, 2)
        found = None
        for batch in content.batches:
            for node in batch.zadani_json["workplace_analysis"]:
                if node["name"] == "Kořen":
                    found = node
                    self.assertNotIn("hazards", node)
                    self.assertEqual(len(node["events"]), 1)
                    self.assertEqual(node["events"][0]["name"], "Událost větve")
        self.assertIsNotNone(found)
        event_names = [
            event_node["name"]
            for batch in content.batches
            for node in batch.zadani_json["workplace_analysis"]
            for event_node in node["events"]
        ]
        self.assertEqual(event_names.count("Událost větve"), 1)
        self.assertEqual(content.export_id_map[found["export_id"]]["id"], item.id)
        self.assertEqual(
            content.export_id_map[found["events"][0]["export_id"]]["id"],
            event.id,
        )

    def test_oversized_branch_exported_alone(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Nadlimitní",
        )
        for index in range(AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH):
            hazard_event_service.create_event(
                hazard_identification_id=self.identification.id,
                inventory_item_id=item.id,
                name=f"E{index}",
            )
        small = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Malý",
        )
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertGreaterEqual(content.batch_count, 2)
        oversized = next(
            batch for batch in content.batches if batch.recommended_limit_exceeded
        )
        self.assertEqual(oversized.source_count, 1)
        self.assertEqual(oversized.source_names, ["Nadlimitní"])
        self.assertTrue(oversized.zadani_json["recommended_limit_exceeded"])
        self.assertGreater(oversized.object_count, AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH)
        small_batch = next(
            batch
            for batch in content.batches
            if small.name in batch.source_names
        )
        self.assertFalse(small_batch.recommended_limit_exceeded)

    def test_selected_sources_scope(self) -> None:
        items = self._create_items(5)
        selected = [items[1].id, items[3].id]
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(
                export_scope=AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
                selected_source_ids=selected,
            ),
        )
        self.assertEqual(content.export_scope, AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED)
        self.assertEqual(content.selected_source_count, 2)
        self.assertEqual(content.batch_count, 1)
        names = [node["name"] for node in content.batches[0].zadani_json["workplace_analysis"]]
        self.assertEqual(names, ["Zdroj 02", "Zdroj 04"])
        self.assertEqual(content.batches[0].zadani_json["export_scope"], "selected")

        target = self.export_dir / "selected.zip"
        result = ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
            options=AiPeerReviewExportOptions(
                export_scope=AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
                selected_source_ids=selected,
            ),
        )
        self.assertEqual(result.review.export_scope, "selected")
        self.assertEqual(result.review.selected_source_count, 2)

    def test_empty_active_sources_no_export(self) -> None:
        with self.assertRaises(AiPeerReviewError) as ctx:
            self.provider.build_export_content(
                self.identification.id,
                options=AiPeerReviewExportOptions(),
            )
        self.assertIn("aktivní zdroj", str(ctx.exception).casefold())

        with self.assertRaises(AiPeerReviewError):
            ai_peer_review_service.export_package(
                self.provider,
                self.identification.id,
                self.export_dir / "empty.zip",
            )
        self.assertFalse((self.export_dir / "empty.zip").exists())
        self.assertEqual(
            ai_peer_review_service.get_for_source(
                SOURCE_TYPE_HAZARD_IDENTIFICATION,
                self.identification.id,
            ),
            [],
        )

    def test_options_dialog_defaults_to_full_scope(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog(
            source_choices=[],
        )
        self.assertTrue(dialog.scope_full.isChecked())
        self.assertFalse(dialog.scope_selected.isChecked())
        self.assertFalse(dialog.source_list.isEnabled())
        options = dialog.get_options()
        self.assertEqual(options.export_scope, AI_PEER_REVIEW_EXPORT_SCOPE_FULL)
        self.assertEqual(options.opponent_role, "experienced_safety_technician")
        self.assertTrue(options.objectives)
        self.assertEqual(options.focus_areas, [])


if __name__ == "__main__":
    unittest.main()
