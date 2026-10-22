"""EMPLOYEE-CENTRAL-9: příprava zkoušky pro centrálního zaměstnance."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-9-"))

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
    from moduly.testy.constants import (
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service


def _db_path() -> Path:
    return Path(storage_module.storage_service.database_path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _exam_count() -> int:
    connection = _connect()
    try:
        return int(connection.execute("SELECT COUNT(*) FROM test_exams").fetchone()[0])
    finally:
        connection.close()


def _exam_row(exam_id: int) -> sqlite3.Row:
    connection = _connect()
    try:
        return connection.execute(
            "SELECT * FROM test_exams WHERE id = ?",
            (exam_id,),
        ).fetchone()
    finally:
        connection.close()


class EmployeeCentral9TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"Provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.role_a = responsibility_role_service.create_role(name=f"Mistr {self.marker}")
        self.role_b = responsibility_role_service.create_role(name=f"Zámečník {self.marker}")
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(topic_id=topic.id, text=f"Otázka {self.marker}")
        self.single_test = test_definition_service.create_test(
            name=f"Jeden {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        self.commission_test = test_definition_service.create_test(
            name=f"Komise {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_COMMISSION,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )

    def _employee(self, number: str, first: str, last: str, *, may_examine: bool = False):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            title_before="Bc.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role_a.id],
            may_examine=may_examine,
            active=True,
        )

    def _worker(self, number: str, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "personal_number": number,
            "title_before": "Ing.",
            "title_after": "Ph.D.",
            "position": f"Svářeč {self.marker}",
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role_a.id, self.role_b.id],
            "active": True,
            "is_thp": False,
            "may_examine": False,
            "performs_controls": False,
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _prepare_worker(self, worker, examiner, **extra):
        payload = {
            "employee_id": worker.id,
            "employee_source": EMPLOYEE_SOURCE_THP_WORKER,
            "examiner_source": EMPLOYEE_SOURCE_THP_WORKER,
            "test_id": self.single_test.id,
            "exam_date": date(2026, 3, 1),
            "examiner_id": examiner.id,
        }
        payload.update(extra)
        return test_exam_service.prepare_exam(**payload)

    def test_central_exam_snapshot_examiner_and_historical_exam(self) -> None:
        historical_employee = self._employee(
            f"H-{self.marker}",
            "Jana",
            f"Historie{self.marker}",
        )
        historical_examiner = self._employee(
            f"EH-{self.marker}",
            "Petr",
            f"Historický{self.marker}",
            may_examine=True,
        )
        historical = test_exam_service.prepare_exam(
            employee_id=historical_employee.id,
            test_id=self.single_test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=historical_examiner.id,
        )
        before = tuple(_exam_row(historical.id))
        self.assertEqual(historical.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)

        worker = self._worker(f"C-{self.marker}", "Eva", f"Centrum{self.marker}")
        examiner = self._worker(
            f"CE-{self.marker}",
            "Adam",
            f"Zkouší{self.marker}",
            may_examine=True,
            responsibility_role_ids=[self.role_a.id],
        )
        chair = self._worker(
            f"CH-{self.marker}",
            "Iva",
            f"Předsedá{self.marker}",
            may_examine=True,
            responsibility_role_ids=[self.role_a.id],
        )
        member = self._worker(
            f"CM-{self.marker}",
            "Ota",
            f"Člen{self.marker}",
            may_examine=True,
            responsibility_role_ids=[self.role_a.id],
        )
        exam = self._prepare_worker(worker, examiner)
        self.assertEqual(exam.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(exam.employee_id, worker.id)
        self.assertEqual(exam.employee_personal_number, f"C-{self.marker}")
        self.assertEqual(exam.employee_first_name, "Eva")
        self.assertEqual(exam.employee_last_name, f"Centrum{self.marker}")
        self.assertEqual(exam.employee_title_before, "Ing.")
        self.assertEqual(exam.employee_title_after, "Ph.D.")
        self.assertEqual(exam.employee_display_name, worker.display_name)
        self.assertEqual(exam.employee_workplace_name, self.workplace.name)
        self.assertEqual(
            exam.employee_roles_text,
            f"Mistr {self.marker}, Zámečník {self.marker}",
        )
        self.assertNotIn(f"Svářeč {self.marker}", exam.employee_roles_text)
        people = test_exam_service.get_examiners(exam.id)
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(people[0].employee_id, examiner.id)
        self.assertEqual(people[0].display_name, examiner.display_name)
        self.assertEqual(people[0].role, EXAM_ROLE_EXAMINER)
        self.assertEqual(people[0].position, 1)

        commission = test_exam_service.prepare_exam(
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=self.commission_test.id,
            exam_date=date(2026, 4, 1),
            chair_id=chair.id,
            member_ids=[member.id],
        )
        commission_people = test_exam_service.get_examiners(commission.id)
        self.assertEqual(
            [(person.role, person.position, person.employee_id, person.employee_source) for person in commission_people],
            [
                (EXAM_ROLE_CHAIR, 1, chair.id, EMPLOYEE_SOURCE_THP_WORKER),
                (EXAM_ROLE_MEMBER, 2, member.id, EMPLOYEE_SOURCE_THP_WORKER),
            ],
        )
        self.assertEqual(commission_people[0].display_name, chair.display_name)
        self.assertEqual(tuple(_exam_row(historical.id)), before)
        self.assertEqual(
            test_exam_service.get_examiners(historical.id)[0].employee_source,
            EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )

    def test_incomplete_worker_and_self_exam_are_refused(self) -> None:
        examiner = self._worker(
            f"CE-{self.marker}",
            "Adam",
            f"Zkouší{self.marker}",
            may_examine=True,
            responsibility_role_ids=[self.role_a.id],
        )
        cases = [
            ({"active": False}, "aktivního zaměstnance"),
            ({"personal_number": ""}, "osobní číslo"),
            ({"workplace_id": None}, "přiřazený provoz"),
            ({"responsibility_role_ids": []}, "funkci / roli"),
        ]
        for extra, reason in cases:
            worker = self._worker(f"X-{uuid.uuid4().hex[:6]}", "Eva", f"Neúplná{self.marker}", **extra)
            before = _exam_count()
            with self.assertRaises(TestExamError) as caught:
                self._prepare_worker(worker, examiner)
            self.assertIn(reason, str(caught.exception))
            self.assertEqual(_exam_count(), before)

        worker = self._worker(f"P-{self.marker}", "Eva", f"Provoz{self.marker}")
        connection = _connect()
        try:
            connection.execute(
                "UPDATE thp_workers SET workplace_id = 999999 WHERE id = ?",
                (worker.id,),
            )
            connection.commit()
        finally:
            connection.close()
        before = _exam_count()
        with self.assertRaises(TestExamError) as missing_workplace:
            self._prepare_worker(worker, examiner)
        self.assertIn("provoz neexistuje", str(missing_workplace.exception))
        self.assertEqual(_exam_count(), before)

        worker = self._worker(f"R-{self.marker}", "Eva", f"Role{self.marker}")
        connection = _connect()
        try:
            role_rows = connection.execute(
                "SELECT id FROM thp_worker_roles WHERE thp_worker_id = ? ORDER BY id",
                (worker.id,),
            ).fetchall()
            keep = role_rows[0][0]
            connection.execute(
                "DELETE FROM thp_worker_roles WHERE thp_worker_id = ? AND id != ?",
                (worker.id, keep),
            )
            connection.execute(
                """
                UPDATE thp_worker_roles
                SET responsibility_role_id = 999999
                WHERE id = ?
                """,
                (keep,),
            )
            connection.commit()
        finally:
            connection.close()
        before = _exam_count()
        with self.assertRaises(TestExamError) as missing_role:
            self._prepare_worker(worker, examiner)
        self.assertIn("role neexistuje", str(missing_role.exception))
        self.assertEqual(_exam_count(), before)

        complete = self._worker(f"S-{self.marker}", "Eva", f"Sama{self.marker}", may_examine=True)
        before = _exam_count()
        with self.assertRaises(TestExamError) as itself:
            self._prepare_worker(complete, complete)
        self.assertIn("nemůže být současně zkoušejícím", str(itself.exception))
        self.assertEqual(_exam_count(), before)

        linked_employee = self._employee(
            f"L-{self.marker}",
            "Jana",
            f"Stejná{self.marker}",
            may_examine=True,
        )
        employee_central_link_service.link_existing(
            test_employee_id=linked_employee.id,
            thp_worker_id=complete.id,
        )
        before = _exam_count()
        with self.assertRaises(TestExamError) as linked_self:
            test_exam_service.prepare_exam(
                employee_id=complete.id,
                employee_source=EMPLOYEE_SOURCE_THP_WORKER,
                examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
                test_id=self.single_test.id,
                exam_date=date(2026, 3, 2),
                examiner_id=linked_employee.id,
            )
        self.assertIn("nemůže být současně zkoušejícím", str(linked_self.exception))
        self.assertEqual(_exam_count(), before)

    def test_failed_prepare_rolls_back_and_linked_validity_stays_one_row(self) -> None:
        employee = self._employee(f"H-{self.marker}", "Jana", f"Historie{self.marker}")
        historical_examiner = self._employee(
            f"EH-{self.marker}",
            "Petr",
            f"Historický{self.marker}",
            may_examine=True,
        )
        historical = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=self.single_test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=historical_examiner.id,
        )
        before_historical = tuple(_exam_row(historical.id))
        worker = self._worker(f"C-{self.marker}", "Eva", f"Centrum{self.marker}")
        examiner = self._worker(
            f"CE-{self.marker}",
            "Adam",
            f"Zkouší{self.marker}",
            may_examine=True,
            responsibility_role_ids=[self.role_a.id],
        )
        employee_central_link_service.link_existing(
            test_employee_id=employee.id,
            thp_worker_id=worker.id,
        )
        exam_validity_service.stop_tracking(employee.id, self.single_test.id)
        before = _exam_count()

        def fail_resume(*_args, **_kwargs):
            raise RuntimeError("přerušení zápisu")

        with patch(
            "moduly.testy.repository.test_exam_validity_tracking_repository.resume_validity_tracking",
            fail_resume,
        ):
            with self.assertRaises(TestExamError):
                self._prepare_worker(worker, examiner)
        self.assertEqual(_exam_count(), before)
        self.assertEqual(tuple(_exam_row(historical.id)), before_historical)

        prepared = self._prepare_worker(worker, examiner)
        self.assertEqual(prepared.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        connection = _connect()
        try:
            markers = connection.execute(
                """
                SELECT COUNT(*) FROM test_exam_validity_tracking
                WHERE test_definition_id = ?
                """,
                (self.single_test.id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(int(markers), 0)
        rows = [
            row
            for row in exam_validity_service.list_rows(
                today=date(2026, 3, 15),
                include_inactive_employees=True,
            )
            if row.test_definition_id == self.single_test.id
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(rows[0].employee_id, worker.id)
        self.assertEqual(rows[0].employee_name, worker.display_name)
        self.assertGreaterEqual(rows[0].prepared_count, 2)
        self.assertEqual(tuple(_exam_row(historical.id)), before_historical)

        from moduly.testy.constants import (
            EXAM_STATUS_COMPLETED,
            WRITTEN_MODE_ELECTRONIC,
            WRITTEN_RESULT_PASSED,
        )

        connection = _connect()
        try:
            connection.execute(
                """
                UPDATE test_exams
                SET status = ?, exam_result = ?, written_result = ?, written_mode = ?
                WHERE id = ?
                """,
                (
                    EXAM_STATUS_COMPLETED,
                    WRITTEN_RESULT_PASSED,
                    WRITTEN_RESULT_PASSED,
                    WRITTEN_MODE_ELECTRONIC,
                    historical.id,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        exported = exam_protocol_export_service.export(
            historical.id,
            _TMP / f"protokol-{self.marker}.odt",
        )
        with zipfile.ZipFile(exported) as package:
            content = package.read("content.xml").decode("utf-8")
        self.assertIn(employee.display_name, content)
        self.assertNotIn(worker.display_name, content)

    def test_existing_employee_foreign_key_is_removed_without_changing_rows(self) -> None:
        employee = self._employee(f"H-{self.marker}", "Jana", f"Historie{self.marker}")
        examiner = self._employee(
            f"EH-{self.marker}",
            "Petr",
            f"Historický{self.marker}",
            may_examine=True,
        )
        historical = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=self.single_test.id,
            exam_date=date(2024, 6, 1),
            examiner_id=examiner.id,
        )
        before_exam = tuple(_exam_row(historical.id))
        connection = _connect()
        try:
            before_people = [
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM test_exam_examiners WHERE exam_id = ? ORDER BY id",
                    (historical.id,),
                )
            ]
        finally:
            connection.close()
        for table in ("test_exams", "test_exam_examiners"):
            _install_test_employee_fk(table)
        initialize_database()
        self.assertEqual(tuple(_exam_row(historical.id)), before_exam)
        connection = _connect()
        try:
            people = [
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM test_exam_examiners WHERE exam_id = ? ORDER BY id",
                    (historical.id,),
                )
            ]
            self.assertEqual(people, before_people)
            for table in ("test_exams", "test_exam_examiners"):
                targets = [
                    (row[3], row[2])
                    for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')
                ]
                self.assertNotIn(("employee_id", "test_employees"), targets)
            exam_indexes = {
                row[1]
                for row in connection.execute('PRAGMA index_list("test_exams")')
            }
            self.assertIn("ix_test_exams_employee_id", exam_indexes)
            self.assertIn("ix_test_exams_test_definition_id", exam_indexes)
        finally:
            connection.close()
        initialize_database()
        self.assertEqual(tuple(_exam_row(historical.id)), before_exam)


def _install_test_employee_fk(table: str) -> None:
    connection = _connect()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        create_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()[0]
        indexes = [
            row[0]
            for row in connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL
                """,
                (table,),
            )
        ]
        body = create_sql.rstrip().rstrip(";")
        body = body[:-1] + ", FOREIGN KEY(employee_id) REFERENCES test_employees (id))"
        kept = f"{table}__oldfk"
        connection.execute(f'ALTER TABLE "{table}" RENAME TO "{kept}"')
        connection.execute(body)
        connection.execute(f'INSERT INTO "{table}" SELECT * FROM "{kept}"')
        connection.execute(f'DROP TABLE "{kept}"')
        for index_sql in indexes:
            connection.execute(index_sql)
        connection.commit()
    finally:
        connection.close()
