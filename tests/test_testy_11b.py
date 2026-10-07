"""TESTY-11b: kompaktní ústní otázky, instrukce testu a pohlaví zaměstnance."""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy import delete, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-11b-"))
_EXAM_DAY = date(2026, 10, 7)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _ensure_test_employee_columns,
        _ensure_test_exam_tables,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_TEXT,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_MEMBER,
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        GENDER_FEMALE,
        GENDER_FEMALE_LABEL,
        GENDER_MALE,
        GENDER_MALE_LABEL,
        PAPER_TEST_INSTRUCTION,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
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
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.exam_protocol_layout import (
        examinee_role_label,
        protocol_people,
    )
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import (
        TestEmployeeError,
        test_employee_service,
    )
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _employee(number: str, first: str, last: str, **kwargs):
    workplace = settings_service.save_workplace(name=kwargs.get("workplace", f"Provoz {number}"))
    role = responsibility_role_service.create_role(name=kwargs.get("role_name", f"Mistr {number}"))
    return test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
        title_before=kwargs.get("title_before", ""),
        title_after=kwargs.get("title_after", ""),
        may_examine=kwargs.get("may_examine", False),
        gender=kwargs.get("gender"),
    )


def _written_topic(name: str) -> int:
    topic = written_question_topic_service.create_topic(name=name)
    for index in range(2):
        written_question_service.create_question(
            topic_id=topic.id,
            text=f"Písemná otázka {name} {index}",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=True),
                WrittenAnswerInput(text="druhá"),
                WrittenAnswerInput(text="třetí"),
            ],
        )
    return topic.id


def _oral_topics(name: str) -> list[TestTopicQuota]:
    topic = oral_question_topic_service.create_topic(name=name)
    oral_question_service.create_question(
        topic_id=topic.id,
        text="Jaké OOPP má mít zaměstnanec",
    )
    oral_question_service.create_question(topic_id=topic.id, text="Otevřená zlomenina")
    return [TestTopicQuota(topic.id, 2)]


def _prepare(employee_id: int, **kwargs):
    definition = test_definition_service.create_test(
        name=kwargs.get("name", "Zkouška pohlaví"),
        uses_written=True,
        uses_oral=bool(kwargs.get("oral_topics")),
        allowed_wrong_answers=0,
        seconds_per_question=30,
        examiner_mode=kwargs.get("examiner_mode", EXAMINER_MODE_NONE),
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(kwargs["topic_id"], 1)],
        oral_topics=kwargs.get("oral_topics"),
    )
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=definition.id,
        exam_date=_EXAM_DAY,
        examiner_id=kwargs.get("examiner_id"),
        rng=PrefixReverse(),
    )


def _plain(path: Path) -> str:
    text = _xml(path).replace("<text:line-break/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _mark(exam_id: int, **fields) -> None:
    with get_session() as session:
        row = session.get(TestExam, int(exam_id))
        assert row is not None
        for key, value in fields.items():
            setattr(row, key, value)
        session.commit()


def _finish_electronic(exam_id: int) -> None:
    _mark(
        exam_id,
        status=EXAM_STATUS_COMPLETED,
        written_mode=WRITTEN_MODE_ELECTRONIC,
        written_result=WRITTEN_RESULT_PASSED,
        exam_result=WRITTEN_RESULT_PASSED,
        written_question_count=1,
        written_correct_count=1,
        written_incorrect_count=0,
        written_unanswered_count=0,
        written_allowed_wrong_answers=0,
    )


def _select_gender(dialog: TestEmployeeDialog, gender: str) -> None:
    for index in range(dialog.gender.count()):
        if dialog.gender.itemData(index) == gender:
            dialog.gender.setCurrentIndex(index)
            return
    raise AssertionError(gender)


class GenderAndProtocolTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(TestExamWrittenChoice))
            session.execute(delete(TestExamWrittenAnswer))
            session.execute(delete(TestExamWrittenQuestion))
            session.execute(delete(TestExamOralQuestion))
            session.execute(delete(TestExamExaminer))
            session.execute(delete(TestExam))
            session.execute(delete(TestDefinitionWrittenTopic))
            session.execute(delete(TestDefinitionOralTopic))
            session.execute(delete(TestDefinition))
            session.execute(delete(WrittenQuestionAnswer))
            session.execute(delete(WrittenQuestion))
            session.execute(delete(OralQuestion))
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(OralQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()
        self.folder = _TMP / self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def test_instruction_and_compact_oral_questions(self) -> None:
        self.assertEqual(
            PAPER_TEST_INSTRUCTION,
            "U každé otázky zakroužkujte jednu správnou odpověď A, B nebo C.",
        )
        employee = _employee("11b-1", "Jan", "Novak")
        topic_id = _written_topic("Papír 11b")
        exam = _prepare(
            employee.id,
            name="Kompaktní ústní",
            topic_id=topic_id,
            oral_topics=_oral_topics("Ústní 11b"),
        )
        individual = self.folder / "individual.odt"
        paper_test_export_service.export(exam.id, individual)
        batch_folder = self.folder / "batch"
        batch_folder.mkdir()
        paper_test_export_service.export_batch([exam.id], batch_folder)
        batch_files = list(batch_folder.glob("*.odt"))
        self.assertEqual(len(batch_files), 1)

        for path in (individual, batch_files[0]):
            plain = _plain(path)
            xml = _xml(path)
            self.assertIn("zakroužkujte", plain)
            self.assertNotIn("označte", plain)
            rows = test_exam_service.get_oral_questions(exam.id)
            first = f"{rows[0].position}. {rows[0].text}"
            second = f"{rows[1].position}. {rows[1].text}"
            self.assertLess(plain.index(first), plain.index(second))
            between = xml[xml.index(first) : xml.index(second)]
            self.assertNotIn("ProtocolNote", between)
            self.assertNotIn("<table:table", between)
            self.assertEqual(xml.count('text:style-name="ProtocolOralText"'), 2)
            self.assertNotIn('text:style-name="ProtocolNote"', xml)
            self.assertNotIn('table:style-name="ProtocolOral"', xml)
            style = xml[xml.find('style:name="ProtocolOralText"') :][:420]
            self.assertIn('fo:margin-top="0.04cm"', style)
            self.assertIn('fo:margin-bottom="0.04cm"', style)
            self.assertIn('fo:keep-together="always"', style)

    def test_employee_gender_storage_and_legacy_null(self) -> None:
        male = _employee("11b-m", "Jan", "Novak", gender=GENDER_MALE)
        female = _employee("11b-f", "Eva", "Mala", gender=GENDER_FEMALE)
        legacy = _employee("11b-n", "Eva", "Neurcena")
        self.assertEqual(test_employee_service.get_employee(male.id).gender, GENDER_MALE)
        self.assertEqual(test_employee_service.get_employee(female.id).gender, GENDER_FEMALE)
        loaded = test_employee_service.get_employee(legacy.id)
        assert loaded is not None
        self.assertIsNone(loaded.gender)
        self.assertEqual(loaded.first_name, "Eva")
        with self.assertRaises(TestEmployeeError):
            _employee("11b-x", "Jan", "Spatny", gender="jine")

        kept = test_employee_service.update_employee(
            legacy.id,
            personal_number=loaded.personal_number,
            first_name=loaded.first_name,
            last_name=loaded.last_name,
        )
        self.assertIsNone(kept.gender)

    def test_editor_requires_choice_and_does_not_preselect_null(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz editor")
        role = responsibility_role_service.create_role(name="Role editor")
        dialog = TestEmployeeDialog()
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.gender.objectName(), "employee-gender")
        self.assertEqual(dialog.gender.itemText(1), GENDER_MALE_LABEL)
        self.assertEqual(dialog.gender.itemText(2), GENDER_FEMALE_LABEL)
        self.assertIsNone(dialog.gender.currentData())

        dialog.personal_number.setText("11b-new")
        dialog.first_name.setText("Eva")
        dialog.last_name.setText("Nova")
        dialog.workplace.set_workplace_id(workplace.id)
        dialog.roles.set_role_ids([role.id])
        with patch.object(QMessageBox, "warning") as warning:
            dialog.accept()
        self.assertIn("Vyberte pohlaví.", warning.call_args[0][2])
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNone(test_employee_service.get_by_personal_number("11b-new"))

        _select_gender(dialog, GENDER_FEMALE)
        dialog.accept()
        created = test_employee_service.get_employee(dialog.saved_employee_id)
        assert created is not None
        self.assertEqual(created.gender, GENDER_FEMALE)

        legacy = _employee(
            "11b-old",
            "Jan",
            "Stary",
            workplace="Provoz stary",
            role_name="Role stary",
            title_before="Ing.",
            may_examine=True,
        )
        edit = TestEmployeeDialog(
            employee=test_employee_service.get_employee(legacy.id),
            role_ids=test_employee_service.get_role_ids(legacy.id),
        )
        self.addCleanup(edit.close)
        self.assertIsNone(edit.gender.currentData())
        self.assertEqual(edit.title_before.text(), "Ing.")
        self.assertTrue(edit.may_examine.isChecked())
        with patch.object(QMessageBox, "warning") as warning:
            edit.accept()
        self.assertIn("Vyberte pohlaví.", warning.call_args[0][2])
        self.assertIsNone(test_employee_service.get_employee(legacy.id).gender)

        _select_gender(edit, GENDER_MALE)
        edit.accept()
        saved = test_employee_service.get_employee(legacy.id)
        assert saved is not None
        self.assertEqual(saved.gender, GENDER_MALE)
        self.assertEqual(saved.title_before, "Ing.")
        self.assertTrue(saved.may_examine)
        self.assertEqual(saved.first_name, "Jan")

        again = TestEmployeeDialog(employee=saved, role_ids=[])
        self.addCleanup(again.close)
        self.assertEqual(again.gender.currentData(), GENDER_MALE)

    def test_snapshot_and_signature_label_on_both_protocols(self) -> None:
        self.assertEqual(examinee_role_label(GENDER_MALE), "Zkoušený")
        self.assertEqual(examinee_role_label(GENDER_FEMALE), "Zkoušená")
        self.assertEqual(examinee_role_label(None), "Zkoušený")
        self.assertEqual(examinee_role_label(""), "Zkoušený")
        commission = protocol_people(
            SimpleNamespace(
                employee_gender=GENDER_FEMALE,
                employee_display_name="Eva Malá",
                examiner_mode=EXAMINER_MODE_COMMISSION,
            ),
            [
                SimpleNamespace(id=1, position=1, role=EXAM_ROLE_CHAIR, display_name="Adam"),
                SimpleNamespace(id=2, position=2, role=EXAM_ROLE_MEMBER, display_name="Iva"),
            ],
        )
        self.assertEqual(
            [role for role, _name in commission],
            ["Zkoušená", "Předseda komise", "Člen komise"],
        )

        topic_id = _written_topic("Snapshot 11b")
        oral = _oral_topics("Ústní snapshot")
        examiner = _employee("11b-ex", "Adam", "Zkus", may_examine=True, gender=GENDER_MALE)
        male = _employee("11b-man", "Jan", "Novak", title_before="Ing.", gender=GENDER_MALE)
        female = _employee("11b-woman", "Eva", "Mala", title_before="Mgr.", gender=GENDER_FEMALE)
        unnamed = _employee("11b-legacy", "Eva", "Bezudaje")

        male_exam = _prepare(
            male.id,
            name="Muž",
            topic_id=topic_id,
            oral_topics=oral,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        female_exam = _prepare(
            female.id,
            name="Žena",
            topic_id=topic_id,
            oral_topics=oral,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        legacy_exam = _prepare(
            unnamed.id,
            name="Bez pohlaví",
            topic_id=topic_id,
            oral_topics=oral,
        )
        self.assertEqual(test_exam_service.get_exam(male_exam.id).employee_gender, GENDER_MALE)
        self.assertEqual(
            test_exam_service.get_exam(female_exam.id).employee_gender,
            GENDER_FEMALE,
        )
        self.assertIsNone(test_exam_service.get_exam(legacy_exam.id).employee_gender)

        test_employee_service.update_employee_details(
            female.id,
            personal_number="11b-woman",
            first_name="Eva",
            last_name="Mala",
            title_before="Mgr.",
            workplace_id=female.workplace_id,
            responsibility_role_ids=test_employee_service.get_role_ids(female.id),
            active=True,
            gender=GENDER_MALE,
        )
        self.assertEqual(
            test_exam_service.get_exam(female_exam.id).employee_gender,
            GENDER_FEMALE,
        )

        cases = (
            (male_exam, "Zkoušený", "Zkoušená", "Ing. Jan Novak"),
            (female_exam, "Zkoušená", "Zkoušený", "Mgr. Eva Mala"),
            (legacy_exam, "Zkoušený", "Zkoušená", "Eva Bezudaje"),
        )
        for exam, present, absent, name in cases:
            paper = self.folder / f"paper-{exam.id}.odt"
            paper_test_export_service.export(exam.id, paper)
            _finish_electronic(exam.id)
            protocol = exam_protocol_export_service.export(
                exam.id,
                self.folder / f"protocol-{exam.id}.odt",
            )
            for path in (paper, protocol):
                plain = _plain(path)
                self.assertIn(present, plain)
                self.assertNotIn(absent, plain)
                self.assertIn(name, plain)
                if exam.id == legacy_exam.id:
                    self.assertNotIn("Zkoušející", plain)
                    self.assertNotIn("Předseda komise", plain)
                else:
                    self.assertIn("Zkoušející", plain)
                xml = _xml(path)
                self.assertNotIn('text:style-name="ProtocolNote"', xml)
                if exam.id == legacy_exam.id:
                    self.assertIn("ÚSTNÍ ČÁST", plain)

    def test_migration_adds_nullable_columns_without_guessing(self) -> None:
        employee = _employee("11b-mig", "Jan", "Puvodni")
        topic_id = _written_topic("Migrace 11b")
        exam = _prepare(employee.id, name="Historická", topic_id=topic_id)
        self.assertIsNone(employee.gender)
        self.assertIsNone(test_exam_service.get_exam(exam.id).employee_gender)

        with _db_engine().connect() as connection:
            connection.execute(text("ALTER TABLE test_employees DROP COLUMN gender"))
            connection.execute(text("ALTER TABLE test_exams DROP COLUMN employee_gender"))
            connection.commit()
        self.assertNotIn("gender", _table_columns("test_employees"))
        self.assertNotIn("employee_gender", _table_columns("test_exams"))

        _ensure_test_employee_columns()
        _ensure_test_exam_tables()
        self.assertIn("gender", _table_columns("test_employees"))
        self.assertIn("employee_gender", _table_columns("test_exams"))

        loaded = test_employee_service.get_employee(employee.id)
        assert loaded is not None
        self.assertEqual(loaded.first_name, "Jan")
        self.assertEqual(loaded.last_name, "Puvodni")
        self.assertIsNone(loaded.gender)
        restored = test_exam_service.get_exam(exam.id)
        assert restored is not None
        self.assertIsNone(restored.employee_gender)
        self.assertEqual(restored.employee_display_name, "Jan Puvodni")

        _ensure_test_employee_columns()
        _ensure_test_exam_tables()
        self.assertIsNone(test_employee_service.get_employee(employee.id).gender)


if __name__ == "__main__":
    unittest.main()
