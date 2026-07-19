"""Fáze COORD-002 – zúčastnění zaměstnavatelé."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-002-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        COORDINATION_EMPLOYER_TYPE_MAIN,
        COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
        EMP_COL_ABBREVIATION,
        EMP_COL_ACTIVE,
        EMP_COL_ICO,
        EMP_COL_IS_MAIN,
        EMP_COL_NAME,
        EMPLOYER_TABLE_HEADERS,
        TAB_BASICS,
        TAB_EMPLOYERS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        CoordinationEmployerError,
        coordination_employer_service,
        default_abbreviation,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord002TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
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
            address="Praha 1",
            nace="",
        )

    def test_model_and_table(self) -> None:
        self.assertEqual(CoordinationEmployer.__tablename__, "coordination_employers")
        columns = _table_columns("coordination_employers")
        for name in (
            "id",
            "coordination_id",
            "employer_type",
            "company_name",
            "ico",
            "address",
            "abbreviation",
            "is_main",
            "note",
            "active",
            "sort_order",
            "created_at",
            "updated_at",
        ):
            self.assertIn(name, columns)

    def test_auto_insert_main_employer(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Auto hlavní",
            meeting_date=date.today(),
        )
        employers = coordination_employer_service.list_for_coordination(coordination.id)
        self.assertEqual(len(employers), 1)
        main = employers[0]
        self.assertTrue(main.is_main)
        self.assertEqual(main.employer_type, COORDINATION_EMPLOYER_TYPE_MAIN)
        self.assertEqual(main.company_name, "Hlavní firma s.r.o.")
        self.assertEqual(main.ico, "12345678")
        self.assertEqual(main.address, "Praha 1")
        self.assertTrue(main.active)
        self.assertEqual(main.sort_order, 1)
        self.assertEqual(main.abbreviation, default_abbreviation("Hlavní firma s.r.o."))

    def test_main_employer_cannot_be_deactivated(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Hlavní nelze",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        with self.assertRaises(CoordinationEmployerError):
            coordination_employer_service.deactivate(main.id)
        reloaded = coordination_employer_service.get_by_id(main.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_add_participant(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Další firma",
            meeting_date=date.today(),
        )
        participant = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Stavex a.s.",
            ico="87654321",
            address="Brno",
            abbreviation="STAVEX",
            note="subdodavatel",
        )
        self.assertFalse(participant.is_main)
        self.assertEqual(participant.employer_type, COORDINATION_EMPLOYER_TYPE_PARTICIPANT)
        self.assertEqual(participant.abbreviation, "STAVEX")
        self.assertEqual(participant.sort_order, 2)

        employers = coordination_employer_service.list_for_coordination(coordination.id)
        self.assertEqual(len(employers), 2)
        self.assertEqual(employers[0].is_main, True)
        self.assertEqual(employers[1].id, participant.id)

    def test_edit_abbreviation(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Zkratka",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        updated = coordination_employer_service.update_employer(
            main.id,
            abbreviation="HLFIRMA",
        )
        assert updated is not None
        self.assertEqual(updated.abbreviation, "HLFIRMA")
        self.assertEqual(updated.company_name, "Hlavní firma s.r.o.")

        participant = coordination_employer_service.add_participant(
            coordination.id,
            company_name="České dráhy",
            abbreviation="CD",
        )
        updated_participant = coordination_employer_service.update_employer(
            participant.id,
            abbreviation="ČD",
            company_name="České dráhy, a.s.",
        )
        assert updated_participant is not None
        self.assertEqual(updated_participant.abbreviation, "ČD")
        self.assertEqual(updated_participant.company_name, "České dráhy, a.s.")

    def test_deactivate_participant(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Deaktivace firmy",
            meeting_date=date.today(),
        )
        participant = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Firma 2",
            abbreviation="FIRMA2",
        )
        self.assertTrue(coordination_employer_service.deactivate(participant.id))
        reloaded = coordination_employer_service.get_by_id(participant.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        active_only = coordination_employer_service.list_for_coordination(
            coordination.id,
            include_inactive=False,
        )
        self.assertEqual(len(active_only), 1)
        self.assertTrue(active_only[0].is_main)

        self.assertTrue(coordination_employer_service.activate(participant.id))
        again = coordination_employer_service.get_by_id(participant.id)
        assert again is not None
        self.assertTrue(again.active)

    def test_employer_sort_order(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Pořadí",
            meeting_date=date.today(),
        )
        first = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Alpha",
            abbreviation="AAA",
        )
        second = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Beta",
            abbreviation="BBB",
        )
        employers = coordination_employer_service.list_for_coordination(coordination.id)
        self.assertEqual(
            [item.abbreviation for item in employers],
            [
                employers[0].abbreviation,
                "AAA",
                "BBB",
            ],
        )
        self.assertEqual(employers[0].sort_order, 1)
        self.assertEqual(first.sort_order, 2)
        self.assertEqual(second.sort_order, 3)
        self.assertEqual([item.sort_order for item in employers], [1, 2, 3])

    def test_unique_abbreviation(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Unikátní zkratka",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        with self.assertRaises(CoordinationEmployerError):
            coordination_employer_service.add_participant(
                coordination.id,
                company_name="Kopie",
                abbreviation=main.abbreviation,
            )

    def test_dialog_employers_tab(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UI záložka",
            meeting_date=date.today(),
        )
        coordination_employer_service.add_participant(
            coordination.id,
            company_name="Partner",
            ico="11112222",
            abbreviation="PART",
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertEqual(dialog.tabs.tabText(0), TAB_BASICS)
        self.assertEqual(dialog.tabs.tabText(1), TAB_EMPLOYERS)
        tab = dialog.employers_tab
        self.assertFalse(tab.content.isHidden())
        self.assertTrue(tab.unavailable_label.isHidden())
        self.assertEqual(
            [dialog.employers_tab.table.horizontalHeaderItem(i).text() for i in range(7)],
            EMPLOYER_TABLE_HEADERS,
        )
        self.assertEqual(tab.table.rowCount(), 2)
        self.assertEqual(tab.table.item(0, EMP_COL_IS_MAIN).text(), "Ano")
        self.assertEqual(tab.table.item(1, EMP_COL_ABBREVIATION).text(), "PART")
        self.assertEqual(tab.table.item(1, EMP_COL_NAME).text(), "Partner")
        self.assertEqual(tab.table.item(1, EMP_COL_ICO).text(), "11112222")
        self.assertEqual(tab.table.item(1, EMP_COL_ACTIVE).text(), "Ano")

        new_dialog = BozpCoordinationDialog(None)
        self.assertTrue(new_dialog.employers_tab.content.isHidden())
        self.assertFalse(new_dialog.employers_tab.unavailable_label.isHidden())


if __name__ == "__main__":
    unittest.main()
