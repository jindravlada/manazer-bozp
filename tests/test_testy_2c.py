"""TESTY-2c: našeptávač funkcí a rolí v editoru zaměstnance."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCompleter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-2c-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.multi_responsibility_role_selector import (
        MultiResponsibilityRoleSelector,
    )
    from core.widgets.search_responsibility_role_selector import (
        SearchResponsibilityRoleSelector,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog


def _completion_matches(selector: SearchResponsibilityRoleSelector, prefix: str) -> list[str]:
    completer = selector.completer()
    assert isinstance(completer, QCompleter)
    completer.setCompletionPrefix(prefix)
    model = completer.completionModel()
    return [
        str(model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole) or "")
        for row in range(model.rowCount())
    ]


class TestEmployeeRoleTypeaheadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        token = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(name=f"Provoz 2c {token}")
        self.role_start = responsibility_role_service.create_role(
            name=f"Mostový elektrikář {token}",
        )
        self.role_other = responsibility_role_service.create_role(
            name=f"Svářeč kotlů {token}",
        )
        self.role_inactive = responsibility_role_service.create_role(
            name=f"Pomocný elektrikář {token}",
        )
        responsibility_role_service.deactivate(self.role_inactive.id)
        self.token = token
        self.dialog = TestEmployeeDialog()

    def tearDown(self) -> None:
        self.dialog.close()

    def test_typeahead_uses_existing_role_selector(self) -> None:
        self.assertIsInstance(self.dialog.roles, MultiResponsibilityRoleSelector)
        self.assertIsInstance(self.dialog.roles.selector, SearchResponsibilityRoleSelector)
        completer = self.dialog.roles.selector.completer()
        self.assertIsInstance(completer, QCompleter)
        self.assertEqual(completer.filterMode(), Qt.MatchFlag.MatchContains)
        self.assertEqual(
            completer.caseSensitivity(),
            Qt.CaseSensitivity.CaseInsensitive,
        )

    def test_suggests_by_name_start_middle_and_case(self) -> None:
        selector = self.dialog.roles.selector
        start_name = self.role_start.name
        other_name = self.role_other.name

        by_start = _completion_matches(selector, "Mostový")
        self.assertIn(start_name, by_start)
        self.assertNotIn(other_name, by_start)

        by_middle = _completion_matches(selector, "ktrik")
        self.assertIn(start_name, by_middle)
        self.assertNotIn(other_name, by_middle)

        by_case = _completion_matches(selector, f"mostový elektrikář {self.token}")
        self.assertIn(start_name, by_case)
        self.assertNotIn(other_name, by_case)

    def test_inactive_role_is_not_offered_for_new_assignment(self) -> None:
        self.assertNotIn(self.role_inactive.id, self.dialog.roles.available_role_ids())
        matches = _completion_matches(self.dialog.roles.selector, f"pomocný elektrikář {self.token}")
        self.assertNotIn(self.role_inactive.name, matches)
        self.assertNotIn(f"{self.role_inactive.name} (neaktivní)", matches)

    def test_already_assigned_role_is_not_offered_again(self) -> None:
        roles = self.dialog.roles
        roles.selector.set_role_id(self.role_start.id)
        roles.add_current()

        self.assertEqual(roles.selected_role_ids(), [self.role_start.id])
        self.assertNotIn(self.role_start.id, roles.available_role_ids())
        self.assertIn(self.role_other.id, roles.available_role_ids())

        matches = _completion_matches(roles.selector, self.token)
        self.assertNotIn(self.role_start.name, matches)
        self.assertIn(self.role_other.name, matches)

        roles.selector.set_role_id(self.role_other.id)
        roles.add_current()
        self.assertEqual(
            roles.selected_role_ids(),
            [self.role_start.id, self.role_other.id],
        )
        self.assertNotIn(self.role_other.id, roles.available_role_ids())

    def test_assigned_inactive_role_stays_visible_in_editor(self) -> None:
        employee = test_employee_service.create_employee(
            personal_number=f"2c-{self.token}",
            first_name="Eva",
            last_name="Malá",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role_start.id, self.role_inactive.id],
            active=True,
        )
        responsibility_role_service.deactivate(self.role_start.id)

        edit = TestEmployeeDialog(
            employee=employee,
            role_ids=test_employee_service.get_role_ids(employee.id),
        )
        try:
            labels = [
                edit.roles.list_widget.item(index).text()
                for index in range(edit.roles.list_widget.count())
            ]
            self.assertIn(f"{self.role_start.name} (neaktivní)", labels)
            self.assertIn(f"{self.role_inactive.name} (neaktivní)", labels)
            self.assertNotIn(self.role_start.id, edit.roles.available_role_ids())
            self.assertNotIn(self.role_inactive.id, edit.roles.available_role_ids())
            self.assertEqual(
                edit.roles.selected_role_ids(),
                [self.role_start.id, self.role_inactive.id],
            )
        finally:
            edit.close()
