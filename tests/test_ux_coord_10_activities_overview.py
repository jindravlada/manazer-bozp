"""UX-COORD-10 – společný přehled činností zaměstnavatelů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QHeaderView, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-10-"))
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
    from core.widgets.table_selection import find_table_row_by_id
    from moduly.koordinace_bozp.constants import (
        ACT_COL_ACTIVE,
        ACT_COL_EMPLOYER,
        ACT_COL_FROM,
        ACT_COL_NAME,
        ACT_COL_PLACE,
        ACT_COL_TO,
        ACTIVITY_TABLE_HEADERS,
        COORD_HEADER_ACTIVITIES,
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
    from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
        coordination_employer_activity_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import (
        BozpCoordinationDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_employer_activities_tab import (
        CoordinationEmployerActivitiesTab,
    )
    from moduly.koordinace_bozp.ui.coordination_employer_activity_dialog import (
        CoordinationEmployerActivityDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord10ActivitiesOverviewTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

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
        self.today = date.today()
        self.operation = settings_service.save_workplace(
            name="UX10 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="UX10 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_coordination(self):
        return bozp_coordination_service.create_coordination(
            subject="UX-COORD-10",
            meeting_date=self.today,
        )

    def test_table_shows_all_employers_activities(self) -> None:
        coordination = self._create_coordination()
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel Alfa s.r.o.",
            abbreviation="ALF",
        )
        coordination_employer_activity_service.add(
            main.id,
            activity_name="Údržba",
            planned_from=self.today + timedelta(days=2),
        )
        coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Montáž",
            planned_from=self.today,
        )

        items = coordination_employer_activity_service.list_for_coordination(
            coordination.id
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(
            [item.activity_name for item in items],
            ["Údržba", "Montáž"],
        )

        tab = CoordinationEmployerActivitiesTab(None, coordination_id=coordination.id)
        self.assertFalse(hasattr(tab, "employer_combo"))
        self.assertEqual(tab.findChildren(QComboBox), [])
        self.assertEqual(tab.table.rowCount(), 2)
        employer_cells = {
            tab.table.item(row, ACT_COL_EMPLOYER).text()
            for row in range(tab.table.rowCount())
        }
        self.assertTrue(any("Hlavní firma" in text for text in employer_cells))
        self.assertTrue(any("Dodavatel Alfa" in text or "ALF" in text for text in employer_cells))
        tab.close()

    def test_sorting_employer_then_from_then_name(self) -> None:
        coordination = self._create_coordination()
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        beta = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Beta s.r.o.",
            abbreviation="BET",
        )
        # Main sort_order=1, Beta sort_order=2.
        coordination_employer_activity_service.add(
            beta.id,
            activity_name="Beta později",
            planned_from=self.today + timedelta(days=5),
        )
        coordination_employer_activity_service.add(
            beta.id,
            activity_name="Beta dříve B",
            planned_from=self.today,
        )
        coordination_employer_activity_service.add(
            beta.id,
            activity_name="Beta dříve A",
            planned_from=self.today,
        )
        coordination_employer_activity_service.add(
            main.id,
            activity_name="Main pozdě",
            planned_from=self.today + timedelta(days=1),
        )
        coordination_employer_activity_service.add(
            main.id,
            activity_name="Main brzy",
            planned_from=self.today,
        )

        names = [
            item.activity_name
            for item in coordination_employer_activity_service.list_for_coordination(
                coordination.id
            )
        ]
        self.assertEqual(
            names,
            [
                "Main brzy",
                "Main pozdě",
                "Beta dříve A",
                "Beta dříve B",
                "Beta později",
            ],
        )

    def test_add_dialog_unchanged_has_employer(self) -> None:
        coordination = self._create_coordination()
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        dialog = CoordinationEmployerActivityDialog(
            None,
            coordination_id=coordination.id,
        )
        self.assertIsInstance(dialog.employer, QComboBox)
        self.assertGreaterEqual(dialog.employer.count(), 1)
        self.assertEqual(dialog.employer.currentData(), main.id)
        dialog.activity_name.setText("Nová činnost")
        data = dialog.get_data()
        self.assertEqual(data["coordination_employer_id"], main.id)
        dialog.close()

    def test_edit_dialog_keeps_employer(self) -> None:
        coordination = self._create_coordination()
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel s.r.o.",
            abbreviation="DOD",
        )
        activity = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Sváření",
        )
        dialog = CoordinationEmployerActivityDialog(
            None,
            coordination_id=coordination.id,
            activity=activity,
        )
        self.assertEqual(dialog.employer.currentData(), contractor.id)
        dialog.close()

    def test_selection_restore_after_changes(self) -> None:
        coordination = self._create_coordination()
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        first = coordination_employer_activity_service.add(
            main.id,
            activity_name="První",
        )
        second = coordination_employer_activity_service.add(
            main.id,
            activity_name="Druhá",
        )
        tab = CoordinationEmployerActivitiesTab(None, coordination_id=coordination.id)
        tab.refresh(select_id=second.id, ensure_visible=True)
        self.assertEqual(tab.table.selected_activity_id(), second.id)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            tab.deactivate_selected_activity()
        self.assertEqual(tab.table.selected_activity_id(), second.id)
        reloaded = coordination_employer_activity_service.get_by_id(second.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            tab.activate_selected_activity()
        self.assertEqual(tab.table.selected_activity_id(), second.id)
        self.assertTrue(coordination_employer_activity_service.get_by_id(second.id).active)

        row = find_table_row_by_id(tab.table, first.id)
        self.assertIsNotNone(row)
        tab.close()

    def test_column_widths_persisted(self) -> None:
        coordination = self._create_coordination()
        tab = CoordinationEmployerActivitiesTab(None, coordination_id=coordination.id)
        header = tab.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(ACT_COL_NAME),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(ACT_COL_PLACE),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (ACT_COL_EMPLOYER, ACT_COL_FROM, ACT_COL_TO, ACT_COL_ACTIVE):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
            )

        tab.table.setColumnWidth(ACT_COL_EMPLOYER, 177)
        save_table_header(tab.table, COORD_HEADER_ACTIVITIES)
        other = CoordinationEmployerActivitiesTab(None, coordination_id=coordination.id)
        configure_and_persist_table_columns(
            other.table, "coordination_employer_activities", COORD_HEADER_ACTIVITIES
        )
        restore_table_header(other.table, COORD_HEADER_ACTIVITIES)
        self.assertEqual(other.table.columnWidth(ACT_COL_EMPLOYER), 177)
        self.assertIsNotNone(coordination_table_settings())
        self.assertEqual(ACTIVITY_TABLE_HEADERS[ACT_COL_EMPLOYER], "Zaměstnavatel")
        tab.close()
        other.close()

    def test_dialog_has_no_employer_combo_on_tab(self) -> None:
        coordination = self._create_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.employer_activities_tab
        self.assertFalse(hasattr(tab, "employer_combo"))
        self.assertEqual(
            [child for child in tab.findChildren(QComboBox)],
            [],
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()
