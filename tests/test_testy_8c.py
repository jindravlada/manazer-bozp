"""TESTY-8c: testovaný zaměstnanec není zkoušející téže zkoušky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-8c-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAM_STATUS_PREPARED,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.modely.oral_question import OralQuestion
    from moduly.testy.modely.oral_question_topic import OralQuestionTopic
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import (
        TestDefinitionWrittenTopic,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        EXAMINEE_CANNOT_EXAMINE,
        TestExamError,
        test_exam_service,
    )
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog


_APP = QApplication.instance() or QApplication([])
_DAY = date(2026, 10, 6)


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _employee(number: str, first: str, last: str, *, may_examine: bool = False):
    workplace = settings_service.save_workplace(name=f"Provoz {number}")
    role = responsibility_role_service.create_role(name=f"Role {number}")
    return test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
        may_examine=may_examine,
    )


def _label(employee) -> str:
    return f"{employee.personal_number} – {employee.display_name}"


def _ids(combo) -> set[int]:
    return set(combo._ids.values())


def _oral_test(name: str, topic_id: int, mode: str):
    return test_definition_service.create_test(
        name=name,
        uses_oral=True,
        examiner_mode=mode,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        oral_topics=[TestTopicQuota(topic_id, 1)],
    )


def _snapshot(exam_id: int):
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    people = tuple(
        (person.employee_id, person.role, person.display_name, person.position)
        for person in test_exam_service.get_examiners(exam_id)
    )
    return (
        exam.employee_id,
        exam.status,
        exam.examiner_mode,
        people,
    )


class ExamineeExcludedFromExaminersTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._dialogs: list[TestExamPrepareDialog] = []
        with get_session() as session:
            session.execute(delete(TestExamWrittenAnswer))
            session.execute(delete(TestExamWrittenQuestion))
            session.execute(delete(TestExamOralQuestion))
            session.execute(delete(TestExamExaminer))
            session.execute(delete(TestExam))
            session.execute(delete(TestDefinitionWrittenTopic))
            session.execute(delete(TestDefinitionOralTopic))
            session.execute(delete(TestDefinition))
            session.execute(delete(OralQuestion))
            session.execute(delete(OralQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()
        self.topic = oral_question_topic_service.create_topic(name="Ústní 8c")
        oral_question_service.create_question(topic_id=self.topic.id, text="Postup")
        self.examinee = _employee("83001", "Jan", "Testovaný", may_examine=True)
        self.alfa = _employee("83002", "Klára", "Zkoušející", may_examine=True)
        self.beta = _employee("83003", "Adam", "Komise", may_examine=True)
        self.gama = _employee("83004", "Iva", "Bezpráva", may_examine=False)
        self.delta = _employee("83005", "Petr", "Neaktivní", may_examine=True)
        test_employee_service.deactivate(self.delta.id)

    def tearDown(self) -> None:
        for dialog in self._dialogs:
            dialog.close()

    def _dialog(self) -> TestExamPrepareDialog:
        dialog = TestExamPrepareDialog()
        self._dialogs.append(dialog)
        return dialog

    def _reject(self, **kwargs) -> TestExamError:
        before = _count(TestExam)
        with self.assertRaises(TestExamError) as caught:
            test_exam_service.prepare_exam(rng=PrefixReverse(), **kwargs)
        self.assertEqual(_count(TestExam), before)
        return caught.exception

    def test_offer_hides_examinee_and_keeps_other_examiners(self) -> None:
        dialog = self._dialog()
        dialog.employee.setCurrentText(_label(self.examinee))
        self.assertEqual(dialog.employee.person_id(), self.examinee.id)
        for combo in (dialog.examiner, dialog.chair, dialog.member):
            offered = _ids(combo)
            self.assertNotIn(self.examinee.id, offered)
            self.assertIn(self.alfa.id, offered)
            self.assertIn(self.beta.id, offered)
            self.assertNotIn(self.gama.id, offered)
            self.assertNotIn(self.delta.id, offered)

    def test_changing_examinee_removes_conflict_from_selection(self) -> None:
        dialog = self._dialog()
        dialog.employee.setCurrentText(_label(self.examinee))
        dialog.examiner.setCurrentText(_label(self.alfa))
        dialog.chair.setCurrentText(_label(self.beta))
        dialog.member.setCurrentText(_label(self.alfa))
        dialog._add_member()
        self.assertEqual(dialog._member_ids(), [self.alfa.id])

        with patch(
            "moduly.testy.ui.test_exam_prepare_dialog.QMessageBox.warning"
        ) as warning:
            dialog.employee.setCurrentText(_label(self.alfa))
        warning.assert_called()
        self.assertEqual(warning.call_args.args[1], "Testy")
        self.assertEqual(warning.call_args.args[2], EXAMINEE_CANNOT_EXAMINE)
        self.assertEqual(dialog.employee.person_id(), self.alfa.id)
        self.assertIsNone(dialog.examiner.person_id())
        self.assertEqual(dialog.chair.person_id(), self.beta.id)
        self.assertNotIn(self.alfa.id, dialog._member_ids())
        self.assertNotIn(self.alfa.id, _ids(dialog.examiner))
        self.assertNotIn(self.alfa.id, _ids(dialog.chair))
        self.assertNotIn(self.alfa.id, _ids(dialog.member))
        self.assertIn(self.beta.id, _ids(dialog.examiner))
        self.assertIn(self.examinee.id, _ids(dialog.examiner))
        self.assertIsNone(dialog.get_data()["examiner_id"])

        with patch(
            "moduly.testy.ui.test_exam_prepare_dialog.QMessageBox.warning"
        ) as chair_warning:
            dialog.employee.setCurrentText(_label(self.beta))
        chair_warning.assert_called()
        self.assertEqual(chair_warning.call_args.args[2], EXAMINEE_CANNOT_EXAMINE)
        self.assertIsNone(dialog.chair.person_id())
        self.assertNotIn(self.beta.id, _ids(dialog.chair))
        self.assertIn(self.alfa.id, _ids(dialog.chair))

    def test_service_rejects_examinee_in_every_examiner_role(self) -> None:
        single = _oral_test("Jeden", self.topic.id, EXAMINER_MODE_SINGLE)
        commission = _oral_test("Komise", self.topic.id, EXAMINER_MODE_COMMISSION)
        plain = _oral_test("Bez", self.topic.id, EXAMINER_MODE_NONE)
        blocked = _employee("83006", "Eva", "Nemůže", may_examine=False)

        examiner_error = self._reject(
            employee_id=self.examinee.id,
            test_id=single.id,
            exam_date=_DAY,
            examiner_id=self.examinee.id,
        )
        self.assertEqual(str(examiner_error), EXAMINEE_CANNOT_EXAMINE)

        blocked_error = self._reject(
            employee_id=blocked.id,
            test_id=single.id,
            exam_date=_DAY,
            examiner_id=blocked.id,
        )
        self.assertEqual(str(blocked_error), EXAMINEE_CANNOT_EXAMINE)

        chair_error = self._reject(
            employee_id=self.examinee.id,
            test_id=commission.id,
            exam_date=_DAY,
            chair_id=self.examinee.id,
            member_ids=[self.alfa.id],
        )
        self.assertEqual(str(chair_error), EXAMINEE_CANNOT_EXAMINE)

        member_error = self._reject(
            employee_id=self.examinee.id,
            test_id=commission.id,
            exam_date=_DAY,
            chair_id=self.alfa.id,
            member_ids=[self.beta.id, self.examinee.id],
        )
        self.assertEqual(str(member_error), EXAMINEE_CANNOT_EXAMINE)

        none_error = self._reject(
            employee_id=self.examinee.id,
            test_id=plain.id,
            exam_date=_DAY,
            examiner_id=self.alfa.id,
        )
        self.assertIn("nevyžaduje", str(none_error))

        exam = test_exam_service.prepare_exam(
            employee_id=self.examinee.id,
            test_id=plain.id,
            exam_date=_DAY,
            rng=PrefixReverse(),
        )
        self.assertEqual(exam.status, EXAM_STATUS_PREPARED)
        self.assertEqual(test_exam_service.get_examiners(exam.id), [])

        kept = test_exam_service.prepare_exam(
            employee_id=self.examinee.id,
            test_id=single.id,
            exam_date=_DAY,
            examiner_id=self.alfa.id,
            rng=PrefixReverse(),
        )
        self.assertEqual(
            [(person.role, person.employee_id) for person in test_exam_service.get_examiners(kept.id)],
            [(EXAM_ROLE_EXAMINER, self.alfa.id)],
        )
        board = test_exam_service.prepare_exam(
            employee_id=self.examinee.id,
            test_id=commission.id,
            exam_date=_DAY,
            chair_id=self.alfa.id,
            member_ids=[self.beta.id],
            rng=PrefixReverse(),
        )
        self.assertEqual(
            [(person.role, person.employee_id) for person in test_exam_service.get_examiners(board.id)],
            [
                (EXAM_ROLE_CHAIR, self.alfa.id),
                (EXAM_ROLE_MEMBER, self.beta.id),
            ],
        )

    def test_existing_exam_snapshot_stays_unchanged(self) -> None:
        single = _oral_test("Historie", self.topic.id, EXAMINER_MODE_SINGLE)
        exam = test_exam_service.prepare_exam(
            employee_id=self.examinee.id,
            test_id=single.id,
            exam_date=_DAY,
            examiner_id=self.alfa.id,
            rng=PrefixReverse(),
        )
        before = _snapshot(exam.id)
        self._reject(
            employee_id=self.alfa.id,
            test_id=single.id,
            exam_date=_DAY,
            examiner_id=self.alfa.id,
        )
        self.assertEqual(_snapshot(exam.id), before)
        self.assertEqual(before[3][0][2], self.alfa.display_name)
        self.assertEqual(_count(TestExam), 1)
