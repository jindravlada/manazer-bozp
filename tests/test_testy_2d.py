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
    from moduly.testy.constants import COLUMN_HEADERS, GENDER_MALE
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog


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
        return test_employee_service.create_employee(**data)

    def test_employee_without_titles_stays_plain(self) -> None:
        created = self._create()
        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.title_before, "")
        self.assertEqual(loaded.title_after, "")
        self.assertFalse(loaded.may_examine)
        self.assertEqual(loaded.display_name, "Jan Novák")

    def test_save_and_load_both_titles(self) -> None:
        created = self._create(title_before=" Ing. ", title_after=" Ph.D. ")
        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.title_before, "Ing.")
        self.assertEqual(loaded.title_after, "Ph.D.")
        self.assertEqual(loaded.first_name, "Jan")
        self.assertEqual(loaded.last_name, "Novák")

        updated = test_employee_service.update_employee_details(
            created.id,
            personal_number=loaded.personal_number,
            first_name=loaded.first_name,
            last_name=loaded.last_name,
            title_before="Mgr.",
            title_after="MBA",
            workplace_id=loaded.workplace_id,
            responsibility_role_ids=[self.role.id],
            active=True,
            gender=GENDER_MALE,
        )
        self.assertEqual(updated.title_before, "Mgr.")
        self.assertEqual(updated.title_after, "MBA")

    def test_save_examiner_flag(self) -> None:
        created = self._create(may_examine=True)
        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertTrue(loaded.may_examine)

        cleared = test_employee_service.update_employee_details(
            created.id,
            personal_number=loaded.personal_number,
            first_name=loaded.first_name,
            last_name=loaded.last_name,
            workplace_id=loaded.workplace_id,
            responsibility_role_ids=[self.role.id],
            may_examine=False,
            active=True,
            gender=GENDER_MALE,
        )
        self.assertFalse(cleared.may_examine)

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

    def test_dialog_edits_titles_and_examiner_flag(self) -> None:
        self.assertEqual(
            COLUMN_HEADERS,
            [
                "ID",
                "Osobní číslo",
                "Příjmení",
                "Jméno",
                "Funkce / role",
                "Provoz (pracoviště)",
                "Stav",
            ],
        )
        dialog = TestEmployeeDialog()
        self.assertFalse(dialog.may_examine.isChecked())
        self.assertEqual(dialog.may_examine.text(), "Zkoušející / člen komise")
        dialog.personal_number.setText("2d-ui")
        dialog.title_before.setText("Ing.")
        dialog.first_name.setText("Jan")
        dialog.last_name.setText("Novák")
        dialog.title_after.setText("Ph.D.")
        dialog.workplace.set_workplace_id(self.workplace.id)
        dialog.roles.set_role_ids([self.role.id])
        dialog.may_examine.setChecked(True)
        for index in range(dialog.gender.count()):
            if dialog.gender.itemData(index) == GENDER_MALE:
                dialog.gender.setCurrentIndex(index)
                break
        dialog.accept()

        saved = test_employee_service.get_employee(dialog.saved_employee_id)
        assert saved is not None
        self.assertEqual(saved.display_name, "Ing. Jan Novák, Ph.D.")
        self.assertTrue(saved.may_examine)

        edit = TestEmployeeDialog(
            employee=saved,
            role_ids=test_employee_service.get_role_ids(saved.id),
        )
        try:
            self.assertEqual(edit.title_before.text(), "Ing.")
            self.assertEqual(edit.title_after.text(), "Ph.D.")
            self.assertTrue(edit.may_examine.isChecked())
        finally:
            edit.close()
            dialog.close()

    def test_initialize_database_is_repeatable(self) -> None:
        before = set(_table_columns("test_employees"))
        initialize_database()
        self.assertEqual(set(_table_columns("test_employees")), before)


if __name__ == "__main__":
    unittest.main()
