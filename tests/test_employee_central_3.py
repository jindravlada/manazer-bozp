"""EMPLOYEE-CENTRAL-3: výslovné propojení zaměstnanců z Testů."""

from __future__ import annotations

import importlib
import inspect
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-3-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_test_employee_central_links,
        initialize_database,
    )

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        EmployeeLinkError,
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.sluzby.test_employee_service import test_employee_service


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _select_all(table: str) -> list[tuple]:
    connection = _connect()
    try:
        return list(connection.execute(f'SELECT * FROM "{table}" ORDER BY id'))
    finally:
        connection.close()


def _count(table: str) -> int:
    connection = _connect()
    try:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        connection.close()


def _index_names(table: str) -> set[str]:
    connection = _connect()
    try:
        return {
            str(row[1])
            for row in connection.execute(f'PRAGMA index_list("{table}")').fetchall()
        }
    finally:
        connection.close()


def _worker_view(worker_id: int) -> tuple:
    worker = settings_service.get_worker_by_id(worker_id)
    assert worker is not None
    return (
        worker.title_before,
        worker.first_name,
        worker.last_name,
        worker.title_after,
        worker.position,
        worker.phone,
        worker.email,
        worker.personal_number,
        worker.workplace_id,
        bool(worker.is_thp),
        bool(worker.may_examine),
        bool(worker.active),
        bool(worker.performs_controls),
        tuple(settings_service.list_worker_role_ids(worker_id)),
    )


def _insert_history(employee_id: int, marker: str, workplace_name: str) -> None:
    created_at = "2024-06-01 10:00:00"
    connection = _connect()
    try:
        definition = connection.execute(
            """
            INSERT INTO test_definitions (
                name, description, active, uses_written, allowed_wrong_answers,
                seconds_per_question, uses_oral, examiner_mode, validity_value,
                validity_unit, created_at, updated_at
            ) VALUES (?, '', 1, 1, 1, 30, 0, 'single', 2, 'year', ?, ?)
            """,
            (f"Test {marker}", created_at, created_at),
        )
        definition_id = int(definition.lastrowid)
        exam = connection.execute(
            """
            INSERT INTO test_exams (
                employee_id, test_definition_id, exam_date, status, examiner_mode,
                employee_personal_number, employee_first_name, employee_last_name,
                employee_title_before, employee_title_after, employee_display_name,
                employee_workplace_name, employee_roles_text, test_name,
                uses_written, uses_oral, allowed_wrong_answers, seconds_per_question,
                written_duration_seconds, validity_value, validity_unit, created_at,
                written_finish_reason, written_technical_detail
            ) VALUES (
                ?, ?, '2024-06-01', 'prepared', 'single',
                'OC', 'Jana', 'Malá', 'Bc.', '', 'Bc. Jana Malá',
                ?, 'Mistr', ?,
                1, 0, 1, 30, 30, 2, 'year', ?,
                '', ''
            )
            """,
            (employee_id, definition_id, workplace_name, f"Test {marker}", created_at),
        )
        connection.execute(
            """
            INSERT INTO test_exam_examiners (
                exam_id, employee_id, display_name, role, position
            ) VALUES (?, ?, 'Bc. Jana Malá', 'examiner', 1)
            """,
            (int(exam.lastrowid), employee_id),
        )
        connection.execute(
            """
            INSERT INTO test_exam_validity_tracking (employee_id, test_definition_id)
            VALUES (?, ?)
            """,
            (employee_id, definition_id),
        )
        connection.commit()
    finally:
        connection.close()


class EmployeeCentral3TestCase(unittest.TestCase):
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

    def _employee(self, **overrides):
        data = {
            "personal_number": f"TE-{self.marker}-{uuid.uuid4().hex[:4]}",
            "first_name": "Jana",
            "last_name": f"Malá{self.marker}",
            "title_before": "Bc.",
            "title_after": "DiS.",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role_a.id, self.role_b.id],
            "may_examine": True,
            "active": True,
        }
        data.update(overrides)
        return test_employee_service.create_employee(**data)

    def test_migration_creates_empty_map_and_repeat_keeps_data(self) -> None:
        source = inspect.getsource(_ensure_test_employee_central_links)
        self.assertNotIn("INSERT", source.upper())
        self.assertNotIn("UPDATE", source.upper())
        self.assertNotIn("test_exams", source)

        names = _index_names("test_employee_central_links")
        self.assertIn("uq_test_employee_central_links_employee", names)
        self.assertIn("uq_test_employee_central_links_worker", names)

        employee = self._employee()
        _insert_history(employee.id, self.marker, self.workplace.name)
        worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"Jiný{self.marker}",
            position="Vedoucí",
            phone="601",
            personal_number=f"THP-{self.marker}",
            performs_controls=True,
        )
        link = employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )

        employees = _select_all("test_employees")
        roles = _select_all("test_employee_roles")
        exams = _select_all("test_exams")
        examiners = _select_all("test_exam_examiners")
        tracking = _select_all("test_exam_validity_tracking")
        links = _select_all("test_employee_central_links")
        workers = _select_all("thp_workers")

        initialize_database()

        self.assertEqual(_select_all("test_employees"), employees)
        self.assertEqual(_select_all("test_employee_roles"), roles)
        self.assertEqual(_select_all("test_exams"), exams)
        self.assertEqual(_select_all("test_exam_examiners"), examiners)
        self.assertEqual(_select_all("test_exam_validity_tracking"), tracking)
        self.assertEqual(_select_all("test_employee_central_links"), links)
        self.assertEqual(_select_all("thp_workers"), workers)
        kept = employee_central_link_service.get_by_test_employee(employee.id)
        assert kept is not None
        self.assertEqual(kept.id, link.id)
        self.assertEqual(kept.thp_worker_id, worker.id)

        connection = _connect()
        try:
            connection.execute("DROP TABLE test_employee_central_links")
            connection.commit()
        finally:
            connection.close()

        initialize_database()
        self.assertEqual(_count("test_employee_central_links"), 0)
        self.assertEqual(_select_all("test_employees"), employees)
        self.assertEqual(_select_all("test_exams"), exams)
        self.assertIsNone(
            employee_central_link_service.get_by_test_employee(employee.id)
        )
        initialize_database()
        self.assertEqual(_count("test_employee_central_links"), 0)
        self.assertEqual(_select_all("test_exams"), exams)
        self.assertIn(
            "uq_test_employee_central_links_employee",
            _index_names("test_employee_central_links"),
        )

    def test_link_existing_keeps_both_records_and_history(self) -> None:
        employee = self._employee(personal_number=f"SRC-{self.marker}")
        _insert_history(employee.id, f"link-{self.marker}", self.workplace.name)
        worker = settings_service.save_worker(
            title_before="Ing.",
            first_name="Petr",
            last_name=f"Starý{self.marker}",
            title_after="CSc.",
            position="Vedoucí provozu",
            phone="777111222",
            email=f"petr{self.marker}@example.test",
            personal_number=f"OLD-{self.marker}",
            workplace_id=self.workplace.id,
            performs_controls=True,
            may_examine=False,
            active=True,
        )
        before_worker = _worker_view(worker.id)
        before_employee = _select_all("test_employees")
        before_roles = _select_all("test_employee_roles")
        before_exams = _select_all("test_exams")
        before_examiners = _select_all("test_exam_examiners")
        before_tracking = _select_all("test_exam_validity_tracking")

        link = employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )

        self.assertEqual(link.test_employee_id, employee.id)
        self.assertEqual(link.thp_worker_id, worker.id)
        self.assertEqual(_worker_view(worker.id), before_worker)
        self.assertTrue(before_worker[9])
        self.assertTrue(before_worker[12])
        self.assertEqual(_select_all("test_employees"), before_employee)
        self.assertEqual(_select_all("test_employee_roles"), before_roles)
        self.assertEqual(_select_all("test_exams"), before_exams)
        self.assertEqual(_select_all("test_exam_examiners"), before_examiners)
        self.assertEqual(_select_all("test_exam_validity_tracking"), before_tracking)

    def test_create_and_link_copies_test_data_without_touching_source(self) -> None:
        employee = self._employee(
            personal_number=f"NEW-{self.marker}",
            first_name="  Eva  ".strip(),
            last_name=f"Nová{self.marker}",
            may_examine=True,
            active=True,
        )
        _insert_history(employee.id, f"new-{self.marker}", self.workplace.name)
        before_employee = _select_all("test_employees")
        before_roles = _select_all("test_employee_roles")
        before_exams = _select_all("test_exams")
        before_examiners = _select_all("test_exam_examiners")
        before_tracking = _select_all("test_exam_validity_tracking")
        workers_before = _count("thp_workers")

        link = employee_central_link_service.create_and_link(employee.id)
        created = settings_service.get_worker_by_id(link.thp_worker_id)
        assert created is not None

        self.assertEqual(_count("thp_workers"), workers_before + 1)
        self.assertEqual(created.personal_number, f"NEW-{self.marker}")
        self.assertEqual(created.title_before, "Bc.")
        self.assertEqual(created.first_name, "Eva")
        self.assertEqual(created.last_name, f"Nová{self.marker}")
        self.assertEqual(created.title_after, "DiS.")
        self.assertEqual(created.workplace_id, self.workplace.id)
        self.assertEqual(
            settings_service.list_worker_role_ids(created.id),
            [self.role_a.id, self.role_b.id],
        )
        self.assertTrue(created.active)
        self.assertTrue(created.may_examine)
        self.assertFalse(created.is_thp)
        self.assertFalse(created.performs_controls)
        self.assertEqual(created.position, "")
        self.assertEqual(created.phone, "")
        self.assertEqual(created.email, "")
        self.assertEqual(_select_all("test_employees"), before_employee)
        self.assertEqual(_select_all("test_employee_roles"), before_roles)
        self.assertEqual(_select_all("test_exams"), before_exams)
        self.assertEqual(_select_all("test_exam_examiners"), before_examiners)
        self.assertEqual(_select_all("test_exam_validity_tracking"), before_tracking)
        stored = test_employee_service.get_employee(employee.id)
        assert stored is not None
        self.assertTrue(stored.active)

        with self.assertRaises(EmployeeLinkError):
            employee_central_link_service.create_and_link(employee.id)
        self.assertEqual(_count("thp_workers"), workers_before + 1)

    def test_duplicate_links_are_rejected(self) -> None:
        first = self._employee(last_name=f"První{self.marker}")
        second = self._employee(last_name=f"Druhá{self.marker}")
        worker_a = settings_service.save_worker(
            first_name="Adam",
            last_name=f"A{self.marker}",
        )
        worker_b = settings_service.save_worker(
            first_name="Bára",
            last_name=f"B{self.marker}",
        )
        link = employee_central_link_service.link_existing(
            test_employee_id=first.id,
            thp_worker_id=worker_a.id,
        )
        links_before_repeat = _count("test_employee_central_links")
        again = employee_central_link_service.link_existing(
            test_employee_id=first.id,
            thp_worker_id=worker_a.id,
        )
        self.assertEqual(again.id, link.id)
        self.assertEqual(_count("test_employee_central_links"), links_before_repeat)
        links_after_repeat = links_before_repeat

        with self.assertRaises(EmployeeLinkError):
            employee_central_link_service.link_existing(
                test_employee_id=first.id,
                thp_worker_id=worker_b.id,
            )
        with self.assertRaises(EmployeeLinkError):
            employee_central_link_service.link_existing(
                test_employee_id=second.id,
                thp_worker_id=worker_a.id,
            )
        self.assertEqual(_count("test_employee_central_links"), links_after_repeat)

        connection = _connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO test_employee_central_links (
                        test_employee_id, thp_worker_id, created_at
                    ) VALUES (?, ?, '2024-01-01 00:00:00')
                    """,
                    (second.id, worker_a.id),
                )
                connection.commit()
            connection.rollback()
        finally:
            connection.close()

    def test_hint_does_not_link_and_same_name_stays_separate(self) -> None:
        number = f"HINT-{self.marker}"
        employee = self._employee(
            personal_number=number,
            first_name="Eva",
            last_name=f"Stejná{self.marker}",
        )
        same_number = settings_service.save_worker(
            first_name="Jiná",
            last_name=f"Osoba{self.marker}",
            personal_number=number,
            position="Původní funkce",
            phone="123",
            performs_controls=True,
        )
        namesake = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Stejná{self.marker}",
            personal_number=f"JINÉ-{self.marker}",
            position="Jmenovec",
        )
        before_same = _worker_view(same_number.id)
        before_name = _worker_view(namesake.id)

        hints = employee_central_link_service.personal_number_hints(employee.id)
        self.assertEqual([worker.id for worker in hints], [same_number.id])
        self.assertIsNone(
            employee_central_link_service.get_by_test_employee(employee.id)
        )
        self.assertIsNone(employee_central_link_service.get_by_worker(namesake.id))
        self.assertEqual(self._links_touching(employee.id), 0)

        workers_before = _count("thp_workers")
        with self.assertRaises(EmployeeLinkError) as raised:
            employee_central_link_service.create_and_link(employee.id)
        self.assertIn(number, str(raised.exception))
        self.assertEqual(_count("thp_workers"), workers_before)
        self.assertIsNone(
            employee_central_link_service.get_by_test_employee(employee.id)
        )
        self.assertEqual(_worker_view(same_number.id), before_same)

        other = self._employee(
            personal_number=f"FREE-{self.marker}",
            first_name="Eva",
            last_name=f"Stejná{self.marker}",
        )
        created = employee_central_link_service.create_and_link(other.id)
        self.assertNotEqual(created.thp_worker_id, namesake.id)
        self.assertIsNone(employee_central_link_service.get_by_worker(namesake.id))
        self.assertEqual(_worker_view(namesake.id), before_name)
        self.assertFalse(_worker_view(created.thp_worker_id)[9])

    def test_failed_create_does_not_leave_a_partial_worker(self) -> None:
        employee = self._employee(personal_number=f"FAIL-{self.marker}")
        _insert_history(employee.id, f"fail-{self.marker}", self.workplace.name)
        before_employee = _select_all("test_employees")
        before_exams = _select_all("test_exams")
        before_examiners = _select_all("test_exam_examiners")
        before_tracking = _select_all("test_exam_validity_tracking")
        workers_before = _count("thp_workers")
        links_before = _count("test_employee_central_links")

        connection = _connect()
        try:
            connection.execute(
                "UPDATE test_employees SET workplace_id = 999999 WHERE id = ?",
                (employee.id,),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(EmployeeLinkError):
            employee_central_link_service.create_and_link(employee.id)
        self.assertEqual(_count("thp_workers"), workers_before)
        self.assertEqual(_count("test_employee_central_links"), links_before)

        connection = _connect()
        try:
            connection.execute(
                "UPDATE test_employees SET workplace_id = ? WHERE id = ?",
                (self.workplace.id, employee.id),
            )
            connection.execute(
                """
                UPDATE test_employee_roles
                SET responsibility_role_id = 999999
                WHERE employee_id = ? AND responsibility_role_id = ?
                """,
                (employee.id, self.role_a.id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(EmployeeLinkError):
            employee_central_link_service.create_and_link(employee.id)
        self.assertEqual(_count("thp_workers"), workers_before)

        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_employee_roles
                SET responsibility_role_id = ?
                WHERE employee_id = ? AND responsibility_role_id = 999999
                """,
                (self.role_a.id, employee.id),
            )
            connection.commit()
        finally:
            connection.close()

        with patch.object(
            employee_central_link_service.repository,
            "_add_link",
            side_effect=RuntimeError("selhání uložení"),
        ):
            with self.assertRaises(RuntimeError):
                employee_central_link_service.create_and_link(employee.id)

        self.assertEqual(_count("thp_workers"), workers_before)
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertEqual(_select_all("test_exams"), before_exams)
        self.assertEqual(_select_all("test_exam_examiners"), before_examiners)
        self.assertEqual(_select_all("test_exam_validity_tracking"), before_tracking)
        self.assertEqual(
            [
                row
                for row in _select_all("test_employees")
                if row[0] == employee.id
            ],
            [row for row in before_employee if row[0] == employee.id],
        )

    def _links_touching(self, test_employee_id: int) -> int:
        connection = _connect()
        try:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM test_employee_central_links
                    WHERE test_employee_id = ?
                    """,
                    (test_employee_id,),
                ).fetchone()[0]
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
