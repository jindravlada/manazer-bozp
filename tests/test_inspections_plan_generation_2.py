"""INSPECTIONS-PLAN-GENERATION-2: jen Provozy a roční číslování."""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp(prefix="inspections-plan-gen-2-"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import ENTITY_PROVERKY
    from core.shared.sluzby.control_result_service import control_result_service
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_generation_service import (
        bozp_inspection_generation_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
    from moduly.proverky.ui.generate_inspections_dialog import GenerateInspectionsDialog
    from moduly.proverky.ui.proverky_page import ProverkyPage, _InspectionRow

# Kanonická testovací sada hierarchie: 2 aktivní Provozy.
CANONICAL_ACTIVE_OPERATION_COUNT = 2


class InspectionsPlanGeneration2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        for workplace in list(settings_service.get_workplaces(include_inactive=True)):
            workplace.active = False
            settings_service.repository.save_workplace(workplace)

    def _operation(self, name: str, *, active: bool = True, **fields):
        return settings_service.save_workplace(
            name=name,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
            active=active,
            **fields,
        )

    def _workplace(self, name: str, parent_id: int, *, active: bool = True):
        return settings_service.save_workplace(
            name=name,
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=parent_id,
            active=active,
        )

    def _part(self, name: str, parent_id: int, *, active: bool = True):
        return settings_service.save_workplace(
            name=name,
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=parent_id,
            active=active,
        )

    def _canonical_hierarchy(self):
        first = self._operation("Provoz Alpha")
        second = self._operation("Provoz Beta")
        inactive = self._operation("Provoz Neaktivní", active=False)
        workplace = self._workplace("Pracoviště Alpha 1", first.id)
        part = self._part("Část Alpha 1a", workplace.id)
        return {
            "operations": (first, second),
            "inactive": inactive,
            "workplace": workplace,
            "part": part,
        }

    def test_01_active_operation_is_generated(self) -> None:
        operation = self._operation("Provoz Alpha")
        result = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0].workplace_id, operation.id)
        self.assertEqual(result.created[0].year, 2027)
        self.assertEqual(result.created[0].status, "Plánováno")

    def test_02_subordinate_workplace_is_not_generated(self) -> None:
        operation = self._operation("Provoz Beta")
        workplace = self._workplace("Pracoviště Beta 1", operation.id)
        result = bozp_inspection_generation_service.generate_for_year(2027)
        workplace_ids = {item.workplace_id for item in result.created}
        self.assertIn(operation.id, workplace_ids)
        self.assertNotIn(workplace.id, workplace_ids)

    def test_03_workplace_part_is_not_generated(self) -> None:
        operation = self._operation("Provoz Gama")
        workplace = self._workplace("Pracoviště Gama 1", operation.id)
        part = self._part("Část Gama 1a", workplace.id)
        result = bozp_inspection_generation_service.generate_for_year(2027)
        workplace_ids = {item.workplace_id for item in result.created}
        self.assertEqual(workplace_ids, {operation.id})
        self.assertNotIn(part.id, workplace_ids)

    def test_04_inactive_operation_is_not_generated(self) -> None:
        inactive = self._operation("Provoz Neaktivní", active=False)
        result = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(result.created, ())
        self.assertEqual(result.skipped_existing, 0)
        self.assertIsNone(next(
            (item for item in bozp_inspection_service.get_all() if item.workplace_id == inactive.id),
            None,
        ))

    def test_05_two_active_operations_create_two_inspections(self) -> None:
        hierarchy = self._canonical_hierarchy()
        result = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(CANONICAL_ACTIVE_OPERATION_COUNT, 2)
        self.assertEqual(len(result.created), CANONICAL_ACTIVE_OPERATION_COUNT)
        self.assertEqual(result.skipped_existing, 0)
        self.assertEqual(
            {item.workplace_id for item in result.created},
            {hierarchy["operations"][0].id, hierarchy["operations"][1].id},
        )
        self.assertNotIn(hierarchy["inactive"].id, {item.workplace_id for item in result.created})
        self.assertNotIn(hierarchy["workplace"].id, {item.workplace_id for item in result.created})
        self.assertNotIn(hierarchy["part"].id, {item.workplace_id for item in result.created})

    def test_06_repeat_generation_is_idempotent(self) -> None:
        self._operation("Provoz Delta")
        first = bozp_inspection_generation_service.generate_for_year(2027)
        second = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(len(first.created), 1)
        self.assertEqual(len(second.created), 0)
        self.assertEqual(second.skipped_existing, 1)
        self.assertEqual(len(bozp_inspection_service.get_for_year(2027)), 1)

    def test_07_child_inspection_does_not_block_parent_operation(self) -> None:
        operation = self._operation("Provoz Epsilon")
        workplace = self._workplace("Pracoviště Epsilon 1", operation.id)
        bozp_inspection_service.create_inspection(
            year=2027,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        result = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0].workplace_id, operation.id)

    def test_08_first_number_of_2027_is_independent_of_db_id(self) -> None:
        dummy = bozp_inspection_service.create_inspection(
            year=2026,
            workplace_name="Jiný rok",
        )
        self._operation("Provoz Zeta")
        result = bozp_inspection_generation_service.generate_for_year(2027)
        created = result.created[0]
        self.assertGreater(created.id, dummy.id)
        self.assertNotEqual(created.number, f"{created.id}/2027")
        self.assertEqual(created.number, "1/2027")

    def test_09_next_number_continues_in_same_year(self) -> None:
        self._operation("Provoz Eta A")
        self._operation("Provoz Eta B")
        result = bozp_inspection_generation_service.generate_for_year(2027)
        numbers = [item.number for item in result.created]
        self.assertEqual(numbers, ["1/2027", "2/2027"])

    def test_10_year_2028_starts_again_at_one(self) -> None:
        self._operation("Provoz Theta")
        first = bozp_inspection_generation_service.generate_for_year(2027)
        second = bozp_inspection_generation_service.generate_for_year(2028)
        self.assertEqual(first.created[0].number, "1/2027")
        self.assertEqual(second.created[0].number, "1/2028")

    def test_11_gap_uses_maximum_plus_one(self) -> None:
        first = bozp_inspection_service.create_inspection(year=2027, workplace_name="A")
        second = bozp_inspection_service.create_inspection(year=2027, workplace_name="B")
        self.assertEqual(first.number, "1/2027")
        self.assertEqual(second.number, "2/2027")
        bozp_inspection_service.delete_inspection(first.id)
        third = bozp_inspection_service.create_inspection(year=2027, workplace_name="C")
        self.assertEqual(third.number, "3/2027")

    def test_12_manual_and_bulk_share_numbering(self) -> None:
        self._operation("Provoz Iota")
        manual = bozp_inspection_service.create_inspection(year=2027, workplace_name="Ruční")
        bulk = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(manual.number, "1/2027")
        self.assertEqual(bulk.created[0].number, "2/2027")

    def test_13_generation_does_not_create_results_or_snapshots(self) -> None:
        self._operation("Provoz Kappa")
        result = bozp_inspection_generation_service.generate_for_year(2027)
        inspection_id = result.created[0].id
        self.assertEqual(
            control_result_service.get_for_entity(ENTITY_PROVERKY, inspection_id),
            [],
        )
        with get_session() as session:
            tables = {
                row[0]
                for row in session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            if "audit_question_snapshots" in tables:
                snapshot_count = session.execute(
                    text("SELECT COUNT(*) FROM audit_question_snapshots WHERE audit_id = :id"),
                    {"id": inspection_id},
                ).scalar()
                self.assertEqual(snapshot_count, 0)

    def test_14_startup_and_refresh_do_not_generate(self) -> None:
        self._operation("Provoz Lambda")
        self.assertEqual(bozp_inspection_service.get_all(), [])
        initialize_database()
        self.assertEqual(bozp_inspection_service.get_all(), [])
        page = ProverkyPage()
        try:
            page.refresh()
        finally:
            page.close()
            page.deleteLater()
        self.assertEqual(bozp_inspection_service.get_all(), [])

    def test_15_overview_and_numeric_sort_still_work(self) -> None:
        from PySide6.QtCore import Qt

        low = bozp_inspection_service.create_inspection(year=2027, workplace_name="Nízký")
        high = bozp_inspection_service.create_inspection(year=2027, workplace_name="Vysoký")
        self.assertEqual(low.number, "1/2027")
        self.assertEqual(high.number, "2/2027")

        table = BozpInspectionTable()
        table.load_inspections(
            [
                _InspectionRow(high, counts={"total": 10, "zavady": 10}),
                _InspectionRow(low, counts={"total": 2, "zavady": 2}),
            ]
        )
        self.assertEqual(table.item(0, 1).text(), "2/2027")
        self.assertEqual(table.item(1, 1).text(), "1/2027")
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(table.item(0, 4).text(), "2")
        self.assertEqual(table.item(1, 4).text(), "10")
        table.sortItems(1, Qt.SortOrder.AscendingOrder)
        self.assertEqual(table.item(0, 1).text(), "1/2027")
        self.assertEqual(table.item(1, 1).text(), "2/2027")

    def test_16_ambiguous_level_is_skipped_and_logged(self) -> None:
        operation = self._operation("Provoz Máta")
        ambiguous = self._operation("Záznam bez typu")
        ambiguous.item_type = "neznamy_historicky"
        settings_service.repository.save_workplace(ambiguous)

        with self.assertLogs(
            "moduly.proverky.sluzby.bozp_inspection_generation_service",
            level=logging.WARNING,
        ) as captured:
            result = bozp_inspection_generation_service.generate_for_year(2027)

        self.assertEqual(len(result.created), 1)
        self.assertEqual(result.created[0].workplace_id, operation.id)
        self.assertTrue(any("nejednoznačná úroveň" in message for message in captured.output))

    def test_17_skipped_count_excludes_subordinates(self) -> None:
        hierarchy = self._canonical_hierarchy()
        first = bozp_inspection_generation_service.generate_for_year(2027)
        second = bozp_inspection_generation_service.generate_for_year(2027)
        self.assertEqual(len(first.created), CANONICAL_ACTIVE_OPERATION_COUNT)
        self.assertEqual(second.skipped_existing, CANONICAL_ACTIVE_OPERATION_COUNT)
        self.assertNotIn(hierarchy["workplace"].id, {item.workplace_id for item in first.created})

    def test_18_empty_year_restarts_at_one(self) -> None:
        created = bozp_inspection_service.create_inspection(year=2027, workplace_name="Dočasná")
        bozp_inspection_service.delete_inspection(created.id)
        again = bozp_inspection_service.create_inspection(year=2027, workplace_name="Nová")
        self.assertEqual(again.number, "1/2027")

    def test_19_dialog_summary_mentions_year_created_and_skipped_operations(self) -> None:
        source = inspect.getsource(GenerateInspectionsDialog._generate)
        self.assertIn("rok {year}", source)
        self.assertIn("len(result.created)", source)
        self.assertIn("Přeskočeno provozů, které už plán mají", source)
        self.assertNotIn("pracovišť", source)
        self.assertNotIn("pracoviště", source.lower())


if __name__ == "__main__":
    unittest.main()
