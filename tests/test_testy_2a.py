"""TESTY-2a: datový model zaměstnanců."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, func, select, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-2a-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _table_columns,
        _table_exists,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.sluzby.test_employee_service import (
        TestEmployeeError,
        test_employee_service,
    )


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


class TestEmployeeModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.commit()
        self.workplace = settings_service.save_workplace(name="Provoz přezkoušení")
        self.other_workplace = settings_service.save_workplace(name="Druhý provoz")
        self.role_a = responsibility_role_service.create_role(name="Mistr přezkoušení")
        self.role_b = responsibility_role_service.create_role(name="Vedoucí směny")
        self.role_c = responsibility_role_service.create_role(name="Obsluha jeřábu")

    def _create(self, **overrides):
        data = {
            "personal_number": "00123",
            "first_name": "Jan",
            "last_name": "Novák",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role_a.id],
            "active": True,
        }
        data.update(overrides)
        return test_employee_service.create_employee(**data)

    def test_create_and_load_identity(self) -> None:
        created = self._create(personal_number="  00123  ")
        self.assertEqual(created.personal_number, "00123")
        self.assertEqual(created.first_name, "Jan")
        self.assertEqual(created.last_name, "Novák")
        self.assertTrue(created.active)

        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.personal_number, "00123")
        self.assertEqual(loaded.first_name, "Jan")
        self.assertEqual(loaded.last_name, "Novák")

        by_number = test_employee_service.get_by_personal_number("00123")
        assert by_number is not None
        self.assertEqual(by_number.id, created.id)

    def test_single_workplace_reference(self) -> None:
        employee = self._create()
        self.assertEqual(employee.workplace_id, self.workplace.id)
        self.assertNotIn("workplace_name", _table_columns("test_employees"))
        self.assertNotIn("name", _table_columns("test_employees"))

        updated = test_employee_service.set_workplace(
            employee.id,
            self.other_workplace.id,
        )
        self.assertEqual(updated.workplace_id, self.other_workplace.id)
        reloaded = test_employee_service.get_employee(employee.id)
        assert reloaded is not None
        self.assertEqual(reloaded.workplace_id, self.other_workplace.id)

    def test_multiple_roles_and_replacement(self) -> None:
        employee = self._create(
            responsibility_role_ids=[self.role_a.id, self.role_b.id, self.role_a.id],
        )
        self.assertEqual(
            test_employee_service.get_role_ids(employee.id),
            [self.role_a.id, self.role_b.id],
        )
        self.assertNotIn("name", _table_columns("test_employee_roles"))

        replaced = test_employee_service.set_roles(
            employee.id,
            [self.role_c.id, self.role_a.id],
        )
        self.assertEqual(replaced, [self.role_c.id, self.role_a.id])
        self.assertEqual(
            test_employee_service.get_role_ids(employee.id),
            [self.role_c.id, self.role_a.id],
        )
        reloaded = test_employee_service.get_employee(employee.id)
        assert reloaded is not None
        self.assertEqual(reloaded.workplace_id, self.workplace.id)

    def test_update_identity_keeps_workplace_and_roles(self) -> None:
        employee = self._create(
            responsibility_role_ids=[self.role_a.id, self.role_b.id],
        )
        updated = test_employee_service.update_employee(
            employee.id,
            personal_number="00456",
            first_name="Petr",
            last_name="Svoboda",
        )
        self.assertEqual(updated.personal_number, "00456")
        self.assertEqual(updated.first_name, "Petr")
        self.assertEqual(updated.last_name, "Svoboda")
        self.assertEqual(updated.workplace_id, self.workplace.id)
        self.assertEqual(
            test_employee_service.get_role_ids(employee.id),
            [self.role_a.id, self.role_b.id],
        )
        self.assertIsNone(test_employee_service.get_by_personal_number("00123"))
        found = test_employee_service.get_by_personal_number("00456")
        assert found is not None
        self.assertEqual(found.id, employee.id)

    def test_deactivate_keeps_row(self) -> None:
        employee = self._create()
        deactivated = test_employee_service.deactivate(employee.id)
        self.assertFalse(deactivated.active)
        self.assertEqual(_count(TestEmployee), 1)

        loaded = test_employee_service.get_employee(employee.id)
        assert loaded is not None
        self.assertFalse(loaded.active)
        self.assertEqual(loaded.personal_number, "00123")

        active_only = test_employee_service.list_employees()
        self.assertNotIn(employee.id, [item.id for item in active_only])
        everyone = test_employee_service.list_employees(include_inactive=True)
        self.assertIn(employee.id, [item.id for item in everyone])

        activated = test_employee_service.activate(employee.id)
        self.assertTrue(activated.active)
        self.assertEqual(
            [item.id for item in test_employee_service.list_employees()],
            [employee.id],
        )

    def test_reject_invalid_references_and_duplicates(self) -> None:
        before = _count(TestEmployee)
        with self.assertRaises(TestEmployeeError):
            self._create(workplace_id=999_999)
        with self.assertRaises(TestEmployeeError):
            self._create(responsibility_role_ids=[999_999])
        with self.assertRaises(TestEmployeeError):
            self._create(responsibility_role_ids=[])
        with self.assertRaises(TestEmployeeError):
            self._create(personal_number="   ")
        self.assertEqual(_count(TestEmployee), before)

        employee = self._create()
        with self.assertRaises(TestEmployeeError):
            self._create(personal_number="00123")
        with self.assertRaises(TestEmployeeError):
            test_employee_service.set_workplace(employee.id, 999_999)
        with self.assertRaises(TestEmployeeError):
            test_employee_service.set_roles(employee.id, [self.role_a.id, 999_999])
        self.assertEqual(
            test_employee_service.get_role_ids(employee.id),
            [self.role_a.id],
        )
        reloaded = test_employee_service.get_employee(employee.id)
        assert reloaded is not None
        self.assertEqual(reloaded.workplace_id, self.workplace.id)

    def test_migration_preserves_existing_database(self) -> None:
        workplace_columns = set(_table_columns("workplaces"))
        role_columns = set(_table_columns("responsibility_roles"))
        workplace_name = self.workplace.name
        role_name = self.role_a.name

        with get_session() as session:
            session.execute(text("DROP TABLE IF EXISTS test_employee_roles"))
            session.execute(text("DROP TABLE IF EXISTS test_employees"))
            session.commit()

        self.assertFalse(_table_exists("test_employees"))
        self.assertFalse(_table_exists("test_employee_roles"))

        initialize_database()

        self.assertEqual(set(_table_columns("workplaces")), workplace_columns)
        self.assertEqual(set(_table_columns("responsibility_roles")), role_columns)
        self.assertTrue(_table_exists("test_employees"))
        self.assertTrue(_table_exists("test_employee_roles"))
        self.assertEqual(_count(TestEmployee), 0)
        self.assertIn("personal_number", _unique_indexed_columns("test_employees"))

        workplace = settings_service.get_workplace_by_id(self.workplace.id)
        assert workplace is not None
        self.assertEqual(workplace.name, workplace_name)
        role = responsibility_role_service.get_by_id(self.role_a.id)
        assert role is not None
        self.assertEqual(role.name, role_name)

        restored = self._create()
        self.assertEqual(restored.personal_number, "00123")
        self.assertEqual(restored.workplace_id, self.workplace.id)


def _unique_indexed_columns(table_name: str) -> set[str]:
    from core.database.database_initializer import _db_engine

    columns: set[str] = set()
    with _db_engine().connect() as connection:
        indexes = connection.execute(text(f"PRAGMA index_list({table_name})")).fetchall()
        for index in indexes:
            if not index[2]:
                continue
            info = connection.execute(text(f"PRAGMA index_info({index[1]})")).fetchall()
            columns.update(str(row[2]) for row in info)
    return columns


if __name__ == "__main__":
    unittest.main()
