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
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from tests.historical_test_employee import seed_historical_test_employee


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
        self.role_a = responsibility_role_service.create_role(name="Mistr přezkoušení")

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
        return seed_historical_test_employee(**data)

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
