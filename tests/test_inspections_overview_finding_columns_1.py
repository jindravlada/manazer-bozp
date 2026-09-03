"""INSPECTIONS-OVERVIEW-FINDING-COLUMNS-1: skutečné počty podle druhu Finding."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest

from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication

from sqlalchemy import event

_TMP = Path(tempfile.mkdtemp())

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.finding_service import finding_service
    from core.database.session import get_session

    from moduly.proverky.constants import (
        INSPECTION_STATUS_FILTER_VSE,
        INSPECTION_STATUS_DOKONCENO,
        YEAR_FILTER_VSE,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_table import BozpInspectionTable
    from moduly.proverky.ui.proverky_page import ProverkyPage
    from moduly.proverky import ui as proverky_ui_package
    import moduly.proverky.ui.proverky_page as page_module


def _read_int(table, row: int, column: int) -> int:
    item = table.item(row, column)
    if item is None:
        raise AssertionError(f"Missing table cell at row={row} col={column}")
    return int(item.text())


class InspectionsOverviewFindingColumnsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def _prepare_page(self) -> ProverkyPage:
        page = ProverkyPage()
        page.status_filter.setCurrentText(INSPECTION_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        return page

    def _row_index_by_inspection_id(self, page: ProverkyPage, inspection_id: int) -> int:
        for row in range(page.table.rowCount()):
            item = page.table.item(row, 0)
            if item and int(item.text()) == inspection_id:
                return row
        raise AssertionError(f"Inspection id={inspection_id} not found in table")

    def _column_indices(self) -> dict[str, int]:
        # 0 hidden ID
        return {
            "cislo": 1,
            "datum": 2,
            "pracoviste": 3,
            "celkem": 4,
            "zavady": 5,
            "nedostatky": 6,
            "poruseni": 7,
            "neshody": 8,
            "pkz": 9,
            "ostatni": 10,
            "stav": 11,
        }

    def _assert_finding_counts(
        self,
        table: BozpInspectionTable,
        row: int,
        *,
        celkem: int,
        zavady: int,
        nedostatky: int,
        poruseni: int,
        neshody: int,
        pkz: int,
        ostatni: int,
    ) -> None:
        cols = self._column_indices()
        self.assertEqual(_read_int(table, row, cols["celkem"]), celkem)
        self.assertEqual(_read_int(table, row, cols["zavady"]), zavady)
        self.assertEqual(_read_int(table, row, cols["nedostatky"]), nedostatky)
        self.assertEqual(_read_int(table, row, cols["poruseni"]), poruseni)
        self.assertEqual(_read_int(table, row, cols["neshody"]), neshody)
        self.assertEqual(_read_int(table, row, cols["pkz"]), pkz)
        self.assertEqual(_read_int(table, row, cols["ostatni"]), ostatni)
        self.assertEqual(
            zavady + nedostatky + poruseni + neshody + pkz + ostatni,
            celkem,
        )

    def test_01_table_does_not_contain_specialista_boZp(self) -> None:
        table = BozpInspectionTable()
        labels = [
            table.horizontalHeaderItem(i).text()
            for i in range(1, table.columnCount())
            if table.horizontalHeaderItem(i) is not None
        ]
        self.assertNotIn("Specialista BOZP", labels)

    def test_02_table_does_not_contain_nazev(self) -> None:
        table = BozpInspectionTable()
        labels = [
            table.horizontalHeaderItem(i).text()
            for i in range(1, table.columnCount())
            if table.horizontalHeaderItem(i) is not None
        ]
        self.assertNotIn("Název", labels)

    def test_03_table_does_not_use_legacy_zavady_aggregate(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="X",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Nedostatek",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=1,
            zavady=0,
            nedostatky=1,
            poruseni=0,
            neshody=0,
            pkz=0,
            ostatni=0,
        )
        page.close()

    def test_04_table_column_order_11_visible_columns(self) -> None:
        table = BozpInspectionTable()
        visible = [table.horizontalHeaderItem(i).text() for i in range(1, 12)]
        expected = [
            "Číslo",
            "Datum prověrky",
            "Pracoviště",
            "Celkem",
            "Závady",
            "Nedostatky",
            "Porušení",
            "Neshody",
            "PKZ",
            "Ostatní",
            "Stav",
        ]
        self.assertEqual(visible, expected)

    def test_05_canonical_finding_types_go_to_correct_columns(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="C",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Závada",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Nedostatek",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_PORUSENI_PREDPISU,
            description="Porušení",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="PKZ",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=5,
            zavady=1,
            nedostatky=1,
            poruseni=1,
            neshody=1,
            pkz=1,
            ostatni=0,
        )
        page.close()

    def test_06_pozorovani_and_zjisteni_go_to_ostatni(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="O",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_POZOROVANI,
            description="Pozorování",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=2,
            zavady=0,
            nedostatky=0,
            poruseni=0,
            neshody=0,
            pkz=0,
            ostatni=2,
        )
        page.close()

    def test_07_unknown_historical_finding_type_goes_to_ostatni(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="U",
        )

        with get_session() as session:
            session.add(
                Finding(
                    entity_type=ENTITY_PROVERKY,
                    entity_id=inspection.id,
                    finding_type="legacy_unknown_type_code",
                    status=FINDING_STATUS_VYPORADANO,
                    description="Legacy unknown type",
                    display_order=0,
                )
            )
            session.commit()

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=1,
            zavady=0,
            nedostatky=0,
            poruseni=0,
            neshody=0,
            pkz=0,
            ostatni=1,
        )
        page.close()

    def test_08_open_and_resolved_findings_are_counted(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="S",
        )
        for status in (
            FINDING_STATUS_OTEVRENE,
            FINDING_STATUS_V_PROCESU,
            FINDING_STATUS_VYPORADANO,
        ):
            finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZAVADA,
                description="Závada",
                status=status,
            )

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=3,
            zavady=3,
            nedostatky=0,
            poruseni=0,
            neshody=0,
            pkz=0,
            ostatni=0,
        )
        page.close()

    def test_09_control_example_12_equals_breakdown_sum(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="X1",
        )
        for _ in range(5):
            finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZAVADA,
                description="Závada",
                status=FINDING_STATUS_OTEVRENE,
            )
        for _ in range(5):
            finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZJISTENI,
                description="Zjištění",
                status=FINDING_STATUS_OTEVRENE,
            )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_POZOROVANI,
            description="Pozorování",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=12,
            zavady=5,
            nedostatky=0,
            poruseni=0,
            neshody=1,
            pkz=0,
            ostatni=6,
        )
        page.close()

    def test_10_category_sum_always_equals_total(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="X2",
        )
        for _ in range(2):
            finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_ZAVADA,
                description="Závada",
                status=FINDING_STATUS_OTEVRENE,
            )
        for _ in range(3):
            finding_service.create(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_NEDOSTATEK,
                description="Nedostatek",
                status=FINDING_STATUS_OTEVRENE,
            )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_PORUSENI_PREDPISU,
            description="Porušení",
            status=FINDING_STATUS_OTEVRENE,
        )

        with get_session() as session:
            session.add(
                Finding(
                    entity_type=ENTITY_PROVERKY,
                    entity_id=inspection.id,
                    finding_type="unknown_category_code",
                    status=FINDING_STATUS_OTEVRENE,
                    description="unknown",
                    display_order=0,
                )
            )
            session.commit()

        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)

        cols = self._column_indices()
        celkem = _read_int(page.table, row, cols["celkem"])
        zavady = _read_int(page.table, row, cols["zavady"])
        nedostatky = _read_int(page.table, row, cols["nedostatky"])
        poruseni = _read_int(page.table, row, cols["poruseni"])
        neshody = _read_int(page.table, row, cols["neshody"])
        pkz = _read_int(page.table, row, cols["pkz"])
        ostatni = _read_int(page.table, row, cols["ostatni"])
        self.assertEqual(zavady + nedostatky + poruseni + neshody + pkz + ostatni, celkem)
        page.close()

    def test_11_inspection_without_findings_shows_zeroes(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="Z0",
        )
        page = self._prepare_page()
        row = self._row_index_by_inspection_id(page, inspection.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=0,
            zavady=0,
            nedostatky=0,
            poruseni=0,
            neshody=0,
            pkz=0,
            ostatni=0,
        )
        page.close()

    def test_12_overview_uses_batch_loading_no_get_for_entity_in_loop(self) -> None:
        a = bozp_inspection_service.create_inspection(
            workplace_name="A",
            year=date.today().year,
            title="A",
        )
        b = bozp_inspection_service.create_inspection(
            workplace_name="B",
            year=date.today().year,
            title="B",
        )
        c = bozp_inspection_service.create_inspection(
            workplace_name="C",
            year=date.today().year,
            title="C",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            a.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="x",
            status=FINDING_STATUS_OTEVRENE,
        )
        # intentionally no findings for b/c

        page = ProverkyPage()
        page.status_filter.setCurrentText(INSPECTION_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))

        with (
            patch.object(page_module.finding_service, "get_for_entity", side_effect=AssertionError("N+1 get_for_entity called")),
            patch.object(
                page_module.finding_service,
                "get_for_entities",
                wraps=page_module.finding_service.get_for_entities,
            ) as get_for_entities_mock,
        ):
            page.refresh()

        self.assertEqual(get_for_entities_mock.call_count, 1)
        page.close()

    def test_13_overview_loading_does_not_write_to_db(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="W",
            year=date.today().year,
            title="R",
        )
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="x",
            status=FINDING_STATUS_OTEVRENE,
        )

        engine = session_module.engine
        statements: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            statements.append(statement.lstrip().upper())

        event.listen(engine, "before_cursor_execute", _capture)
        try:
            page = self._prepare_page()
            page.close()
        finally:
            event.remove(engine, "before_cursor_execute", _capture)

        self.assertFalse(
            any(
                stmt.startswith(("INSERT", "UPDATE", "DELETE"))
                for stmt in statements
            ),
            f"Unexpected write statements during refresh: {statements[:20]}",
        )

    def test_14_numeric_sorting_places_2_before_10(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                type(
                    "Row",
                    (),
                    {
                        "id": 1,
                        "number": "1",
                        "inspection_date": None,
                        "workplace_name": "A",
                        "findings_total_count": 2,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 2,
                        "status": "",
                    },
                )(),
                type(
                    "Row",
                    (),
                    {
                        "id": 10,
                        "number": "10",
                        "inspection_date": None,
                        "workplace_name": "B",
                        "findings_total_count": 10,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 10,
                        "status": "",
                    },
                )(),
                type(
                    "Row",
                    (),
                    {
                        "id": 2,
                        "number": "2",
                        "inspection_date": None,
                        "workplace_name": "C",
                        "findings_total_count": 1,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 1,
                        "status": "",
                    },
                )(),
            ]
        )

        # Celkem = column 4
        table.sortItems(4, Qt.SortOrder.AscendingOrder)

        ids_sorted = [int(table.item(row, 0).text()) for row in range(table.rowCount())]
        self.assertEqual(ids_sorted, [2, 1, 10])

    def test_15_date_sort_still_works(self) -> None:
        table = BozpInspectionTable()
        table.load_inspections(
            [
                type(
                    "Row",
                    (),
                    {
                        "id": 1,
                        "number": "1",
                        "inspection_date": date(2026, 3, 15),
                        "workplace_name": "A",
                        "findings_total_count": 0,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 0,
                        "status": "",
                    },
                )(),
                type(
                    "Row",
                    (),
                    {
                        "id": 2,
                        "number": "2",
                        "inspection_date": date(2026, 1, 5),
                        "workplace_name": "B",
                        "findings_total_count": 0,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 0,
                        "status": "",
                    },
                )(),
                type(
                    "Row",
                    (),
                    {
                        "id": 3,
                        "number": "3",
                        "inspection_date": date(2026, 7, 1),
                        "workplace_name": "C",
                        "findings_total_count": 0,
                        "zavady_count": 0,
                        "nedostatky_count": 0,
                        "poruseni_predpisu_count": 0,
                        "neshody_count": 0,
                        "pkz_count": 0,
                        "ostatni_count": 0,
                        "status": "",
                    },
                )(),
            ]
        )

        # Datum prověrky = column 2
        table.sortItems(2, Qt.SortOrder.AscendingOrder)

        ids_sorted = [int(table.item(row, 0).text()) for row in range(table.rowCount())]
        self.assertEqual(ids_sorted, [2, 1, 3])

    def test_16_double_click_opens_selected_inspection(self) -> None:
        inspection_a = bozp_inspection_service.create_inspection(
            workplace_name="A",
            year=date.today().year,
            title="A",
        )
        inspection_b = bozp_inspection_service.create_inspection(
            workplace_name="B",
            year=date.today().year,
            title="B",
        )
        page = self._prepare_page()
        row_b = self._row_index_by_inspection_id(page, inspection_b.id)

        # vyber jen jeden řádek, aby _selected_row_count() bylo == 1
        selection_model = page.table.selectionModel()
        selection_model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        selection_model.select(page.table.model().index(row_b, 0), flags)

        with patch.object(page, "open_inspection") as open_inspection_mock:
            page.table.doubleClicked.emit(page.table.model().index(row_b, 0))
            open_inspection_mock.assert_called_once_with(inspection_b.id)
        page.close()

    def _assert_fills_viewport_no_hscroll(self, table: BozpInspectionTable, *, width: int, height: int) -> None:
        page_width_before = table.viewport().width()
        table.setParent(None)
        self._app.processEvents()
        # viewport width se počítá až po show/resize rodiče; proto měříme po přeceněné stránce
        used = sum(table.columnWidth(i) for i in range(table.columnCount()))
        viewport = table.viewport().width()
        self.assertGreater(viewport, 0)
        self.assertLessEqual(abs(used - viewport), 8, f"used={used} viewport={viewport} before={page_width_before}")
        self.assertEqual(table.horizontalScrollBar().maximum(), 0)

    def test_17_viewports_filled_at_1600(self) -> None:
        page = self._prepare_page()
        page.resize(1600, 900)
        page.show()
        for _ in range(3):
            self._app.processEvents()

        used = sum(page.table.columnWidth(i) for i in range(page.table.columnCount()))
        viewport = page.table.viewport().width()
        self.assertGreater(viewport, 0)
        self.assertLessEqual(abs(used - viewport), 8)
        self.assertEqual(page.table.horizontalScrollBar().maximum(), 0)

        header = page.table.horizontalHeader()
        for column in range(page.table.columnCount() - 1):
            right = header.sectionViewportPosition(column) + header.sectionSize(column)
            nxt = header.sectionViewportPosition(column + 1)
            self.assertLessEqual(right, nxt + 1)

        page.close()

    def test_18_viewports_filled_at_1920(self) -> None:
        page = self._prepare_page()
        page.resize(1920, 1080)
        page.show()
        for _ in range(3):
            self._app.processEvents()

        used = sum(page.table.columnWidth(i) for i in range(page.table.columnCount()))
        viewport = page.table.viewport().width()
        self.assertGreater(viewport, 0)
        self.assertLessEqual(abs(used - viewport), 8)
        self.assertEqual(page.table.horizontalScrollBar().maximum(), 0)

        header = page.table.horizontalHeader()
        for column in range(page.table.columnCount() - 1):
            right = header.sectionViewportPosition(column) + header.sectionSize(column)
            nxt = header.sectionViewportPosition(column + 1)
            self.assertLessEqual(right, nxt + 1)

        page.close()


if __name__ == "__main__":
    unittest.main()

