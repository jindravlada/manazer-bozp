"""EMPLOYEE-CENTRAL-12: dialog propojení a převzetí údajů."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-12-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui.employee_link_dialog import EmployeeLinkDialog
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.testy.constants import EXAMINER_MODE_NONE, VALIDITY_UNIT_YEARS
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(storage_module.storage_service.database_path))
    connection.row_factory = sqlite3.Row
    return connection


def _count(table: str) -> int:
    connection = _connect()
    try:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        connection.close()


def _rows(table: str) -> list[tuple]:
    connection = _connect()
    try:
        return list(connection.execute(f'SELECT * FROM "{table}" ORDER BY id'))
    finally:
        connection.close()


def _row_for(table, personal_number: str) -> int:
    for row in range(table.rowCount()):
        item = table.item(row, 1)
        if item is not None and item.text() == personal_number:
            return row
    raise AssertionError(personal_number)


def _row_containing(table, text: str) -> int:
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None and item.text() == text:
                return row
    raise AssertionError(text)


def _proposal_row(dialog: EmployeeLinkDialog, label: str):
    for row in range(dialog.proposal_table.rowCount()):
        item = dialog.proposal_table.item(row, 0)
        if item is not None and item.text() == label:
            return row
    raise AssertionError(label)


def _check(dialog: EmployeeLinkDialog, label: str) -> None:
    item = dialog.proposal_table.item(_proposal_row(dialog, label), 3)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)


class EmployeeCentral12TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.dialogs: list[EmployeeLinkDialog] = []
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.other = settings_service.save_workplace(
            name=f"Jiný provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.kept_role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")
        self.extra_role = responsibility_role_service.create_role(
            name=f"Zámečník {self.marker}"
        )

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()

    def _dialog(self, worker_id: int) -> EmployeeLinkDialog:
        dialog = EmployeeLinkDialog(worker_id=worker_id)
        self.dialogs.append(dialog)
        return dialog

    def _employee(self, number: str, first: str, last: str, **extra):
        data = {
            "personal_number": number,
            "first_name": first,
            "last_name": last,
            "title_before": "Bc.",
            "workplace_id": self.other.id,
            "responsibility_role_ids": [self.kept_role.id, self.extra_role.id],
            "may_examine": True,
            "active": True,
        }
        data.update(extra)
        return test_employee_service.create_employee(**data)

    def _worker(self, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "title_before": "Ing.",
            "position": f"Svářeč {self.marker}",
            "personal_number": "",
            "workplace_id": None,
            "responsibility_role_ids": [self.kept_role.id],
            "active": True,
            "is_thp": True,
            "may_examine": False,
            "performs_controls": True,
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _select(self, dialog: EmployeeLinkDialog, number: str) -> None:
        dialog.employee_table.selectRow(_row_for(dialog.employee_table, number))

    def test_dialog_offers_manual_choice_and_search(self) -> None:
        worker = self._worker("Eva", f"Centrální{self.marker}", personal_number=f"H-{self.marker}")
        self._worker("Adam", f"Druhý{self.marker}")
        match = self._employee(f"H-{self.marker}", "Jana", f"Shoda{self.marker}")
        other_employee = self._employee(
            f"J-{self.marker}",
            "Petr",
            f"Jiný{self.marker}",
            active=False,
        )
        links_before = _count("test_employee_central_links")
        page = NastaveniPage()
        self.assertFalse(page.worker_link_button.isEnabled())
        page.worker_table.selectRow(
            _row_containing(page.worker_table, f"Centrální{self.marker}")
        )
        page.update_worker_buttons()
        self.assertTrue(page.worker_link_button.isEnabled())
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        page.worker_table.selectionModel().clearSelection()
        for name in (f"Centrální{self.marker}", f"Druhý{self.marker}"):
            page.worker_table.selectionModel().select(
                page.worker_table.model().index(_row_containing(page.worker_table, name), 0),
                flags,
            )
        page.update_worker_buttons()
        self.assertFalse(page.worker_link_button.isEnabled())

        dialog = self._dialog(worker.id)
        self.assertEqual(dialog.windowTitle(), "Propojit s Testy")
        self.assertEqual(dialog.employee_table.currentRow(), -1)
        self.assertIn(match.display_name, dialog.hint_label.text())
        self.assertIn("nápovědu", dialog.hint_label.text())
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertFalse(dialog.confirm_button.isEnabled())
        self._select(dialog, other_employee.personal_number)
        self.assertTrue(dialog.confirm_button.isEnabled())
        self.assertGreater(dialog.proposal_table.rowCount(), 0)
        dialog.employee_filter.search_edit.setText(f"jiný{self.marker}")
        self.assertFalse(
            dialog.employee_table.isRowHidden(_row_for(dialog.employee_table, f"J-{self.marker}"))
        )
        self.assertTrue(
            dialog.employee_table.isRowHidden(_row_for(dialog.employee_table, f"H-{self.marker}"))
        )
        dialog.employee_filter.search_edit.setText("petr")
        self.assertFalse(
            dialog.employee_table.isRowHidden(_row_for(dialog.employee_table, f"J-{self.marker}"))
        )
        dialog.employee_filter.search_edit.setText(f"J-{self.marker}")
        self.assertFalse(
            dialog.employee_table.isRowHidden(_row_for(dialog.employee_table, f"J-{self.marker}"))
        )
        self.assertEqual(_count("test_employee_central_links"), links_before)

    def test_confirm_selected_fields_updates_the_worker_list(self) -> None:
        worker = self._worker("Eva", f"Centrální{self.marker}")
        employee = self._employee(f"T-{self.marker}", "Jana", f"Testová{self.marker}")
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(topic_id=topic.id, text=f"Otázka {self.marker}")
        test = test_definition_service.create_test(
            name=f"Historie {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2024, 6, 1),
        )
        exams_before = _rows("test_exams")
        page = NastaveniPage()
        page.worker_table.selectRow(
            _row_containing(page.worker_table, f"Centrální{self.marker}")
        )

        def run(dialog: EmployeeLinkDialog) -> int:
            self._select(dialog, employee.personal_number)
            roles = dialog.proposal_table.item(_proposal_row(dialog, "Funkce / role"), 3)
            assert roles is not None
            self.assertIn(f"Zámečník {self.marker}", roles.text())
            self.assertTrue(bool(roles.flags() & Qt.ItemFlag.ItemIsUserCheckable))
            _check(dialog, "Osobní číslo")
            _check(dialog, "Funkce / role")
            dialog._confirm()
            return int(dialog.result())

        with (
            patch.object(EmployeeLinkDialog, "exec", run),
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(QMessageBox, "information") as info,
        ):
            page.link_selected_worker()
        info.assert_called()
        self.assertIn("převzaty", info.call_args.args[2])
        saved = settings_service.get_worker_by_id(worker.id)
        assert saved is not None
        self.assertEqual(saved.personal_number, f"T-{self.marker}")
        self.assertIsNone(saved.workplace_id)
        self.assertFalse(saved.may_examine)
        self.assertEqual(saved.position, f"Svářeč {self.marker}")
        self.assertTrue(saved.is_thp)
        self.assertEqual(
            settings_service.list_worker_role_ids(worker.id),
            [self.kept_role.id, self.extra_role.id],
        )
        self.assertEqual(_rows("test_exams"), exams_before)
        selected = page.worker_table.selectionModel().selectedRows()
        self.assertEqual(len(selected), 1)
        self.assertEqual(
            page.worker_table.item(selected[0].row(), 0).text(),
            str(worker.id),
        )
        self.assertEqual(
            page.worker_table.item(selected[0].row(), 1).text(),
            f"T-{self.marker}",
        )

    def test_link_without_takeover_and_cancel_write_nothing_extra(self) -> None:
        links_before = _count("test_employee_central_links")
        worker = self._worker("Eva", f"Centrální{self.marker}")
        employee = self._employee(f"T-{self.marker}", "Jana", f"Testová{self.marker}")
        dialog = self._dialog(worker.id)
        self._select(dialog, employee.personal_number)
        _check(dialog, "Osobní číslo")
        dialog.cancel_button.click()
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertIsNone(settings_service.get_worker_by_id(worker.id).personal_number)

        again = self._dialog(worker.id)
        self._select(again, employee.personal_number)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            again._confirm()
        self.assertEqual(_count("test_employee_central_links"), links_before)

        with (
            patch.object(QMessageBox, "question") as question,
            patch.object(QMessageBox, "information"),
        ):
            question.return_value = QMessageBox.StandardButton.Yes
            again._confirm()
        self.assertIn("Žádné údaje se nepřevezmou", question.call_args.args[2])
        self.assertIsNone(settings_service.get_worker_by_id(worker.id).personal_number)
        self.assertIsNone(settings_service.get_worker_by_id(worker.id).workplace_id)
        link = employee_central_link_service.get_by_worker(worker.id)
        assert link is not None
        self.assertEqual(link.test_employee_id, employee.id)

    def test_already_linked_pair_can_be_completed(self) -> None:
        worker = self._worker("Eva", f"Centrální{self.marker}")
        employee = self._employee(f"T-{self.marker}", "Jana", f"Testová{self.marker}")
        link = employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        dialog = self._dialog(worker.id)
        self.assertTrue(dialog.picker_box.isHidden())
        self.assertIn(employee.display_name, dialog.locked_label.text())
        self.assertTrue(dialog.confirm_button.isEnabled())
        _check(dialog, "Provoz")
        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as question,
            patch.object(QMessageBox, "information"),
        ):
            dialog._confirm()
        self.assertIn("znovu se nezaloží", question.call_args.args[2])
        self.assertIn(self.other.name, question.call_args.args[2])
        saved = settings_service.get_worker_by_id(worker.id)
        assert saved is not None
        self.assertEqual(saved.workplace_id, self.other.id)
        self.assertIsNone(saved.personal_number)
        kept = employee_central_link_service.get_by_worker(worker.id)
        assert kept is not None
        self.assertEqual(kept.id, link.id)
        self.assertEqual(
            employee_central_link_service.get_by_test_employee(employee.id).id,
            link.id,
        )

    def test_occupied_link_and_changed_data_are_refused(self) -> None:
        holder = self._worker("Adam", f"Držitel{self.marker}")
        worker = self._worker("Eva", f"Centrální{self.marker}")
        employee = self._employee(f"T-{self.marker}", "Jana", f"Testová{self.marker}")
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=holder.id,
        )
        blocked = self._dialog(worker.id)
        self._select(blocked, employee.personal_number)
        self.assertFalse(blocked.confirm_button.isEnabled())
        self.assertIn("již propojen", blocked.status_label.text())
        blocked._confirm()
        self.assertEqual(employee_central_link_service.get_by_worker(worker.id), None)

        fresh_employee = self._employee(f"N-{self.marker}", "Lea", f"Nová{self.marker}")
        dialog = self._dialog(worker.id)
        self._select(dialog, fresh_employee.personal_number)
        settings_service.save_worker(id=worker.id, personal_number=f"Z-{self.marker}")
        _check(dialog, "Osobní číslo")
        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as question,
            patch.object(QMessageBox, "warning") as warning,
        ):
            dialog._confirm()
        warning.assert_called()
        self.assertIn("nový návrh", warning.call_args.args[2])
        self.assertIn("Načíst nový návrh?", question.call_args_list[-1].args[2])
        number = dialog.proposal_table.item(_proposal_row(dialog, "Osobní číslo"), 2)
        assert number is not None
        self.assertEqual(number.text(), f"Z-{self.marker}")
        choice = dialog.proposal_table.item(_proposal_row(dialog, "Osobní číslo"), 3)
        assert choice is not None
        self.assertIsNone(choice.data(Qt.ItemDataRole.UserRole))
        self.assertEqual(settings_service.get_worker_by_id(worker.id).personal_number, f"Z-{self.marker}")
        self.assertIsNone(employee_central_link_service.get_by_worker(worker.id))
