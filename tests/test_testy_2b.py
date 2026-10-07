"""TESTY-2b: UI evidence zaměstnanců."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QLineEdit
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-2b-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.widgets.workplace_selector import WorkplaceSelector
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ACTION_EDIT,
        ACTION_NEW,
        COL_FIRST_NAME,
        COL_LAST_NAME,
        COL_PERSONAL_NUMBER,
        COL_ROLES,
        COL_STATUS,
        COL_WORKPLACE,
        COLUMN_HEADERS,
        SHOW_INACTIVE_LABEL,
        GENDER_MALE,
        STATUS_ACTIVE_LABEL,
        STATUS_INACTIVE_LABEL,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog
    from moduly.testy.ui.testy_page import TestyPage


def _count_employees() -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(TestEmployee)) or 0)


class TestEmployeeUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.commit()
        self.workplace = settings_service.save_workplace(name="Provoz UI")
        self.other_workplace = settings_service.save_workplace(name="Druhý provoz UI")
        self.role_a = responsibility_role_service.create_role(name="Mistr UI")
        self.role_b = responsibility_role_service.create_role(name="Jeřábník UI")
        self.page = TestyPage()

    def _fill(
        self,
        dialog: TestEmployeeDialog,
        *,
        personal_number: str = "00100",
        first_name: str = "Eva",
        last_name: str = "Malá",
        workplace_id: int | None = None,
        role_ids: list[int] | None = None,
        active: bool = True,
    ) -> None:
        dialog.personal_number.setText(personal_number)
        dialog.first_name.setText(first_name)
        dialog.last_name.setText(last_name)
        if workplace_id is not None:
            dialog.workplace.set_workplace_id(workplace_id)
        if role_ids is not None:
            dialog.roles.set_role_ids(role_ids)
        dialog.active_checkbox.setChecked(active)
        for index in range(dialog.gender.count()):
            if dialog.gender.itemData(index) == GENDER_MALE:
                dialog.gender.setCurrentIndex(index)
                break

    def _warning_text(self, warning) -> str:
        self.assertTrue(warning.called)
        return str(warning.call_args[0][2])

    def test_page_shows_employee_register(self) -> None:
        headers = [
            self.page.table.horizontalHeaderItem(column).text()
            for column in range(self.page.table.columnCount())
        ]
        self.assertEqual(headers, COLUMN_HEADERS)
        self.assertTrue(self.page.table.alternatingRowColors())
        self.assertEqual(self.page.new_btn.text(), ACTION_NEW)
        self.assertEqual(self.page.edit_btn.text(), ACTION_EDIT)
        self.assertTrue(self.page.new_btn.isEnabled())
        self.assertFalse(self.page.edit_btn.isEnabled())
        self.assertEqual(self.page.show_inactive.text(), SHOW_INACTIVE_LABEL)
        self.assertFalse(self.page.show_inactive.isChecked())

    def test_create_and_edit_through_page(self) -> None:
        workplace_id = self.workplace.id
        role_ids = [self.role_a.id, self.role_b.id]

        class _Create(TestEmployeeDialog):
            def exec(self):  # noqa: A003
                self.personal_number.setText("00100")
                self.first_name.setText("Eva")
                self.last_name.setText("Malá")
                self.workplace.set_workplace_id(workplace_id)
                self.roles.set_role_ids(role_ids)
                for index in range(self.gender.count()):
                    if self.gender.itemData(index) == GENDER_MALE:
                        self.gender.setCurrentIndex(index)
                        break
                self.accept()
                return int(QDialog.DialogCode.Accepted)

        with patch("moduly.testy.ui.testy_page.TestEmployeeDialog", _Create):
            self.page.new_btn.click()

        self.assertEqual(self.page.table.rowCount(), 1)
        self.assertEqual(self.page.table.item(0, COL_PERSONAL_NUMBER).text(), "00100")
        self.assertEqual(self.page.table.item(0, COL_LAST_NAME).text(), "Malá")
        self.assertEqual(self.page.table.item(0, COL_FIRST_NAME).text(), "Eva")
        self.assertEqual(self.page.table.item(0, COL_ROLES).text(), "Mistr UI, Jeřábník UI")
        self.assertEqual(self.page.table.item(0, COL_WORKPLACE).text(), "Provoz UI")
        self.assertEqual(self.page.table.item(0, COL_STATUS).text(), STATUS_ACTIVE_LABEL)
        self.assertTrue(self.page.edit_btn.isEnabled())

        employee = test_employee_service.get_by_personal_number("00100")
        assert employee is not None
        self.assertEqual(employee.workplace_id, self.workplace.id)
        self.assertEqual(
            test_employee_service.get_role_ids(employee.id),
            [self.role_a.id, self.role_b.id],
        )

        other_workplace_id = self.other_workplace.id

        class _Edit(TestEmployeeDialog):
            def exec(self):  # noqa: A003
                self.last_name.setText("Velká")
                self.workplace.set_workplace_id(other_workplace_id)
                self.accept()
                return int(QDialog.DialogCode.Accepted)

        with patch("moduly.testy.ui.testy_page.TestEmployeeDialog", _Edit):
            self.page.edit_btn.click()

        reloaded = test_employee_service.get_employee(employee.id)
        assert reloaded is not None
        self.assertEqual(reloaded.last_name, "Velká")
        self.assertEqual(reloaded.workplace_id, self.other_workplace.id)
        self.assertEqual(self.page.table.item(0, COL_LAST_NAME).text(), "Velká")
        self.assertEqual(self.page.table.item(0, COL_WORKPLACE).text(), "Druhý provoz UI")
        self.assertEqual(_count_employees(), 1)

    def test_workplace_is_single_catalog_choice(self) -> None:
        dialog = TestEmployeeDialog(self.page)
        self.assertIsInstance(dialog.workplace, WorkplaceSelector)
        self.assertFalse(dialog.workplace.allow_custom_value)
        self.assertFalse(
            any(
                isinstance(widget, QLineEdit) and widget is not dialog.personal_number
                and widget is not dialog.first_name
                and widget is not dialog.last_name
                and widget.parent() is dialog
                for widget in dialog.findChildren(QLineEdit)
            )
        )
        self._fill(
            dialog,
            workplace_id=self.workplace.id,
            role_ids=[self.role_a.id],
        )
        dialog.workplace.setCurrentText("Ručně zadaný provoz")
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("provoz", self._warning_text(warning).casefold())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(_count_employees(), 0)

        dialog.workplace.set_workplace_id(self.workplace.id)
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        employee = test_employee_service.get_by_personal_number("00100")
        assert employee is not None
        self.assertEqual(employee.workplace_id, self.workplace.id)

    def test_required_fields_and_duplicate_personal_number(self) -> None:
        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, personal_number="  ", workplace_id=self.workplace.id, role_ids=[self.role_a.id])
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("osobní číslo", self._warning_text(warning).casefold())
        self.assertEqual(_count_employees(), 0)

        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, first_name=" ", workplace_id=self.workplace.id, role_ids=[self.role_a.id])
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("jméno", self._warning_text(warning).casefold())

        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, last_name=" ", workplace_id=self.workplace.id, role_ids=[self.role_a.id])
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("příjmení", self._warning_text(warning).casefold())

        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, role_ids=[self.role_a.id])
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("provoz", self._warning_text(warning).casefold())

        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, workplace_id=self.workplace.id, role_ids=[])
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            dialog.accept()
        self.assertIn("funkci", self._warning_text(warning).casefold())
        self.assertEqual(_count_employees(), 0)

        first = TestEmployeeDialog(self.page)
        self._fill(first, workplace_id=self.workplace.id, role_ids=[self.role_a.id, self.role_b.id])
        first.accept()
        self.assertEqual(_count_employees(), 1)

        duplicate = TestEmployeeDialog(self.page)
        self._fill(
            duplicate,
            personal_number="00100",
            first_name="Jiná",
            last_name="Osoba",
            workplace_id=self.other_workplace.id,
            role_ids=[self.role_b.id],
        )
        with patch("moduly.testy.ui.test_employee_dialog.QMessageBox.warning") as warning:
            duplicate.accept()
        self.assertIn("již existuje", self._warning_text(warning))
        self.assertNotEqual(duplicate.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(_count_employees(), 1)
        self.assertIsNone(test_employee_service.get_by_personal_number("Jiná"))

    def test_deactivate_hides_by_default_and_keeps_row(self) -> None:
        dialog = TestEmployeeDialog(self.page)
        self._fill(dialog, workplace_id=self.workplace.id, role_ids=[self.role_a.id])
        dialog.accept()
        employee = test_employee_service.get_by_personal_number("00100")
        assert employee is not None

        edit = TestEmployeeDialog(
            self.page,
            employee=test_employee_service.get_employee(employee.id),
            role_ids=test_employee_service.get_role_ids(employee.id),
        )
        edit.active_checkbox.setChecked(False)
        edit.accept()

        self.assertEqual(_count_employees(), 1)
        kept = test_employee_service.get_employee(employee.id)
        assert kept is not None
        self.assertFalse(kept.active)

        self.page.refresh()
        self.assertEqual(self.page.table.rowCount(), 0)

        self.page.show_inactive.setChecked(True)
        self.assertEqual(self.page.table.rowCount(), 1)
        self.assertEqual(self.page.table.item(0, COL_STATUS).text(), STATUS_INACTIVE_LABEL)
        self.assertEqual(self.page.table.item(0, COL_PERSONAL_NUMBER).text(), "00100")

    def test_filter_by_personal_number_and_name(self) -> None:
        first = TestEmployeeDialog(self.page)
        self._fill(
            first,
            personal_number="00111",
            first_name="Adam",
            last_name="Adamský",
            workplace_id=self.workplace.id,
            role_ids=[self.role_a.id],
        )
        first.accept()
        second = TestEmployeeDialog(self.page)
        self._fill(
            second,
            personal_number="00222",
            first_name="Beata",
            last_name="Bílá",
            workplace_id=self.workplace.id,
            role_ids=[self.role_b.id],
        )
        second.accept()
        self.page.refresh()
        self.assertEqual(self.page.table.rowCount(), 2)

        self.page.text_filter.search_edit.setText("00222")
        self.assertTrue(self.page.table.isRowHidden(self._row_with("00111")))
        self.assertFalse(self.page.table.isRowHidden(self._row_with("00222")))

        self.page.text_filter.search_edit.setText("adam")
        self.assertFalse(self.page.table.isRowHidden(self._row_with("00111")))
        self.assertTrue(self.page.table.isRowHidden(self._row_with("00222")))

        self.page.text_filter.search_edit.setText("bíl")
        self.assertTrue(self.page.table.isRowHidden(self._row_with("00111")))
        self.assertFalse(self.page.table.isRowHidden(self._row_with("00222")))

    def test_edit_shows_deactivated_workplace_and_role(self) -> None:
        dialog = TestEmployeeDialog(self.page)
        self._fill(
            dialog,
            workplace_id=self.workplace.id,
            role_ids=[self.role_a.id, self.role_b.id],
        )
        dialog.accept()
        employee = test_employee_service.get_by_personal_number("00100")
        assert employee is not None

        settings_service.deactivate_workplace(self.workplace.id)
        responsibility_role_service.deactivate(self.role_a.id)

        edit = TestEmployeeDialog(
            self.page,
            employee=test_employee_service.get_employee(employee.id),
            role_ids=test_employee_service.get_role_ids(employee.id),
        )
        self.assertEqual(edit._workplace_id(), self.workplace.id)
        self.assertIn("Provoz UI", edit.workplace.currentText())
        self.assertIn("(neaktivní)", edit.workplace.currentText())
        self.assertEqual(edit.roles.selected_role_ids(), [self.role_a.id, self.role_b.id])
        labels = [
            edit.roles.list_widget.item(index).text()
            for index in range(edit.roles.list_widget.count())
        ]
        self.assertIn("Mistr UI (neaktivní)", labels)
        self.assertIn("Jeřábník UI", labels)

        fresh = TestEmployeeDialog(self.page)
        self.assertLess(fresh.workplace.findData(self.workplace.id), 0)
        self.assertLess(fresh.roles.selector.findData(self.role_a.id), 0)
        self.assertGreaterEqual(fresh.roles.selector.findData(self.role_b.id), 0)

    def _row_with(self, personal_number: str) -> int:
        for row in range(self.page.table.rowCount()):
            item = self.page.table.item(row, COL_PERSONAL_NUMBER)
            if item is not None and item.text() == personal_number:
                return row
        self.fail(f"Řádek {personal_number} nebyl nalezen")
        return -1


if __name__ == "__main__":
    unittest.main()
