"""TESTY-2d: tituly zaměstnance a oprávnění ke zkoušení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-2d-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _ensure_test_employee_columns,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from core.database.session import get_session
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from tests.historical_test_employee import seed_historical_test_employee


class TestEmployeeTitlesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.commit()
        self.workplace = settings_service.save_workplace(name="Provoz 2d")
        self.role = responsibility_role_service.create_role(name="Mistr 2d")

    def _create(self, **overrides) -> TestEmployee:
        data = {
            "personal_number": "2d-001",
            "first_name": "Jan",
            "last_name": "Novák",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role.id],
        }
        data.update(overrides)
        return seed_historical_test_employee(**data)

    def test_employee_without_titles_stays_plain(self) -> None:
        created = self._create()
        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.title_before, "")
        self.assertEqual(loaded.title_after, "")
        self.assertFalse(loaded.may_examine)
        self.assertEqual(loaded.display_name, "Jan Novák")

    def test_display_name_composition(self) -> None:
        plain = self._create(personal_number="2d-plain")
        self.assertEqual(plain.display_name, "Jan Novák")

        before = self._create(
            personal_number="2d-before",
            title_before="Ing.",
        )
        self.assertEqual(before.display_name, "Ing. Jan Novák")

        after = self._create(
            personal_number="2d-after",
            title_after="Ph.D.",
        )
        self.assertEqual(after.display_name, "Jan Novák, Ph.D.")

        both = self._create(
            personal_number="2d-both",
            title_before="Ing.",
            title_after="Ph.D.",
        )
        self.assertEqual(both.display_name, "Ing. Jan Novák, Ph.D.")

    def test_eligible_examiners_are_active_and_flagged(self) -> None:
        eligible = self._create(personal_number="2d-yes", may_examine=True)
        ordinary = self._create(personal_number="2d-no", may_examine=False)
        inactive = self._create(
            personal_number="2d-off",
            may_examine=True,
            active=False,
        )

        ids = [item.id for item in test_employee_service.list_eligible_examiners()]
        self.assertEqual(ids, [eligible.id])

    def test_migration_keeps_existing_employee(self) -> None:
        created = self._create(personal_number="2d-old", first_name="Stary", last_name="Zamestnanec")
        with _db_engine().connect() as connection:
            connection.execute(text("ALTER TABLE test_employees DROP COLUMN title_before"))
            connection.execute(text("ALTER TABLE test_employees DROP COLUMN title_after"))
            connection.execute(text("ALTER TABLE test_employees DROP COLUMN may_examine"))
            connection.commit()

        self.assertNotIn("title_before", _table_columns("test_employees"))
        _ensure_test_employee_columns()
        columns = set(_table_columns("test_employees"))
        self.assertIn("title_before", columns)
        self.assertIn("title_after", columns)
        self.assertIn("may_examine", columns)

        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.personal_number, "2d-old")
        self.assertEqual(loaded.first_name, "Stary")
        self.assertEqual(loaded.last_name, "Zamestnanec")
        self.assertEqual(loaded.workplace_id, self.workplace.id)
        self.assertEqual(loaded.title_before, "")
        self.assertEqual(loaded.title_after, "")
        self.assertFalse(loaded.may_examine)
        self.assertEqual(
            test_employee_service.get_role_ids(created.id),
            [self.role.id],
        )

        _ensure_test_employee_columns()
        again = test_employee_service.get_employee(created.id)
        assert again is not None
        self.assertEqual(again.personal_number, "2d-old")

    def test_initialize_database_is_repeatable(self) -> None:
        before = set(_table_columns("test_employees"))
        initialize_database()
        self.assertEqual(set(_table_columns("test_employees")), before)


if __name__ == "__main__":
    unittest.main()
