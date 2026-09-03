"""AUDITS-OVERVIEW-FINDING-COLUMNS-2: podrobný rozpis druhů Finding v přehledu."""

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

    from core.database.session import get_session
    from core.shared.constants import (
        CONTROL_RESULT_NEVYHOVUJE,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_BEZPROSTREDNI_PRICINA,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_OPATRENI,
        FINDING_TYPE_POKYN,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_SYSTEMOVA_PRICINA,
        FINDING_TYPE_ZAKLADNI_PRICINA,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_activity_statistics_service import (
        control_activity_statistics_service,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_STATUS_FILTER_VSE,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        YEAR_FILTER_VSE,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audit_table import (
        COL_AUDIT_DATE,
        COL_AUDIT_TYPE,
        COL_FINDINGS_TOTAL,
        COL_NEDOSTATKY,
        COL_NESHODY,
        COL_OSTATNI,
        COL_PKZ,
        COL_PORUSENI,
        COL_POZOROVANI,
        COL_STATUS,
        COL_WORKPLACE,
        COL_ZAVADY,
        COL_ZJISTENI,
        AuditTable,
    )
    from moduly.audity.ui.audity_page import AudityPage
    import moduly.audity.ui.audity_page as page_module
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service
    from tests.audit_v2a_test_support import prepare_v2_audit_create


_COUNT_COLUMNS = (
    COL_FINDINGS_TOTAL,
    COL_ZAVADY,
    COL_NEDOSTATKY,
    COL_PORUSENI,
    COL_NESHODY,
    COL_POZOROVANI,
    COL_ZJISTENI,
    COL_PKZ,
    COL_OSTATNI,
)

_VISIBLE_HEADERS = [
    "Číslo auditu",
    "Rok",
    "Plánovaný měsíc",
    "Auditovaný provoz",
    "Datum auditu",
    "Celkem",
    "Závady",
    "Nedostatky",
    "Porušení",
    "Neshody",
    "Pozorování",
    "Zjištění",
    "PKZ",
    "Ostatní",
    "Stav",
    "Typ auditu",
]


def _read_int(table, row: int, column: int) -> int:
    item = table.item(row, column)
    if item is None:
        raise AssertionError(f"Missing table cell at row={row} col={column}")
    return int(item.text())


def _dummy_row(
    *,
    row_id: int,
    number: str,
    total: int,
    zavady: int = 0,
    nedostatky: int = 0,
    poruseni: int = 0,
    neshody: int = 0,
    pozorovani: int = 0,
    zjisteni: int = 0,
    pkz: int = 0,
    ostatni: int = 0,
    workplace: str = "W",
    audit_date: date | None = None,
    status: str = "",
):
    return type(
        "Row",
        (),
        {
            "id": row_id,
            "number": number,
            "year": 2026,
            "planned_month": 4,
            "workplace_name": workplace,
            "audit_date": audit_date,
            "findings_total_count": total,
            "zavady_count": zavady,
            "nedostatky_count": nedostatky,
            "poruseni_count": poruseni,
            "neshody_count": neshody,
            "pozorovani_count": pozorovani,
            "zjisteni_count": zjisteni,
            "pkz_count": pkz,
            "ostatni_count": ostatni,
            "status": status,
            "audit_type": "Řádný",
        },
    )()


class AuditsOverviewFindingColumnsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def _prepare_page(self) -> AudityPage:
        page = AudityPage()
        page.status_filter.setCurrentText(AUDIT_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        return page

    def _row_index_by_audit_id(self, page: AudityPage, audit_id: int) -> int:
        for row in range(page.table.rowCount()):
            item = page.table.item(row, 0)
            if item and int(item.text()) == audit_id:
                return row
        raise AssertionError(f"Audit id={audit_id} not found in table")

    def _assert_finding_counts(
        self,
        table: AuditTable,
        row: int,
        *,
        celkem: int,
        zavady: int = 0,
        nedostatky: int = 0,
        poruseni: int = 0,
        neshody: int = 0,
        pozorovani: int = 0,
        zjisteni: int = 0,
        pkz: int = 0,
        ostatni: int = 0,
    ) -> None:
        self.assertEqual(_read_int(table, row, COL_FINDINGS_TOTAL), celkem)
        self.assertEqual(_read_int(table, row, COL_ZAVADY), zavady)
        self.assertEqual(_read_int(table, row, COL_NEDOSTATKY), nedostatky)
        self.assertEqual(_read_int(table, row, COL_PORUSENI), poruseni)
        self.assertEqual(_read_int(table, row, COL_NESHODY), neshody)
        self.assertEqual(_read_int(table, row, COL_POZOROVANI), pozorovani)
        self.assertEqual(_read_int(table, row, COL_ZJISTENI), zjisteni)
        self.assertEqual(_read_int(table, row, COL_PKZ), pkz)
        self.assertEqual(_read_int(table, row, COL_OSTATNI), ostatni)
        self.assertEqual(
            zavady
            + nedostatky
            + poruseni
            + neshody
            + pozorovani
            + zjisteni
            + pkz
            + ostatni,
            celkem,
        )

    def test_01_table_column_order(self) -> None:
        table = AuditTable()
        visible = [
            table.horizontalHeaderItem(i).text()
            for i in range(1, table.columnCount())
        ]
        self.assertEqual(visible, _VISIBLE_HEADERS)
        self.assertEqual(
            table.horizontalHeaderItem(COL_PORUSENI).toolTip(),
            "Porušení předpisů",
        )
        self.assertEqual(
            table.horizontalHeaderItem(COL_PKZ).toolTip(),
            "Příležitosti ke zlepšení",
        )
        tooltip = table.horizontalHeaderItem(COL_OSTATNI).toolTip().lower()
        self.assertIn("ostatn", tooltip)
        self.assertIn("příčinn", tooltip)
        self.assertIn("historick", tooltip)

    def test_02_each_canonical_type_goes_to_own_column(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        for finding_type, description in (
            (FINDING_TYPE_ZAVADA, "Závada"),
            (FINDING_TYPE_NEDOSTATEK, "Nedostatek"),
            (FINDING_TYPE_PORUSENI_PREDPISU, "Porušení"),
            (FINDING_TYPE_NESHODA, "Neshoda"),
            (FINDING_TYPE_POZOROVANI, "Pozorování"),
            (FINDING_TYPE_ZJISTENI, "Zjištění"),
            (FINDING_TYPE_PRILEZITOST, "PKZ"),
        ):
            finding_service.create(
                ENTITY_AUDITY,
                audit.id,
                finding_type=finding_type,
                description=description,
                status=FINDING_STATUS_OTEVRENE,
            )

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=7,
            zavady=1,
            nedostatky=1,
            poruseni=1,
            neshody=1,
            pozorovani=1,
            zjisteni=1,
            pkz=1,
            ostatni=0,
        )
        page.close()

    def test_03_causal_opatreni_and_pokyn_go_to_ostatni(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        for finding_type, description in (
            (FINDING_TYPE_BEZPROSTREDNI_PRICINA, "Bezprostřední"),
            (FINDING_TYPE_SYSTEMOVA_PRICINA, "Systémová"),
            (FINDING_TYPE_ZAKLADNI_PRICINA, "Základní"),
            (FINDING_TYPE_OPATRENI, "Opatření"),
            (FINDING_TYPE_POKYN, "Pokyn"),
        ):
            finding_service.create(
                ENTITY_AUDITY,
                audit.id,
                finding_type=finding_type,
                description=description,
                status=FINDING_STATUS_OTEVRENE,
            )

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=5,
            ostatni=5,
        )
        page.close()

    def test_04_unknown_historical_finding_type_goes_to_ostatni(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        with get_session() as session:
            session.add(
                Finding(
                    entity_type=ENTITY_AUDITY,
                    entity_id=audit.id,
                    finding_type="legacy_unknown_type_code",
                    status=FINDING_STATUS_VYPORADANO,
                    description="Legacy unknown type",
                    display_order=0,
                )
            )
            session.commit()

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=1,
            ostatni=1,
        )
        page.close()

    def test_05_control_example_sum_and_no_double_count(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        specs = (
            (FINDING_TYPE_ZAVADA, 2),
            (FINDING_TYPE_NEDOSTATEK, 1),
            (FINDING_TYPE_PORUSENI_PREDPISU, 1),
            (FINDING_TYPE_NESHODA, 2),
            (FINDING_TYPE_POZOROVANI, 1),
            (FINDING_TYPE_ZJISTENI, 3),
            (FINDING_TYPE_PRILEZITOST, 4),
            (FINDING_TYPE_SYSTEMOVA_PRICINA, 1),
        )
        for finding_type, count in specs:
            for index in range(count):
                finding_service.create(
                    ENTITY_AUDITY,
                    audit.id,
                    finding_type=finding_type,
                    description=f"{finding_type}-{index}",
                    status=FINDING_STATUS_OTEVRENE,
                )
        with get_session() as session:
            session.add(
                Finding(
                    entity_type=ENTITY_AUDITY,
                    entity_id=audit.id,
                    finding_type="legacy_unknown_type_code",
                    status=FINDING_STATUS_OTEVRENE,
                    description="unknown",
                    display_order=0,
                )
            )
            session.commit()

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=16,
            zavady=2,
            nedostatky=1,
            poruseni=1,
            neshody=2,
            pozorovani=1,
            zjisteni=3,
            pkz=4,
            ostatni=2,
        )
        category_sum = sum(
            _read_int(page.table, row, column)
            for column in _COUNT_COLUMNS
            if column != COL_FINDINGS_TOTAL
        )
        self.assertEqual(category_sum, _read_int(page.table, row, COL_FINDINGS_TOTAL))
        page.close()

    def test_06_all_finding_statuses_are_counted(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        for status in (
            FINDING_STATUS_OTEVRENE,
            FINDING_STATUS_V_PROCESU,
            FINDING_STATUS_VYPORADANO,
        ):
            finding_service.create(
                ENTITY_AUDITY,
                audit.id,
                finding_type=FINDING_TYPE_NESHODA,
                description="Neshoda",
                status=status,
            )

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=3,
            neshody=3,
        )
        page.close()

    def test_07_audit_without_findings_shows_zeroes(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(page.table, row, celkem=0)
        page.close()

    def test_08_overview_uses_batch_loading_no_n_plus_one(self) -> None:
        a = audit_service.create_audit(workplace_name="A", year=date.today().year)
        audit_service.create_audit(workplace_name="B", year=date.today().year)
        audit_service.create_audit(workplace_name="C", year=date.today().year)
        finding_service.create(
            ENTITY_AUDITY,
            a.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="x",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = AudityPage()
        page.status_filter.setCurrentText(AUDIT_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))

        with (
            patch.object(
                page_module.finding_service,
                "get_for_entity",
                side_effect=AssertionError("N+1 get_for_entity called"),
            ),
            patch.object(
                page_module.finding_service,
                "get_by_id",
                side_effect=AssertionError("N+1 get_by_id called"),
            ),
            patch.object(
                page_module.finding_service,
                "get_for_entities",
                wraps=page_module.finding_service.get_for_entities,
            ) as get_for_entities_mock,
        ):
            page.refresh()

        self.assertEqual(get_for_entities_mock.call_count, 1)
        args, _kwargs = get_for_entities_mock.call_args
        self.assertEqual(args[0], ENTITY_AUDITY)
        page.close()

    def test_09_overview_loading_does_not_write_or_create_tasks(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="x",
            status=FINDING_STATUS_OTEVRENE,
        )

        engine = session_module.engine
        statements: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            statements.append(statement.lstrip().upper())

        event.listen(engine, "before_cursor_execute", _capture)
        try:
            with patch.object(
                task_service,
                "create_task",
                side_effect=AssertionError("refresh created a task"),
            ):
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

    def test_10_nonzero_counts_are_bold_and_zeroes_are_grey(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            status=FINDING_STATUS_OTEVRENE,
        )

        page = self._prepare_page()
        row = self._row_index_by_audit_id(page, audit.id)
        for col in _COUNT_COLUMNS:
            item = page.table.item(row, col)
            self.assertIsNotNone(item)
            self.assertEqual(item.background().style(), Qt.BrushStyle.NoBrush)

        total_item = page.table.item(row, COL_FINDINGS_TOTAL)
        self.assertTrue(total_item.font().bold())
        self.assertEqual(total_item.foreground().style(), Qt.BrushStyle.NoBrush)
        neshody_item = page.table.item(row, COL_NESHODY)
        self.assertTrue(neshody_item.font().bold())
        self.assertEqual(neshody_item.foreground().style(), Qt.BrushStyle.NoBrush)

        zero_cols = (
            COL_ZAVADY,
            COL_NEDOSTATKY,
            COL_PORUSENI,
            COL_POZOROVANI,
            COL_ZJISTENI,
            COL_PKZ,
            COL_OSTATNI,
        )
        for col in zero_cols:
            item = page.table.item(row, col)
            self.assertFalse(item.font().bold())
            self.assertNotEqual(item.foreground().style(), Qt.BrushStyle.NoBrush)

        page.table.selectRow(row)
        for col in _COUNT_COLUMNS:
            item = page.table.item(row, col)
            self.assertEqual(item.background().style(), Qt.BrushStyle.NoBrush)
        page.close()

    def test_11_numeric_sorting_on_all_count_columns(self) -> None:
        table = AuditTable()
        table.load_audits(
            [
                _dummy_row(
                    row_id=1,
                    number="1/2026",
                    total=2,
                    zavady=2,
                    nedostatky=2,
                    poruseni=2,
                    neshody=2,
                    pozorovani=2,
                    zjisteni=2,
                    pkz=2,
                    ostatni=2,
                ),
                _dummy_row(
                    row_id=10,
                    number="10/2026",
                    total=10,
                    zavady=10,
                    nedostatky=10,
                    poruseni=10,
                    neshody=10,
                    pozorovani=10,
                    zjisteni=10,
                    pkz=10,
                    ostatni=10,
                ),
                _dummy_row(
                    row_id=2,
                    number="2/2026",
                    total=1,
                    zavady=1,
                    nedostatky=1,
                    poruseni=1,
                    neshody=1,
                    pozorovani=1,
                    zjisteni=1,
                    pkz=1,
                    ostatni=1,
                ),
            ]
        )

        for column in _COUNT_COLUMNS:
            table.sortItems(column, Qt.SortOrder.AscendingOrder)
            self.assertEqual(
                [int(table.item(row, 0).text()) for row in range(table.rowCount())],
                [2, 1, 10],
                msg=f"ascending column {column}",
            )
            table.sortItems(column, Qt.SortOrder.DescendingOrder)
            self.assertEqual(
                [int(table.item(row, 0).text()) for row in range(table.rowCount())],
                [10, 1, 2],
                msg=f"descending column {column}",
            )

    def test_12_double_click_opens_selected_audit(self) -> None:
        audit_a = audit_service.create_audit(workplace_name="A", year=date.today().year)
        audit_b = audit_service.create_audit(workplace_name="B", year=date.today().year)
        page = self._prepare_page()
        row_b = self._row_index_by_audit_id(page, audit_b.id)

        selection_model = page.table.selectionModel()
        selection_model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        selection_model.select(page.table.model().index(row_b, 0), flags)

        with patch.object(page, "open_audit") as open_audit_mock:
            page.table.doubleClicked.emit(page.table.model().index(row_b, 0))
            open_audit_mock.assert_called_once_with(audit_b.id)
        self.assertNotEqual(audit_a.id, audit_b.id)
        page.close()

    def test_13_viewports_filled_without_horizontal_scrollbar(self) -> None:
        page = self._prepare_page()
        measured: dict[tuple[int, int], dict[str, int]] = {}
        for width, height in ((1600, 900), (1920, 1080)):
            page.resize(width, height)
            page.show()
            for _ in range(3):
                self._app.processEvents()

            used = sum(page.table.columnWidth(i) for i in range(page.table.columnCount()))
            viewport = page.table.viewport().width()
            self.assertGreater(viewport, 0)
            self.assertLessEqual(abs(used - viewport), 8, f"{width}x{height}")
            self.assertEqual(page.table.horizontalScrollBar().maximum(), 0)

            header = page.table.horizontalHeader()
            for column in range(page.table.columnCount() - 1):
                right = header.sectionViewportPosition(column) + header.sectionSize(column)
                nxt = header.sectionViewportPosition(column + 1)
                self.assertLessEqual(right, nxt + 1)

            measured[(width, height)] = {
                "viewport": viewport,
                "used": used,
                **{
                    page.table.horizontalHeaderItem(i).text(): page.table.columnWidth(i)
                    for i in range(page.table.columnCount())
                },
            }
        print("AUDITS-OVERVIEW-FINDING-COLUMNS-2 widths:", measured)
        page.close()

    def test_14_program_visits_without_audit_row_are_not_shown(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Skutečný audit",
            year=date.today().year,
        )
        workplace = settings_service.save_workplace(name="Provoz návštěva", active=True)
        program = audit_program_service.create_program(
            name="Program bez zahájení",
            date_from=date(date.today().year, 1, 1),
            date_to=date(date.today().year + 2, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=12,
        )
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=workplace.id,
            planned_year=date.today().year,
            planned_month=4,
        )
        self.assertIsNone(visit.audit_id)

        page = self._prepare_page()
        ids = [
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        ]
        self.assertEqual(ids, [audit.id])
        workplaces = {
            page.table.item(row, COL_WORKPLACE).text()
            for row in range(page.table.rowCount())
        }
        self.assertNotIn(workplace.name, workplaces)
        page.close()

    def test_15_exports_manager_and_deferred_start_stay_functional(self) -> None:
        audit = audit_service.create_audit(workplace_name="W", year=date.today().year)
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Závada",
            status=FINDING_STATUS_VYPORADANO,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="proc",
                area_label="Proces",
                section_id="krit",
                section_label="Kritérium",
                control_point_id="q1",
                control_point_label="Otázka",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        before = control_activity_statistics_service.compute(ENTITY_AUDITY, audit.id)
        self.assertEqual(before.findings_total, 2)
        self.assertGreaterEqual(before.ratings_nevyhovuje, 1)

        page = AudityPage()
        page.status_filter.setCurrentText(AUDIT_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))

        with (
            patch(
                "moduly.audity.ui.audity_page.protokol_audit_service.open_for_audit",
                side_effect=AssertionError("overview generated protocol"),
            ),
            patch(
                "moduly.audity.ui.audity_page.protokol_audit_service.open_detailed_report_for_audit",
                side_effect=AssertionError("overview generated detailed report"),
            ),
            patch("moduly.audity.ui.audity_page.exec_maximized") as exec_mock,
        ):
            page.refresh()
            page.open_program_manager()
            exec_mock.assert_called_once()
            self.assertIsInstance(exec_mock.call_args[0][0], AuditProgramManagerDialog)

        row = self._row_index_by_audit_id(page, audit.id)
        self._assert_finding_counts(
            page.table,
            row,
            celkem=2,
            zavady=1,
            neshody=1,
        )

        after = control_activity_statistics_service.compute(ENTITY_AUDITY, audit.id)
        self.assertEqual(after.findings_total, before.findings_total)
        self.assertEqual(after.ratings_nevyhovuje, before.ratings_nevyhovuje)
        page.close()

        v2 = prepare_v2_audit_create()
        system_wp, operation_wp = v2.__enter__()
        try:
            program = audit_program_service.create_program(
                name="Program odloženého zahájení",
                date_from=date(2026, 4, 1),
                date_to=date(2029, 3, 31),
                standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
            )
            audit_program_service.add_workplace(
                program.id,
                workplace_id=operation_wp.id,
                workplace_name=operation_wp.name,
                audit_interval_months=6,
            )
            visit = audit_program_service.add_visit(
                program.id,
                workplace_id=operation_wp.id,
                planned_year=2026,
                planned_month=4,
                planned_date=date(2026, 4, 15),
            )
            self.assertIsNone(visit.audit_id)
            started = date(2026, 4, 12)
            created = audit_program_service.create_audit_from_visit(
                visit.id,
                started_at=started,
            )
            self.assertEqual(created.started_at, started)
            refreshed = audit_program_service.repository.get_visit(visit.id)
            assert refreshed is not None
            self.assertEqual(refreshed.audit_id, created.id)
        finally:
            v2.__exit__(None, None, None)

    def test_16_existing_identity_columns_remain(self) -> None:
        table = AuditTable()
        labels = [
            table.horizontalHeaderItem(i).text()
            for i in range(table.columnCount())
        ]
        self.assertEqual(labels[COL_AUDIT_DATE], "Datum auditu")
        self.assertEqual(labels[COL_STATUS], "Stav")
        self.assertEqual(labels[COL_AUDIT_TYPE], "Typ auditu")
        self.assertIn("Zjištění", labels)
        self.assertEqual(labels[COL_ZJISTENI], "Zjištění")


if __name__ == "__main__":
    unittest.main()
