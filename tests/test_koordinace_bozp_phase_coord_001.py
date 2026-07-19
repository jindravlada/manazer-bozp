"""Fáze COORD-001 – založení modulu Koordinace BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-001-"))
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
    from core.modules.module_manager import ModuleManager
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_ARCHIVED,
        BOZP_COORDINATION_STATUS_COMPLETED,
        BOZP_COORDINATION_STATUS_DRAFT,
        BOZP_COORDINATION_STATUS_LABELS,
        DEFAULT_BOZP_COORDINATION_STATUS,
        MODULE_KEY,
        MODULE_NAME,
        TABLE_HEADERS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
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
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.module import get_module_definition
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        BozpCoordinationError,
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord001TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.execute(delete(HazardIdentification))
            session.commit()

    def test_model_and_table(self) -> None:
        self.assertEqual(BozpCoordination.__tablename__, "bozp_coordinations")
        column = BozpCoordination.__table__.c.status
        self.assertEqual(column.default.arg, DEFAULT_BOZP_COORDINATION_STATUS)
        self.assertTrue(BozpCoordination.__table__.c.active.default.arg)

        columns = _table_columns("bozp_coordinations")
        for name in (
            "id",
            "coordination_number",
            "meeting_date",
            "place",
            "subject",
            "status",
            "note",
            "valid_from",
            "valid_to",
            "created_at",
            "updated_at",
            "active",
        ):
            self.assertIn(name, columns)

    def test_module_registered(self) -> None:
        module = get_module_definition()
        self.assertEqual(module.key, MODULE_KEY)
        self.assertEqual(module.name, MODULE_NAME)
        self.assertTrue(module.enabled)
        keys = {item.key for item in ModuleManager().get_modules()}
        self.assertIn(MODULE_KEY, keys)

    def test_create_coordination(self) -> None:
        created = bozp_coordination_service.create_coordination(
            meeting_date=date(2026, 7, 19),
            place="Jednací místnost",
            subject="Koordinace stavebních prací",
            status=BOZP_COORDINATION_STATUS_DRAFT,
            note="COORD-001",
        )
        self.assertIsNotNone(created.id)
        self.assertEqual(created.subject, "Koordinace stavebních prací")
        self.assertEqual(created.place, "Jednací místnost")
        self.assertEqual(created.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertTrue(created.active)

    def test_automatic_numbering(self) -> None:
        year = datetime.now().year
        first = bozp_coordination_service.create_coordination(
            subject="První",
            meeting_date=date.today(),
        )
        second = bozp_coordination_service.create_coordination(
            subject="Druhá",
            meeting_date=date.today(),
        )
        self.assertEqual(first.coordination_number, f"{year}-0001")
        self.assertEqual(second.coordination_number, f"{year}-0002")

    def test_numbering_independent_from_hazard_identifications(self) -> None:
        year = datetime.now().year
        operation = settings_service.save_workplace(
            name="COORD provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="COORD pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Coord", last_name="Tester")
        identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.assertEqual(identification.identification_number, f"{year}-0001")

        coordination = bozp_coordination_service.create_coordination(
            subject="Samostatná řada",
            meeting_date=date.today(),
        )
        self.assertEqual(coordination.coordination_number, f"{year}-0001")

    def test_change_status(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="Stav",
            meeting_date=date.today(),
        )
        updated = bozp_coordination_service.update_coordination(
            created.id,
            meeting_date=created.meeting_date,
            place=created.place,
            subject=created.subject,
            status=BOZP_COORDINATION_STATUS_COMPLETED,
            note=created.note,
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.status, BOZP_COORDINATION_STATUS_COMPLETED)
        self.assertEqual(
            BOZP_COORDINATION_STATUS_LABELS[updated.status],
            "Dokončeno",
        )

        archived = bozp_coordination_service.update_coordination(
            created.id,
            meeting_date=created.meeting_date,
            place="",
            subject="Stav",
            status=BOZP_COORDINATION_STATUS_ARCHIVED,
            note="",
        )
        assert archived is not None
        self.assertEqual(archived.status, BOZP_COORDINATION_STATUS_ARCHIVED)

    def test_deactivate_without_delete(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="Deaktivace",
            meeting_date=date.today(),
        )
        self.assertTrue(bozp_coordination_service.deactivate(created.id))
        loaded = bozp_coordination_service.get_by_id(created.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertFalse(loaded.active)

        active_only = bozp_coordination_service.get_all(include_inactive=False)
        self.assertEqual(active_only, [])
        all_rows = bozp_coordination_service.get_all(include_inactive=True)
        self.assertEqual(len(all_rows), 1)
        self.assertEqual(all_rows[0].id, created.id)

        self.assertTrue(bozp_coordination_service.activate(created.id))
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_page_list_and_open(self) -> None:
        created = bozp_coordination_service.create_coordination(
            meeting_date=date(2026, 7, 19),
            place="Areál A",
            subject="Předmět v seznamu",
            status=BOZP_COORDINATION_STATUS_DRAFT,
        )
        page = KoordinaceBozpPage()
        self.assertEqual(page.new_btn.text(), "Nová koordinace")
        self.assertEqual(page.open_btn.text(), "Otevřít")
        self.assertEqual(page.activate_btn.text(), "Aktivovat")
        self.assertEqual(page.deactivate_btn.text(), "Deaktivovat")
        self.assertEqual(
            list(page.table.horizontalHeaderItem(i).text() for i in range(1, 7)),
            TABLE_HEADERS[1:],
        )

        page.refresh()
        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), created.coordination_number)
        self.assertEqual(page.table.item(0, 3).text(), "Areál A")
        self.assertEqual(page.table.item(0, 4).text(), "Předmět v seznamu")

        page.table.selectRow(0)
        dialog = BozpCoordinationDialog(page, coordination=created)
        self.assertEqual(dialog.number_label.text(), created.coordination_number)
        self.assertEqual(dialog.subject.text(), "Předmět v seznamu")
        data = dialog.get_data()
        self.assertEqual(data["subject"], "Předmět v seznamu")
        # Číslo není editovatelné (jen QLabel).
        self.assertFalse(hasattr(dialog, "number_edit"))

    def test_subject_required(self) -> None:
        with self.assertRaises(BozpCoordinationError):
            bozp_coordination_service.create_coordination(
                subject="   ",
                meeting_date=date.today(),
            )


if __name__ == "__main__":
    unittest.main()
