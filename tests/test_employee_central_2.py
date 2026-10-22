"""EMPLOYEE-CENTRAL-2: formulář a seznam centrální evidence zaměstnanců."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

    from core.widgets.thp_worker_selector import ThpWorkerSelector
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import (
        SettingsWorkerError,
        settings_service,
    )
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.nastaveni.ui.thp_worker_dialog import (
        POSITION_HINT,
        ROLES_HINT,
        ThpWorkerDialog,
    )
    from moduly.schuzky.sluzby.meeting_participant_ref import MEETING_SOURCE_THP_WORKER
    from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _count(table: str) -> int:
    connection = sqlite3.connect(str(_db_path()))
    try:
        row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    finally:
        connection.close()
    return int(row[0])


def _header_index(table, title: str) -> int:
    for column in range(table.columnCount()):
        header = table.horizontalHeaderItem(column)
        if header is not None and header.text() == title:
            return column
    raise AssertionError(title)


def _row_for_worker(table, worker_id: int) -> int:
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() == str(worker_id):
            return row
    raise AssertionError(worker_id)


class EmployeeCentral2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.employees_before = _count("test_employees")
        cls.exams_before = _count("test_exams")

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.role_a = responsibility_role_service.create_role(
            name=f"Mistr {self.marker}"
        )
        self.role_b = responsibility_role_service.create_role(
            name=f"Svářeč {self.marker}"
        )

    def test_new_employee_defaults_hints_and_list(self) -> None:
        dialog = ThpWorkerDialog()
        self.assertEqual(dialog.windowTitle(), "Nový zaměstnanec")
        self.assertTrue(dialog.active_checkbox.isChecked())
        self.assertFalse(dialog.is_thp_checkbox.isChecked())
        self.assertFalse(dialog.performs_controls_checkbox.isChecked())
        self.assertFalse(dialog.may_examine.isChecked())
        self.assertEqual(dialog.position_hint.text(), POSITION_HINT)
        self.assertEqual(dialog.position_hint.objectName(), "MutedText")
        self.assertTrue(dialog.position_hint.wordWrap())
        self.assertIn(
            "koordinaci bozp",
            dialog.position.toolTip().casefold().replace("\n", " "),
        )
        self.assertEqual(dialog.roles_hint.text(), ROLES_HINT)
        self.assertEqual(dialog.roles_hint.objectName(), "MutedText")
        self.assertIn(
            "nemění údaj",
            dialog.roles.toolTip().casefold().replace("\n", " "),
        )

        number = f"OC-{self.marker}"
        dialog.title_before.setText("Bc.")
        dialog.first_name.setText("  Eva  ")
        dialog.last_name.setText("  Nováková  ")
        dialog.title_after.setText("DiS.")
        dialog.position.setText("Svářečka")
        dialog.phone.setText("777000111")
        dialog.email.setText(f"eva{self.marker}@example.test")
        dialog.personal_number.setText(f"  {number}  ")
        dialog.workplace.set_workplace_id(self.workplace.id)
        dialog.roles.set_role_ids([self.role_a.id, self.role_b.id])
        dialog.accept()

        saved = settings_service.get_worker_by_id(dialog.saved_worker_id)
        assert saved is not None
        self.assertEqual(saved.first_name, "Eva")
        self.assertEqual(saved.last_name, "Nováková")
        self.assertEqual(saved.title_before, "Bc.")
        self.assertEqual(saved.title_after, "DiS.")
        self.assertEqual(saved.position, "Svářečka")
        self.assertEqual(saved.phone, "777000111")
        self.assertEqual(saved.personal_number, number)
        self.assertEqual(saved.workplace_id, self.workplace.id)
        self.assertFalse(saved.is_thp)
        self.assertFalse(saved.may_examine)
        self.assertFalse(saved.performs_controls)
        self.assertTrue(saved.active)
        self.assertEqual(
            settings_service.list_worker_role_ids(saved.id),
            [self.role_a.id, self.role_b.id],
        )

        page = NastaveniPage()
        self.assertEqual(page.tabs.tabText(0), "Zaměstnanci")
        button_texts = [button.text() for button in page.findChildren(QPushButton)]
        self.assertIn("Přidat zaměstnance", button_texts)
        self.assertIn("Aktivovat", button_texts)
        self.assertIn("Deaktivovat", button_texts)
        page.worker_filter.setCurrentText("Všichni")
        row = _row_for_worker(page.worker_table, saved.id)
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Osobní číslo")).text(),
            number,
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Jméno")).text(),
            "Eva",
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Příjmení")).text(),
            "Nováková",
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Funkce")).text(),
            "Svářečka",
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Provoz")).text(),
            self.workplace.name,
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Vedoucí / THP")).text(),
            "Ne",
        )
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Aktivní")).text(),
            "Ano",
        )
        self.assertEqual(_count("test_employees"), self.employees_before)
        self.assertEqual(_count("test_exams"), self.exams_before)

    def test_edit_existing_thp_saves_new_fields_without_changing_position(self) -> None:
        worker = settings_service.save_worker(
            title_before="Ing.",
            first_name="Adam",
            last_name=f"Dvořák{self.marker}",
            position="Bezpečnostní technik",
            phone="111",
            performs_controls=True,
        )
        self.assertTrue(worker.is_thp)

        dialog = ThpWorkerDialog(worker=worker)
        self.assertEqual(dialog.windowTitle(), "Upravit zaměstnance")
        self.assertTrue(dialog.is_thp_checkbox.isChecked())
        self.assertTrue(dialog.performs_controls_checkbox.isChecked())
        self.assertEqual(dialog.position.text(), "Bezpečnostní technik")

        number = f"THP-{self.marker}"
        dialog.personal_number.setText(number)
        dialog.workplace.set_workplace_id(self.workplace.id)
        dialog.roles.set_role_ids([self.role_b.id, self.role_a.id])
        dialog.may_examine.setChecked(True)
        dialog.phone.setText("222")
        dialog.accept()

        stored = settings_service.get_worker_by_id(worker.id)
        assert stored is not None
        self.assertTrue(stored.is_thp)
        self.assertTrue(stored.performs_controls)
        self.assertTrue(stored.may_examine)
        self.assertEqual(stored.position, "Bezpečnostní technik")
        self.assertEqual(stored.personal_number, number)
        self.assertEqual(stored.workplace_id, self.workplace.id)
        self.assertEqual(stored.phone, "222")
        self.assertEqual(
            settings_service.list_worker_role_ids(worker.id),
            [self.role_b.id, self.role_a.id],
        )

        partial = settings_service.save_worker(id=worker.id, email="adam@example.test")
        self.assertEqual(partial.email, "adam@example.test")
        self.assertTrue(partial.is_thp)
        self.assertEqual(partial.personal_number, number)
        self.assertEqual(
            settings_service.list_worker_role_ids(worker.id),
            [self.role_b.id, self.role_a.id],
        )

    def test_personal_number_unique_when_filled_and_blank_repeats(self) -> None:
        first = settings_service.save_worker(
            first_name="Ema",
            last_name=f"První{self.marker}",
            personal_number="   ",
            is_thp=False,
        )
        second = settings_service.save_worker(
            first_name="Ema",
            last_name=f"Druhá{self.marker}",
            personal_number="",
            is_thp=False,
        )
        self.assertIsNone(first.personal_number)
        self.assertIsNone(second.personal_number)

        number = f"UNIQ-{self.marker}"
        occupied = settings_service.save_worker(
            id=first.id,
            personal_number=number,
        )
        self.assertEqual(occupied.personal_number, number)
        self.assertFalse(occupied.is_thp)

        with self.assertRaises(SettingsWorkerError) as raised:
            settings_service.save_worker(
                first_name="Ema",
                last_name=f"Třetí{self.marker}",
                personal_number=number,
                is_thp=False,
            )
        self.assertIn(number, str(raised.exception))

        dialog = ThpWorkerDialog()
        dialog.first_name.setText("Ema")
        dialog.last_name.setText(f"Čtvrtá{self.marker}")
        dialog.personal_number.setText(number)
        with patch.object(QMessageBox, "warning") as warning:
            dialog.accept()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIn(number, warning.call_args.args[2])
        self.assertIsNone(dialog.saved_worker_id)

    def test_validation_requires_names_and_existing_catalog_values(self) -> None:
        with self.assertRaises(SettingsWorkerError):
            settings_service.save_worker(first_name="  ", last_name="Novák", is_thp=False)
        with self.assertRaises(SettingsWorkerError):
            settings_service.save_worker(
                first_name="Eva",
                last_name="Novák",
                workplace_id=999_999,
                is_thp=False,
            )
        with self.assertRaises(SettingsWorkerError):
            settings_service.save_worker(
                first_name="Eva",
                last_name="Novák",
                responsibility_role_ids=[999_999],
                is_thp=False,
            )

        dialog = ThpWorkerDialog()
        dialog.first_name.setText("   ")
        dialog.last_name.setText("Novák")
        with patch.object(QMessageBox, "warning") as warning:
            dialog.accept()
        self.assertIn("Vyplňte jméno.", warning.call_args.args[2])
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

        dialog.workplace.setCurrentText("Neexistující provoz")
        dialog.first_name.setText("Eva")
        with patch.object(QMessageBox, "warning") as warning:
            dialog.accept()
        self.assertIn("neexistuje", warning.call_args.args[2])

    def test_activation_checkbox_and_list_buttons_share_active_flag(self) -> None:
        dialog = ThpWorkerDialog()
        dialog.first_name.setText("Petr")
        dialog.last_name.setText(f"Aktivní{self.marker}")
        dialog.position.setText("Operátor")
        dialog.roles.set_role_ids([self.role_a.id])
        dialog.accept()
        worker_id = dialog.saved_worker_id
        assert worker_id is not None
        before = _count("thp_workers")

        page = NastaveniPage()
        page.worker_filter.setCurrentText("Všichni")
        row = _row_for_worker(page.worker_table, worker_id)
        page.worker_table.selectRow(row)
        page.update_worker_buttons()
        self.assertTrue(page.worker_edit_button.isEnabled())
        self.assertTrue(page.worker_deactivate_button.isEnabled())
        self.assertFalse(page.worker_activate_button.isEnabled())

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            page.deactivate_selected_worker()

        stored = settings_service.get_worker_by_id(worker_id)
        assert stored is not None
        self.assertFalse(stored.active)
        self.assertEqual(_count("thp_workers"), before)
        self.assertEqual(
            settings_service.list_worker_role_ids(worker_id),
            [self.role_a.id],
        )

        editor = ThpWorkerDialog(worker=stored)
        self.assertFalse(editor.active_checkbox.isChecked())
        editor.active_checkbox.setChecked(True)
        editor.accept()
        stored = settings_service.get_worker_by_id(worker_id)
        assert stored is not None
        self.assertTrue(stored.active)

        page.refresh_workers()
        row = _row_for_worker(page.worker_table, worker_id)
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Aktivní")).text(),
            "Ano",
        )

        editor = ThpWorkerDialog(worker=stored)
        editor.active_checkbox.setChecked(False)
        editor.accept()
        page.worker_filter.setCurrentText("Všichni")
        page.refresh_workers()
        row = _row_for_worker(page.worker_table, worker_id)
        self.assertEqual(
            page.worker_table.item(row, _header_index(page.worker_table, "Aktivní")).text(),
            "Ne",
        )
        page.worker_table.selectRow(row)
        page.update_worker_buttons()
        self.assertTrue(page.worker_activate_button.isEnabled())
        self.assertFalse(page.worker_deactivate_button.isEnabled())

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            page.activate_selected_worker()
        stored = settings_service.get_worker_by_id(worker_id)
        assert stored is not None
        self.assertTrue(stored.active)
        self.assertEqual(
            settings_service.list_worker_role_ids(worker_id),
            [self.role_a.id],
        )

        page.worker_filter.setCurrentText("Aktivní")
        visible_ids = [
            int(page.worker_table.item(row, 0).text())
            for row in range(page.worker_table.rowCount())
        ]
        self.assertIn(worker_id, visible_ids)

    def test_pickers_keep_leading_workers_and_historical_ids(self) -> None:
        ordinary = settings_service.save_worker(
            first_name="Řadový",
            last_name=f"Zaměstnanec{self.marker}",
            position="Dělník",
            is_thp=False,
            performs_controls=False,
            may_examine=False,
        )
        leading = settings_service.save_worker(
            first_name="Vedoucí",
            last_name=f"Technik{self.marker}",
            performs_controls=True,
        )
        leading_without_controls = settings_service.save_worker(
            first_name="Vedoucí",
            last_name=f"BezKontrol{self.marker}",
            performs_controls=False,
        )
        inactive = settings_service.save_worker(
            first_name="Bývalý",
            last_name=f"Vedoucí{self.marker}",
        )
        settings_service.deactivate_worker(inactive.id)

        self.assertFalse(ordinary.is_thp)
        self.assertTrue(leading.is_thp)

        listed = {worker.id for worker in settings_service.get_workers()}
        self.assertIn(ordinary.id, listed)
        self.assertIn(leading.id, listed)
        leading_ids = {
            worker.id
            for worker in settings_service.get_workers(leading_only=True)
        }
        self.assertNotIn(ordinary.id, leading_ids)
        self.assertIn(leading.id, leading_ids)
        self.assertNotIn(inactive.id, leading_ids)

        selector = ThpWorkerSelector()
        offered = {
            selector.itemData(index)
            for index in range(selector.count())
            if isinstance(selector.itemData(index), int)
        }
        self.assertNotIn(ordinary.id, offered)
        self.assertNotIn(inactive.id, offered)
        self.assertIn(leading.id, offered)
        self.assertIn(leading_without_controls.id, offered)

        selector.set_person_id(ordinary.id)
        self.assertEqual(selector.current_person_id(), ordinary.id)
        selector.set_person_id(inactive.id)
        self.assertEqual(selector.current_person_id(), inactive.id)
        self.assertIn("(neaktivní)", selector.currentText())

        typeahead = MeetingPersonTypeahead()
        meeting_ids = set()
        for index in range(typeahead.count()):
            data = typeahead.itemData(index)
            if (
                isinstance(data, dict)
                and data.get("source_type") == MEETING_SOURCE_THP_WORKER
            ):
                meeting_ids.add(int(data["source_id"]))
        self.assertNotIn(ordinary.id, meeting_ids)
        self.assertIn(leading.id, meeting_ids)
        typeahead.set_ref(
            {
                "source_type": MEETING_SOURCE_THP_WORKER,
                "source_id": ordinary.id,
            }
        )
        current = typeahead.current_ref()
        assert current is not None
        self.assertEqual(current["source_id"], ordinary.id)

        control_ids = {
            worker.id for worker in settings_service.get_workers_for_controls()
        }
        self.assertNotIn(ordinary.id, control_ids)
        self.assertNotIn(leading_without_controls.id, control_ids)
        self.assertIn(leading.id, control_ids)
        self.assertIsNotNone(settings_service.get_worker_by_id(ordinary.id))
        self.assertEqual(_count("test_employees"), self.employees_before)
        self.assertEqual(_count("test_exams"), self.exams_before)


if __name__ == "__main__":
    unittest.main()
