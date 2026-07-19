"""UX-COORD-4d – doladění tabulek Koordinace BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QHeaderView, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-4d-"))
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
    from core.widgets.table_header_settings import (
        configure_and_persist_table_columns,
        coordination_table_settings,
        restore_table_header,
        save_table_header,
    )
    from moduly.koordinace_bozp.constants import (
        COORD_HEADER_EMPLOYERS,
        COORD_HEADER_LIST,
        COORD_HEADER_MEASURES,
        EMP_COL_NAME,
        MSR_COL_DESCRIPTION,
        COL_SUBJECT,
        MEASURE_CATEGORY_COMMUNICATION,
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
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable
    from moduly.koordinace_bozp.ui.coordination_employer_table import (
        CoordinationEmployerTable,
    )
    from moduly.koordinace_bozp.ui.coordination_measure_table import (
        CoordinationMeasureTable,
    )
    from moduly.koordinace_bozp.ui.coordination_measures_tab import (
        CoordinationMeasuresTab,
    )
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _send_key(widget, key: Qt.Key) -> None:
    event = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


class UxCoord4dTablesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        coordination_table_settings().clear()
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
            subject="UX-COORD-4d akce",
            meeting_date=date.today(),
            place="Praha",
        )

    def test_text_column_uses_stretch(self) -> None:
        list_table = BozpCoordinationTable()
        configure_and_persist_table_columns(
            list_table, "bozp_coordinations", COORD_HEADER_LIST
        )
        self.assertEqual(
            list_table.horizontalHeader().sectionResizeMode(COL_SUBJECT),
            QHeaderView.ResizeMode.Stretch,
        )

        emp_table = CoordinationEmployerTable()
        configure_and_persist_table_columns(
            emp_table, "coordination_employers", COORD_HEADER_EMPLOYERS
        )
        self.assertEqual(
            emp_table.horizontalHeader().sectionResizeMode(EMP_COL_NAME),
            QHeaderView.ResizeMode.Stretch,
        )

        msr_table = CoordinationMeasureTable()
        configure_and_persist_table_columns(
            msr_table, "coordination_measures", COORD_HEADER_MEASURES
        )
        self.assertEqual(
            msr_table.horizontalHeader().sectionResizeMode(MSR_COL_DESCRIPTION),
            QHeaderView.ResizeMode.Stretch,
        )

    def test_restore_saved_header_widths(self) -> None:
        table = CoordinationEmployerTable()
        configure_and_persist_table_columns(
            table, "coordination_employers", COORD_HEADER_EMPLOYERS
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(EMP_COL_NAME, QHeaderView.Interactive)
        table.setColumnWidth(EMP_COL_NAME, 333)
        save_table_header(table, COORD_HEADER_EMPLOYERS)

        other = CoordinationEmployerTable()
        configure_and_persist_table_columns(
            other, "coordination_employers", COORD_HEADER_EMPLOYERS
        )
        self.assertTrue(restore_table_header(other, COORD_HEADER_EMPLOYERS))
        self.assertEqual(other.columnWidth(EMP_COL_NAME), 333)

    def test_double_click_opens_edit(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Krátký",
            description="Text",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        tab.table.selectRow(0)
        with patch.object(tab, "edit_selected_measure") as edit_mock:
            tab.table.doubleClicked.disconnect()
            tab.table.doubleClicked.connect(tab.edit_selected_measure)
            index = tab.table.model().index(0, MSR_COL_DESCRIPTION)
            tab.table.doubleClicked.emit(index)
            edit_mock.assert_called()
        self.assertEqual(tab.table.selected_measure_id(), measure.id)

    def test_enter_opens_edit(self) -> None:
        coordination = self._create_coordination()
        coordination_measure_service.add(
            coordination.id,
            title="Krátký",
            description="Text",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        tab.table.setFocus()
        tab.table.selectRow(0)
        tab._update_action_buttons()
        called = []

        def _edit() -> None:
            called.append(True)

        self.assertTrue(hasattr(tab.table, "_row_actions_filter"))
        tab.table._row_actions_filter.on_edit = _edit
        _send_key(tab.table, Qt.Key.Key_Return)
        self.assertTrue(called)

    def test_delete_asks_confirmation_and_deactivates(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Aktivní opatření",
            description="Text",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        tab.table.setFocus()
        tab.table.selectRow(0)
        tab._update_action_buttons()
        self.assertTrue(tab.deactivate_btn.isEnabled())

        with patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question:
            _send_key(tab.table, Qt.Key.Key_Delete)
            question.assert_called()

        reloaded = coordination_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

    def test_delete_without_selection_does_nothing(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Aktivní",
            description="Text",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        tab.table.clearSelection()
        tab._update_action_buttons()
        with patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.question"
        ) as question, patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.information"
        ) as info:
            _send_key(tab.table, Qt.Key.Key_Delete)
            question.assert_not_called()
            info.assert_not_called()
        self.assertTrue(coordination_measure_service.get_by_id(measure.id).active)

    def test_delete_on_inactive_does_not_deactivate(self) -> None:
        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            title="Neaktivní",
            description="Text",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        coordination_measure_service.deactivate(measure.id)
        tab = CoordinationMeasuresTab(coordination_id=coordination.id)
        tab.table.setFocus()
        tab.table.selectRow(0)
        tab._update_action_buttons()
        self.assertFalse(tab.deactivate_btn.isEnabled())

        with patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.question"
        ) as question, patch(
            "moduly.koordinace_bozp.ui.coordination_measures_tab.QMessageBox.information"
        ) as info:
            _send_key(tab.table, Qt.Key.Key_Delete)
            question.assert_not_called()
            info.assert_called()
            self.assertIn("neaktivní", info.call_args.args[2].lower())

        self.assertFalse(coordination_measure_service.get_by_id(measure.id).active)

    def test_list_page_has_row_actions(self) -> None:
        page = KoordinaceBozpPage()
        self.assertTrue(hasattr(page.table, "_row_actions_installed"))
        self.assertEqual(
            page.table.horizontalHeader().sectionResizeMode(COL_SUBJECT),
            QHeaderView.ResizeMode.Stretch,
        )


if __name__ == "__main__":
    unittest.main()
