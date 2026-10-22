"""EMPLOYEE-CENTRAL-11: potvrzené převzetí chybějících údajů při propojení."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-11-"))

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
        TAKEOVER_MAY_EXAMINE,
        TAKEOVER_PERSONAL_NUMBER,
        TAKEOVER_ROLES,
        TAKEOVER_WORKPLACE,
        EmployeeLinkError,
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import EXAMINER_MODE_NONE, VALIDITY_UNIT_YEARS, EMPLOYEE_SOURCE_TEST_EMPLOYEE
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from tests.historical_test_employee import (
        seed_historical_test_employee,
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


def _role_rows(worker_id: int) -> list[tuple[int, int]]:
    connection = _connect()
    try:
        return [
            (int(row["responsibility_role_id"]), int(row["sort_order"]))
            for row in connection.execute(
                """
                SELECT responsibility_role_id, sort_order
                FROM thp_worker_roles
                WHERE thp_worker_id = ?
                ORDER BY sort_order, id
                """,
                (worker_id,),
            )
        ]
    finally:
        connection.close()


class EmployeeCentral11TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.home = settings_service.save_workplace(
            name=f"Domácí provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.other = settings_service.save_workplace(
            name=f"Cizí provoz {self.marker}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.kept_role = responsibility_role_service.create_role(
            name=f"Mistr {self.marker}"
        )
        self.extra_role = responsibility_role_service.create_role(
            name=f"Zámečník {self.marker}"
        )
        self.employee = seed_historical_test_employee(
            personal_number=f"T-{self.marker}",
            first_name="Jana",
            last_name=f"Testová{self.marker}",
            title_before="Bc.",
            workplace_id=self.other.id,
            responsibility_role_ids=[self.kept_role.id, self.extra_role.id],
            may_examine=True,
            active=True,
        )
        self.worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Centrální{self.marker}",
            title_before="Ing.",
            title_after="Ph.D.",
            position=f"Svářeč {self.marker}",
            phone="123",
            email=f"eva-{self.marker}@example.test",
            personal_number="",
            workplace_id=None,
            responsibility_role_ids=[self.kept_role.id],
            active=True,
            is_thp=True,
            may_examine=False,
            performs_controls=True,
        )

    def _field(self, proposal, key: str):
        return next(item for item in proposal.fields if item.field == key)

    def _protected(self) -> tuple:
        worker = settings_service.get_worker_by_id(self.worker.id)
        assert worker is not None
        return (
            worker.title_before,
            worker.first_name,
            worker.last_name,
            worker.title_after,
            worker.position,
            worker.phone,
            worker.email,
            bool(worker.active),
            bool(worker.is_thp),
            bool(worker.performs_controls),
        )

    def test_proposal_reads_differences_without_writing(self) -> None:
        links_before = _count("test_employee_central_links")
        workers_before = _rows("thp_workers")
        employees_before = _rows("test_employees")
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        self.assertFalse(proposal.already_linked)
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertEqual(_rows("thp_workers"), workers_before)
        self.assertEqual(_rows("test_employees"), employees_before)

        number = self._field(proposal, TAKEOVER_PERSONAL_NUMBER)
        self.assertEqual(number.test_value, f"T-{self.marker}")
        self.assertEqual(number.central_value, "—")
        self.assertTrue(number.will_change)
        workplace = self._field(proposal, TAKEOVER_WORKPLACE)
        self.assertEqual(workplace.test_value, self.other.name)
        self.assertEqual(workplace.central_value, "—")
        self.assertTrue(workplace.will_change)
        roles = self._field(proposal, TAKEOVER_ROLES)
        self.assertIn(f"Mistr {self.marker}", roles.test_value)
        self.assertIn(f"Zámečník {self.marker}", roles.test_value)
        self.assertEqual(roles.central_value, f"Mistr {self.marker}")
        self.assertIn(f"Zámečník {self.marker}", roles.proposed_change)
        self.assertNotIn(f"Svářeč {self.marker}", roles.proposed_change)
        self.assertTrue(roles.will_change)
        examiner = self._field(proposal, TAKEOVER_MAY_EXAMINE)
        self.assertEqual(examiner.test_value, "Ano")
        self.assertEqual(examiner.central_value, "Ne")
        self.assertEqual(examiner.proposed_change, "Zapnout")

    def test_confirmed_fields_fill_gaps_and_keep_existing_data(self) -> None:
        topic = oral_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        oral_question_service.create_question(
            topic_id=topic.id,
            text=f"Otázka {self.marker}",
        )
        test = test_definition_service.create_test(
            name=f"Historie {self.marker}",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(topic_id=topic.id, question_count=1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=test.id,
            exam_date=date(2024, 6, 1),
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        exams_before = _rows("test_exams")
        answers_before = _rows("test_exam_oral_questions")
        protected = self._protected()
        kept_roles = _role_rows(self.worker.id)
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        result = employee_central_link_service.apply_confirmed_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
            revision=proposal.revision,
            confirm_fields=[
                TAKEOVER_PERSONAL_NUMBER,
                TAKEOVER_WORKPLACE,
                TAKEOVER_ROLES,
                TAKEOVER_MAY_EXAMINE,
            ],
        )
        self.assertTrue(result.linked_now)
        self.assertEqual(
            result.applied_fields,
            (
                TAKEOVER_PERSONAL_NUMBER,
                TAKEOVER_WORKPLACE,
                TAKEOVER_ROLES,
                TAKEOVER_MAY_EXAMINE,
            ),
        )
        worker = settings_service.get_worker_by_id(self.worker.id)
        assert worker is not None
        self.assertEqual(worker.personal_number, f"T-{self.marker}")
        self.assertEqual(worker.workplace_id, self.other.id)
        self.assertTrue(worker.may_examine)
        self.assertEqual(
            _role_rows(self.worker.id),
            kept_roles + [(self.extra_role.id, kept_roles[-1][1] + 1)],
        )
        self.assertEqual(self._protected(), protected)
        self.assertEqual(_rows("test_exams"), exams_before)
        self.assertEqual(_rows("test_exam_oral_questions"), answers_before)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.employee_id, self.employee.id)
        self.assertEqual(stored.employee_personal_number, f"T-{self.marker}")
        self.assertEqual(stored.employee_display_name, self.employee.display_name)

        again = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        self.assertTrue(again.already_linked)
        self.assertFalse(any(item.will_change for item in again.fields))
        links_after_first = _count("test_employee_central_links")
        repeated = employee_central_link_service.apply_confirmed_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
            revision=again.revision,
            confirm_fields=list(item.field for item in again.fields),
        )
        self.assertFalse(repeated.linked_now)
        self.assertEqual(repeated.link_id, result.link_id)
        self.assertEqual(repeated.applied_fields, ())
        self.assertEqual(len(_role_rows(self.worker.id)), 2)
        self.assertEqual(_count("test_employee_central_links"), links_after_first)

    def test_only_selected_fields_are_copied(self) -> None:
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        result = employee_central_link_service.apply_confirmed_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
            revision=proposal.revision,
            confirm_fields=[TAKEOVER_PERSONAL_NUMBER],
        )
        self.assertEqual(result.applied_fields, (TAKEOVER_PERSONAL_NUMBER,))
        worker = settings_service.get_worker_by_id(self.worker.id)
        assert worker is not None
        self.assertEqual(worker.personal_number, f"T-{self.marker}")
        self.assertIsNone(worker.workplace_id)
        self.assertFalse(worker.may_examine)
        self.assertEqual(_role_rows(self.worker.id), [(self.kept_role.id, 0)])

    def test_existing_values_stay_and_missing_role_is_added(self) -> None:
        filled = settings_service.save_worker(
            id=self.worker.id,
            personal_number=f"C-{self.marker}",
            workplace_id=self.home.id,
            may_examine=True,
            is_thp=True,
            performs_controls=True,
            position=f"Svářeč {self.marker}",
        )
        quiet = seed_historical_test_employee(
            personal_number=f"Q-{self.marker}",
            first_name="Adam",
            last_name=f"Jiný{self.marker}",
            workplace_id=self.other.id,
            responsibility_role_ids=[self.kept_role.id, self.extra_role.id],
            may_examine=False,
        )
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=quiet.id,
            thp_worker_id=filled.id,
        )
        self.assertFalse(self._field(proposal, TAKEOVER_PERSONAL_NUMBER).will_change)
        self.assertFalse(self._field(proposal, TAKEOVER_WORKPLACE).will_change)
        self.assertFalse(self._field(proposal, TAKEOVER_MAY_EXAMINE).will_change)
        self.assertTrue(self._field(proposal, TAKEOVER_ROLES).will_change)
        employee_central_link_service.apply_confirmed_takeover(
            test_employee_id=quiet.id,
            thp_worker_id=filled.id,
            revision=proposal.revision,
            confirm_fields=[
                TAKEOVER_PERSONAL_NUMBER,
                TAKEOVER_WORKPLACE,
                TAKEOVER_ROLES,
                TAKEOVER_MAY_EXAMINE,
            ],
        )
        worker = settings_service.get_worker_by_id(filled.id)
        assert worker is not None
        self.assertEqual(worker.personal_number, f"C-{self.marker}")
        self.assertEqual(worker.workplace_id, self.home.id)
        self.assertTrue(worker.may_examine)
        self.assertEqual(worker.position, f"Svářeč {self.marker}")
        self.assertTrue(worker.is_thp)
        self.assertTrue(worker.performs_controls)
        self.assertEqual(
            [role_id for role_id, _order in _role_rows(filled.id)],
            [self.kept_role.id, self.extra_role.id],
        )

    def test_changed_data_and_duplicate_number_are_refused(self) -> None:
        links_before = _count("test_employee_central_links")
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        settings_service.save_worker(
            id=self.worker.id,
            personal_number=f"Z-{self.marker}",
        )
        with self.assertRaises(EmployeeLinkError) as caught:
            employee_central_link_service.apply_confirmed_takeover(
                test_employee_id=self.employee.id,
                thp_worker_id=self.worker.id,
                revision=proposal.revision,
                confirm_fields=[TAKEOVER_PERSONAL_NUMBER, TAKEOVER_WORKPLACE],
            )
        self.assertIn("nový návrh", str(caught.exception))
        worker = settings_service.get_worker_by_id(self.worker.id)
        assert worker is not None
        self.assertEqual(worker.personal_number, f"Z-{self.marker}")
        self.assertIsNone(worker.workplace_id)
        self.assertEqual(_count("test_employee_central_links"), links_before)

        holder = settings_service.save_worker(
            first_name="Petr",
            last_name=f"Držitel{self.marker}",
            personal_number=f"D-{self.marker}",
            is_thp=False,
            may_examine=False,
            performs_controls=False,
        )
        blank = settings_service.save_worker(
            first_name="Lea",
            last_name=f"Prázdná{self.marker}",
            personal_number="",
            workplace_id=None,
            responsibility_role_ids=[self.kept_role.id],
            is_thp=False,
            may_examine=False,
            performs_controls=False,
        )
        duplicate_employee = seed_historical_test_employee(
            personal_number=f"D-{self.marker}",
            first_name="Lea",
            last_name=f"Stejná{self.marker}",
            workplace_id=self.other.id,
            responsibility_role_ids=[self.kept_role.id],
        )
        fresh = employee_central_link_service.propose_takeover(
            test_employee_id=duplicate_employee.id,
            thp_worker_id=blank.id,
        )
        with self.assertRaises(EmployeeLinkError) as duplicate:
            employee_central_link_service.apply_confirmed_takeover(
                test_employee_id=duplicate_employee.id,
                thp_worker_id=blank.id,
                revision=fresh.revision,
                confirm_fields=[TAKEOVER_PERSONAL_NUMBER],
            )
        self.assertIn("již existuje", str(duplicate.exception))
        self.assertIn("nový návrh", str(duplicate.exception))
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertEqual(
            settings_service.get_worker_by_id(holder.id).personal_number,
            f"D-{self.marker}",
        )
        self.assertIsNone(settings_service.get_worker_by_id(blank.id).personal_number)
        self.assertEqual(
            settings_service.get_worker_by_id(self.worker.id).personal_number,
            f"Z-{self.marker}",
        )

    def test_already_linked_worker_can_be_completed_without_a_second_link(self) -> None:
        links_before = _count("test_employee_central_links")
        link = employee_central_link_service.link_existing(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        untouched = settings_service.get_worker_by_id(self.worker.id)
        assert untouched is not None
        self.assertIsNone(untouched.personal_number)
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        self.assertTrue(proposal.already_linked)
        result = employee_central_link_service.apply_confirmed_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
            revision=proposal.revision,
            confirm_fields=[TAKEOVER_WORKPLACE, TAKEOVER_ROLES],
        )
        self.assertFalse(result.linked_now)
        self.assertEqual(result.link_id, link.id)
        self.assertEqual(_count("test_employee_central_links"), links_before + 1)
        worker = settings_service.get_worker_by_id(self.worker.id)
        assert worker is not None
        self.assertIsNone(worker.personal_number)
        self.assertEqual(worker.workplace_id, self.other.id)
        self.assertEqual(len(_role_rows(self.worker.id)), 2)

    def test_failed_takeover_rolls_back_the_link_and_the_worker(self) -> None:
        proposal = employee_central_link_service.propose_takeover(
            test_employee_id=self.employee.id,
            thp_worker_id=self.worker.id,
        )
        links_before = _count("test_employee_central_links")
        exams_before = _rows("test_exams")
        workers_before = _rows("thp_workers")
        roles_before = _rows("thp_worker_roles")
        with patch(
            "moduly.nastaveni.repository.employee_central_link_repository."
            "EmployeeCentralLinkRepository._after_takeover_writes",
            side_effect=RuntimeError("pád zápisu"),
        ):
            with self.assertRaises(RuntimeError):
                employee_central_link_service.apply_confirmed_takeover(
                    test_employee_id=self.employee.id,
                    thp_worker_id=self.worker.id,
                    revision=proposal.revision,
                    confirm_fields=[
                        TAKEOVER_PERSONAL_NUMBER,
                        TAKEOVER_WORKPLACE,
                        TAKEOVER_ROLES,
                        TAKEOVER_MAY_EXAMINE,
                    ],
                )
        self.assertEqual(_count("test_employee_central_links"), links_before)
        self.assertEqual(_rows("thp_workers"), workers_before)
        self.assertEqual(_rows("thp_worker_roles"), roles_before)
        self.assertEqual(_rows("test_exams"), exams_before)
