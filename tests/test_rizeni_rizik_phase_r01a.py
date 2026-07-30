"""Fáze R01a – založení modulu Řízení rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
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

    from core.modules.module_manager import ModuleManager
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        DEFAULT_HAZARD_IDENTIFICATION_STATUS,
        HAZARD_IDENTIFICATION_STATUS_DRAFT,
        MODULE_KEY,
        MODULE_NAME,
        TABLE_HEADERS,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.module import get_module_definition
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )


class RizeniRizikModulePhaseR01aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentification))
            session.commit()

    def test_hazard_identification_model_defaults(self) -> None:
        column = HazardIdentification.__table__.c.status
        self.assertEqual(column.default.arg, DEFAULT_HAZARD_IDENTIFICATION_STATUS)
        self.assertEqual(HazardIdentification.__tablename__, "hazard_identifications")
        self.assertTrue(HazardIdentification.__table__.c.active.default.arg)

    def test_hazard_identifications_table_exists(self) -> None:
        columns = _table_columns("hazard_identifications")
        self.assertIn("id", columns)
        self.assertIn("identification_number", columns)
        self.assertIn("operation_id", columns)
        self.assertIn("workplace_id", columns)
        self.assertIn("workplace_part_id", columns)
        self.assertIn("responsible_person_id", columns)
        self.assertIn("started_at", columns)
        self.assertIn("status", columns)
        self.assertIn("note", columns)
        self.assertIn("active", columns)
        self.assertIn("created_at", columns)
        self.assertIn("updated_at", columns)

    def test_module_definition_is_registered(self) -> None:
        module = get_module_definition()
        self.assertEqual(module.key, MODULE_KEY)
        self.assertEqual(module.name, MODULE_NAME)
        self.assertTrue(module.enabled)

        registered_keys = {item.key for item in ModuleManager().get_modules()}
        self.assertIn(MODULE_KEY, registered_keys)

    def test_page_opens_with_expected_table(self) -> None:
        from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage

        page = RizeniRizikPage()
        tab = page.identifications_tab
        self.assertEqual(tab.new_btn.text(), "Nová identifikace")
        self.assertEqual(tab.edit_btn.text(), "Upravit")
        self.assertEqual(tab.activate_btn.text(), "Aktivovat")
        self.assertEqual(tab.deactivate_btn.text(), "Deaktivovat")
        self.assertEqual(
            [
                tab.table.horizontalHeaderItem(column).text()
                for column in range(tab.table.columnCount())
            ],
            TABLE_HEADERS,
        )

    def test_list_sorted_by_started_at_desc(self) -> None:
        operation = settings_service.save_workplace(name="Provoz A")
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type="workplace",
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Jan", last_name="Novák")

        hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
            started_at=date(2026, 1, 10),
        )
        newer = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
            started_at=date(2026, 6, 15),
        )

        from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 1).text(), newer.identification_number)
        self.assertNotEqual(table.item(0, 1).text(), table.item(1, 1).text())
        self.assertEqual(table.item(0, 7).text(), "Rozpracováno")
        self.assertEqual(table.item(0, 5).text(), "15.06.2026")

    def test_create_identification_uses_default_status(self) -> None:
        operation = settings_service.save_workplace(name="Provoz test")
        workplace = settings_service.save_workplace(
            name="Pracoviště test",
            item_type="workplace",
            parent_id=operation.id,
        )
        created = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.assertEqual(created.status, HAZARD_IDENTIFICATION_STATUS_DRAFT)
        self.assertRegex(created.identification_number, r"^\d{4}-\d{4}$")


if __name__ == "__main__":
    unittest.main()
