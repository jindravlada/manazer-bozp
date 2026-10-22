"""EMPLOYEE-CENTRAL-4: bezpečné zrušení propojení zaměstnanců."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-4-"))

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
    from moduly.nastaveni.modely.test_employee_central_link import (
        TestEmployeeCentralLink,
    )
    from moduly.nastaveni.repository.employee_central_link_repository import (
        _UNLINK_KNOWN_COLUMNS,
    )
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        EmployeeLinkError,
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_validity_tracking import (
        TestExamValidityTracking,
    )
    from tests.historical_test_employee import (
        seed_historical_test_employee,
    )
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


class EmployeeCentral4TestCase(unittest.TestCase):
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
        return seed_historical_test_employee(**data)

    def test_known_schema_matches_models_without_transfer_columns(self) -> None:
        models = {
            TestEmployeeCentralLink.__tablename__: TestEmployeeCentralLink,
            TestExam.__tablename__: TestExam,
            TestExamExaminer.__tablename__: TestExamExaminer,
            TestExamValidityTracking.__tablename__: TestExamValidityTracking,
        }
        for table_name, model in models.items():
            live = frozenset(column.name for column in model.__table__.columns)
            self.assertEqual(_UNLINK_KNOWN_COLUMNS[table_name], live)
        self.assertIn("thp_worker_id", _UNLINK_KNOWN_COLUMNS["test_employee_central_links"])
        self.assertNotIn("thp_worker_id", _UNLINK_KNOWN_COLUMNS["test_exams"])
        self.assertNotIn("thp_worker_id", _UNLINK_KNOWN_COLUMNS["test_exam_examiners"])
        self.assertNotIn("thp_worker_id", _UNLINK_KNOWN_COLUMNS["test_exam_validity_tracking"])

    def test_unlink_removes_only_the_matching_link(self) -> None:
        employee = self._employee(personal_number=f"SRC-{self.marker}")
        other = self._employee(last_name=f"Jiná{self.marker}")
        _insert_history(employee.id, self.marker, self.workplace.name)
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
            responsibility_role_ids=[self.role_a.id],
        )
        other_worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Druhá{self.marker}",
            personal_number=f"OTHER-{self.marker}",
        )
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        kept = employee_central_link_service.link_existing(
            test_employee_id=other.id,
            thp_worker_id=other_worker.id,
        )
        before_worker = _worker_view(worker.id)
        before_other = _worker_view(other_worker.id)
        before_employees = _select_all("test_employees")
        before_employee_roles = _select_all("test_employee_roles")
        before_worker_roles = _select_all("thp_worker_roles")
        before_exams = _select_all("test_exams")
        before_examiners = _select_all("test_exam_examiners")
        before_tracking = _select_all("test_exam_validity_tracking")

        result = employee_central_link_service.unlink(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )

        self.assertTrue(result.removed)
        self.assertIn("zrušeno", result.message)
        self.assertIsNone(
            employee_central_link_service.get_by_test_employee(employee.id)
        )
        self.assertIsNone(employee_central_link_service.get_by_worker(worker.id))
        remaining = employee_central_link_service.get_by_test_employee(other.id)
        assert remaining is not None
        self.assertEqual(remaining.id, kept.id)
        self.assertEqual(remaining.thp_worker_id, other_worker.id)
        self.assertEqual(_worker_view(worker.id), before_worker)
        self.assertEqual(_worker_view(other_worker.id), before_other)
        self.assertEqual(_select_all("test_employees"), before_employees)
        self.assertEqual(_select_all("test_employee_roles"), before_employee_roles)
        self.assertEqual(_select_all("thp_worker_roles"), before_worker_roles)
        self.assertEqual(_select_all("test_exams"), before_exams)
        self.assertEqual(_select_all("test_exam_examiners"), before_examiners)
        self.assertEqual(_select_all("test_exam_validity_tracking"), before_tracking)
        stored = test_employee_service.get_employee(employee.id)
        assert stored is not None
        self.assertTrue(stored.active)

    def test_wrong_pair_and_missing_link_change_nothing(self) -> None:
        employee = self._employee()
        worker = settings_service.save_worker(
            first_name="Adam",
            last_name=f"A{self.marker}",
        )
        other_worker = settings_service.save_worker(
            first_name="Bára",
            last_name=f"B{self.marker}",
        )
        other_employee = self._employee(last_name=f"Cizí{self.marker}")
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        before_links = _select_all("test_employee_central_links")
        before_workers = _select_all("thp_workers")
        before_employees = _select_all("test_employees")

        with self.assertRaises(EmployeeLinkError) as wrong_worker:
            employee_central_link_service.unlink(
                test_employee_id=employee.id,
                thp_worker_id=other_worker.id,
            )
        self.assertIn("neodpovídá", str(wrong_worker.exception))
        with self.assertRaises(EmployeeLinkError) as wrong_employee:
            employee_central_link_service.unlink(
                test_employee_id=other_employee.id,
                thp_worker_id=worker.id,
            )
        self.assertIn("neodpovídá", str(wrong_employee.exception))

        missing = employee_central_link_service.unlink(
            test_employee_id=other_employee.id,
            thp_worker_id=other_worker.id,
        )
        self.assertFalse(missing.removed)
        self.assertIn("neexistuje", missing.message)
        self.assertEqual(_select_all("test_employee_central_links"), before_links)
        self.assertEqual(_select_all("thp_workers"), before_workers)
        self.assertEqual(_select_all("test_employees"), before_employees)
        kept = employee_central_link_service.get_by_test_employee(employee.id)
        assert kept is not None
        self.assertEqual(kept.thp_worker_id, worker.id)

    def test_failed_delete_rolls_back(self) -> None:
        employee = self._employee()
        worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"Transakce{self.marker}",
        )
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        before = _count("test_employee_central_links")
        repository = employee_central_link_service.repository
        original = repository._delete_link

        def fail(session, link, *, test_employee_id, thp_worker_id):
            original(
                session,
                link,
                test_employee_id=test_employee_id,
                thp_worker_id=thp_worker_id,
            )
            raise RuntimeError("selhání uložení")

        with patch.object(repository, "_delete_link", fail):
            with self.assertRaises(RuntimeError):
                employee_central_link_service.unlink(
                    test_employee_id=employee.id,
                    thp_worker_id=worker.id,
                )

        self.assertEqual(_count("test_employee_central_links"), before)
        kept = employee_central_link_service.get_by_test_employee(employee.id)
        assert kept is not None
        self.assertEqual(kept.thp_worker_id, worker.id)

    def test_unknown_transfer_column_refuses_unlink(self) -> None:
        employee = self._employee()
        worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Závislost{self.marker}",
        )
        link = employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        before_links = _select_all("test_employee_central_links")
        before_exams = _select_all("test_exams")
        before_workers = _select_all("thp_workers")
        before_employees = _select_all("test_employees")

        connection = _connect()
        try:
            connection.execute(
                "ALTER TABLE test_exams ADD COLUMN central_worker_id INTEGER"
            )
            connection.commit()
        finally:
            connection.close()
        try:
            with self.assertRaises(EmployeeLinkError) as refused:
                employee_central_link_service.unlink(
                    test_employee_id=employee.id,
                    thp_worker_id=worker.id,
                )
            self.assertIn("nelze spolehlivě ověřit", str(refused.exception))
            self.assertEqual(_select_all("test_employee_central_links"), before_links)
        finally:
            connection = _connect()
            try:
                connection.execute(
                    "ALTER TABLE test_exams DROP COLUMN central_worker_id"
                )
                connection.commit()
            finally:
                connection.close()

        connection = _connect()
        try:
            connection.execute(
                "ALTER TABLE test_employee_central_links "
                "ADD COLUMN history_transferred INTEGER NOT NULL DEFAULT 0"
            )
            connection.execute(
                """
                UPDATE test_employee_central_links
                SET history_transferred = 1
                WHERE id = ?
                """,
                (link.id,),
            )
            connection.commit()
        finally:
            connection.close()
        try:
            with self.assertRaises(EmployeeLinkError) as transferred:
                employee_central_link_service.unlink(
                    test_employee_id=employee.id,
                    thp_worker_id=worker.id,
                )
            self.assertIn("nelze spolehlivě ověřit", str(transferred.exception))
            kept = employee_central_link_service.get_by_test_employee(employee.id)
            assert kept is not None
            self.assertEqual(kept.thp_worker_id, worker.id)
            self.assertEqual(_select_all("thp_workers"), before_workers)
            self.assertEqual(_select_all("test_employees"), before_employees)
            self.assertEqual(_select_all("test_exams"), before_exams)
        finally:
            connection = _connect()
            try:
                connection.execute(
                    "ALTER TABLE test_employee_central_links "
                    "DROP COLUMN history_transferred"
                )
                connection.commit()
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
