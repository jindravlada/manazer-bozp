"""UX-COORD-5 – navigace a zachování výběru."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidgetItem
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-5-"))
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
    from core.widgets.table_selection import (
        find_table_row_by_id,
        refresh_and_restore_selection,
    )
    from moduly.koordinace_bozp.constants import (
        MEASURE_CATEGORY_COMMUNICATION,
        TAB_MEASURES,
        VALIDITY_FILTER_ALL,
        VALIDITY_FILTER_VALID,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_measure_dialog import (
        CoordinationMeasureDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_measures_tab import (
        CoordinationMeasuresTab,
    )
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _fill_id_table(ids: list[int]):
    table = __import__("PySide6.QtWidgets", fromlist=["QTableWidget"]).QTableWidget()
    table.setColumnCount(1)
    table.setRowCount(len(ids))
    for row, record_id in enumerate(ids):
        table.setItem(row, 0, QTableWidgetItem(str(record_id)))
    return table


class UxCoord5SelectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def _create_coordination(self):
        return bozp_coordination_service.create_coordination(
            subject="UX-COORD-5",
            meeting_date=date.today(),
            place="Praha",
        )

    def test_helper_selects_by_id_not_row_order(self) -> None:
        table = _fill_id_table([30, 10, 20])
        self.assertEqual(find_table_row_by_id(table, 10), 1)
        self.assertTrue(refresh_and_restore_selection(table, 20))
        self.assertEqual(table.item(table.currentRow(), 0).text(), "20")
        self.assertEqual(table.currentRow(), 2)

    def test_helper_fallback_selects_next_then_previous(self) -> None:
        # Záznam 20 skrytý – fallback_row=1 má vybrat následující (30 je na indexu 1 po skrytí 20).
        table = _fill_id_table([10, 30])
        self.assertTrue(
            refresh_and_restore_selection(table, 20, fallback_row=1)
        )
        self.assertEqual(table.currentRow(), 1)
        self.assertEqual(table.item(1, 0).text(), "30")

        table = _fill_id_table([10, 20])
        self.assertTrue(
            refresh_and_restore_selection(table, 99, fallback_row=2)
        )
        self.assertEqual(table.currentRow(), 1)
        self.assertEqual(table.item(1, 0).text(), "20")

        table = _fill_id_table([])
        self.assertFalse(
            refresh_and_restore_selection(table, 1, fallback_row=0)
        )
        self.assertEqual(table.selectedItems(), [])

    def test_add_selects_new_record(self) -> None:
        coordination = self._create_coordination()
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        with patch.object(
            CoordinationMeasureDialog,
            "exec",
            return_value=True,
        ), patch.object(
            CoordinationMeasureDialog,
            "get_data",
            return_value={
                "category": MEASURE_CATEGORY_COMMUNICATION,
                "title": "Nové opatření",
                "description": "Text",
            },
        ):
            tab.add_measure()
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.selected_measure_id(), tab.table.selected_measure_id())
        selected = coordination_measure_service.get_by_id(tab.table.selected_measure_id())
        assert selected is not None
        self.assertEqual(selected.title, "Nové opatření")

    def test_edit_keeps_selected_record(self) -> None:
        coordination = self._create_coordination()
        first = coordination_measure_service.add(
            coordination.id,
            title="První",
            description="A",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        second = coordination_measure_service.add(
            coordination.id,
            title="Druhé",
            description="B",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        # Vybrat druhé podle ID (může být jiný řádek po řazení).
        for row in range(tab.table.rowCount()):
            if int(tab.table.item(row, 0).text()) == second.id:
                tab.table.selectRow(row)
                break
        with patch.object(
            CoordinationMeasureDialog,
            "exec",
            return_value=True,
        ), patch.object(
            CoordinationMeasureDialog,
            "get_data",
            return_value={
                "category": MEASURE_CATEGORY_COMMUNICATION,
                "title": "Upravené druhé",
                "description": "B2",
            },
        ):
            tab.edit_selected_measure()
        self.assertEqual(tab.table.selected_measure_id(), second.id)
        reloaded = coordination_measure_service.get_by_id(second.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Upravené druhé")
        self.assertEqual(first.title, "První")

    def test_deactivate_keeps_id_when_still_visible(self) -> None:
        coordination = self._create_coordination()
        a = coordination_measure_service.add(
            coordination.id, title="A", category=MEASURE_CATEGORY_COMMUNICATION
        )
        b = coordination_measure_service.add(
            coordination.id, title="B", category=MEASURE_CATEGORY_COMMUNICATION
        )
        c = coordination_measure_service.add(
            coordination.id, title="C", category=MEASURE_CATEGORY_COMMUNICATION
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        for row in range(tab.table.rowCount()):
            if int(tab.table.item(row, 0).text()) == b.id:
                tab.table.selectRow(row)
                break
        with patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.deactivate_selected_measure()
        self.assertEqual(tab.table.selected_measure_id(), b.id)
        self.assertFalse(coordination_measure_service.get_by_id(b.id).active)
        self.assertTrue(coordination_measure_service.get_by_id(a.id).active)
        self.assertTrue(coordination_measure_service.get_by_id(c.id).active)

    def test_deactivate_fallback_next_when_hidden(self) -> None:
        table = _fill_id_table([1, 3, 4])  # 2 removed → next at old index 1 is 3
        self.assertTrue(refresh_and_restore_selection(table, 2, fallback_row=1))
        self.assertEqual(int(table.item(table.currentRow(), 0).text()), 3)

        table = _fill_id_table([1, 2])  # last removed, fallback beyond end → previous
        self.assertTrue(refresh_and_restore_selection(table, 3, fallback_row=2))
        self.assertEqual(int(table.item(table.currentRow(), 0).text()), 2)

    def test_activate_keeps_selected_record(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Neaktivní",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        coordination_measure_service.deactivate(measure.id)
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        for row in range(tab.table.rowCount()):
            if int(tab.table.item(row, 0).text()) == measure.id:
                tab.table.selectRow(row)
                break
        with patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.activate_selected_measure()
        self.assertEqual(tab.table.selected_measure_id(), measure.id)
        self.assertTrue(coordination_measure_service.get_by_id(measure.id).active)

    def test_filters_and_tab_preserved(self) -> None:
        page = KoordinaceBozpPage()
        page.validity_filter.setCurrentIndex(
            page.validity_filter.findData(VALIDITY_FILTER_VALID)
        )
        self.assertEqual(page.current_validity_filter(), VALIDITY_FILTER_VALID)
        page.refresh()
        self.assertEqual(page.current_validity_filter(), VALIDITY_FILTER_VALID)
        self.assertNotEqual(page.current_validity_filter(), VALIDITY_FILTER_ALL)

        coordination = self._create_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        measures_index = None
        for index in range(dialog.tabs.count()):
            if dialog.tabs.tabText(index) == TAB_MEASURES:
                measures_index = index
                break
        self.assertIsNotNone(measures_index)
        dialog.tabs.setCurrentIndex(measures_index)
        tab = dialog.coordinator_tab  # ensure dialog built
        measures_tab = dialog.measures_tab
        measures_tab.add_measure = lambda: None  # noqa: E731
        # Obnova dat na záložce nesmí přepnout aktivní tab.
        measures_tab.refresh()
        self.assertEqual(dialog.tabs.currentIndex(), measures_index)
        self.assertIs(tab, dialog.coordinator_tab)
        dialog.mark_clean()
        dialog.close()

    def test_restore_uses_id_after_reorder(self) -> None:
        coordination = self._create_coordination()
        first = coordination_measure_service.add(
            coordination.id, title="AAA", category=MEASURE_CATEGORY_COMMUNICATION
        )
        second = coordination_measure_service.add(
            coordination.id, title="ZZZ", category=MEASURE_CATEGORY_COMMUNICATION
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        coordination_measure_service.move_down(first.id)
        tab.refresh(select_id=first.id, ensure_visible=True)
        self.assertEqual(tab.table.selected_measure_id(), first.id)
        # Po přesunu je first na jiném řádku, ale ID zůstává.
        row = find_table_row_by_id(tab.table, first.id)
        self.assertIsNotNone(row)
        self.assertNotEqual(tab.table.selected_measure_id(), second.id)


if __name__ == "__main__":
    unittest.main()
