"""TESTY-11b: kompaktní ústní otázky, instrukce testu a jednotný podpis zkoušeného."""

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

from PySide6.QtWidgets import QApplication
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
    from moduly.testy.sluzby.test_employee_service import test_employee_service
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


def _raw_value(table: str, row_id: int, column: str):
    with _db_engine().connect() as connection:
        return connection.execute(
            text(f"SELECT {column} FROM {table} WHERE id = :row_id"),
            {"row_id": row_id},
        ).scalar()


_EXAMINEE_LABEL = "Zkoušený(á):"


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
            self.assertEqual(xml.count('text:style-name="ProtocolOralNext"'), 2)
            self.assertEqual(xml.count('text:style-name="ProtocolOralText"'), 0)
            self.assertNotIn('text:style-name="ProtocolNote"', xml)
            self.assertNotIn('table:style-name="ProtocolOral"', xml)
            style = xml[xml.find('style:name="ProtocolOralText"') :][:420]
            self.assertIn('fo:margin-top="0.04cm"', style)
            self.assertIn('fo:margin-bottom="0.04cm"', style)
            self.assertIn('fo:keep-together="always"', style)

    def test_employee_is_saved_without_gender(self) -> None:
        self.assertNotIn("gender", _table_columns("test_employees"))
        created = _employee("11b-new", "Eva", "Nova", title_before="Ing.", may_examine=True)
        self.assertFalse(hasattr(created, "gender"))
        loaded = test_employee_service.get_employee(created.id)
        assert loaded is not None
        self.assertEqual(loaded.first_name, "Eva")
        self.assertEqual(loaded.title_before, "Ing.")
        self.assertTrue(loaded.may_examine)

        updated = test_employee_service.update_employee_details(
            created.id,
            personal_number=loaded.personal_number,
            first_name="Eliška",
            last_name=loaded.last_name,
            title_before=loaded.title_before,
            workplace_id=loaded.workplace_id,
            responsibility_role_ids=test_employee_service.get_role_ids(created.id),
            active=True,
            may_examine=False,
        )
        self.assertEqual(updated.first_name, "Eliška")
        self.assertFalse(updated.may_examine)
        self.assertFalse(hasattr(updated, "gender"))

    def test_editor_saves_without_gender(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz editor")
        role = responsibility_role_service.create_role(name="Role editor")
        dialog = TestEmployeeDialog()
        self.addCleanup(dialog.close)
        self.assertFalse(hasattr(dialog, "gender"))
        dialog.personal_number.setText("11b-ui")
        dialog.title_before.setText("Bc.")
        dialog.first_name.setText("Eva")
        dialog.last_name.setText("Nova")
        dialog.workplace.set_workplace_id(workplace.id)
        dialog.roles.set_role_ids([role.id])
        dialog.may_examine.setChecked(True)
        dialog.accept()

        created = test_employee_service.get_employee(dialog.saved_employee_id)
        assert created is not None
        self.assertEqual(created.display_name, "Bc. Eva Nova")
        self.assertTrue(created.may_examine)
        self.assertFalse(hasattr(created, "gender"))

        edit = TestEmployeeDialog(
            employee=created,
            role_ids=test_employee_service.get_role_ids(created.id),
        )
        self.addCleanup(edit.close)
        self.assertFalse(hasattr(edit, "gender"))
        self.assertEqual(edit.title_before.text(), "Bc.")
        self.assertTrue(edit.may_examine.isChecked())
        edit.last_name.setText("Nová")
        edit.accept()
        saved = test_employee_service.get_employee(created.id)
        assert saved is not None
        self.assertEqual(saved.last_name, "Nová")
        self.assertEqual(saved.title_before, "Bc.")
        self.assertTrue(saved.may_examine)

    def test_new_exam_and_both_protocols_use_one_label(self) -> None:
        self.assertEqual(examinee_role_label(), _EXAMINEE_LABEL)
        self.assertNotIn("employee_gender", _table_columns("test_exams"))
        commission = protocol_people(
            SimpleNamespace(
                employee_gender="female",
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
            [_EXAMINEE_LABEL, "Předseda/předsedkyně komise", "Člen(ka) komise"],
        )

        topic_id = _written_topic("Snapshot 11b")
        oral = _oral_topics("Ústní snapshot")
        examiner = _employee("11b-ex", "Adam", "Zkus", may_examine=True)
        examinee = _employee("11b-man", "Jan", "Novak", title_before="Ing.")
        exam = _prepare(
            examinee.id,
            name="Bez pohlaví",
            topic_id=topic_id,
            oral_topics=oral,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertFalse(hasattr(stored, "employee_gender"))
        self.assertEqual(stored.employee_display_name, "Ing. Jan Novak")

        paper = self.folder / "paper.odt"
        paper_test_export_service.export(exam.id, paper)
        _finish_electronic(exam.id)
        protocol = exam_protocol_export_service.export(exam.id, self.folder / "protocol.odt")
        for path in (paper, protocol):
            plain = _plain(path)
            self.assertEqual(plain.count(_EXAMINEE_LABEL), 2)
            self.assertLess(plain.index(_EXAMINEE_LABEL), plain.index("ÚSTNÍ ČÁST"))
            self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.rindex(_EXAMINEE_LABEL))
            self.assertNotIn("Zkoušená", plain)
            self.assertIn("Ing. Jan Novak", plain)
            self.assertIn("Zkoušející", plain)
            self.assertNotIn("Předseda/předsedkyně komise", plain)

    def test_legacy_gender_column_stays_readable(self) -> None:
        employee = _employee("11b-mig", "Eva", "Puvodni", title_before="Mgr.")
        topic_id = _written_topic("Migrace 11b")
        exam = _prepare(employee.id, name="Historická", topic_id=topic_id)
        self.assertNotIn("gender", _table_columns("test_employees"))
        self.assertNotIn("employee_gender", _table_columns("test_exams"))

        with _db_engine().connect() as connection:
            connection.execute(text("ALTER TABLE test_employees ADD COLUMN gender VARCHAR(10)"))
            connection.execute(
                text("ALTER TABLE test_exams ADD COLUMN employee_gender VARCHAR(10)")
            )
            connection.execute(
                text("UPDATE test_exams SET employee_gender = 'female' WHERE id = :exam_id"),
                {"exam_id": exam.id},
            )
            connection.execute(
                text("UPDATE test_employees SET gender = 'female' WHERE id = :employee_id"),
                {"employee_id": employee.id},
            )
            connection.commit()

        _ensure_test_employee_columns()
        _ensure_test_exam_tables()
        self.assertIn("gender", _table_columns("test_employees"))
        self.assertIn("employee_gender", _table_columns("test_exams"))
        self.assertEqual(_raw_value("test_exams", exam.id, "employee_gender"), "female")

        loaded = test_employee_service.get_employee(employee.id)
        assert loaded is not None
        self.assertEqual(loaded.display_name, "Mgr. Eva Puvodni")
        restored = test_exam_service.get_exam(exam.id)
        assert restored is not None
        self.assertEqual(restored.employee_display_name, "Mgr. Eva Puvodni")
        self.assertFalse(hasattr(restored, "employee_gender"))
        self.assertTrue(test_exam_service.get_written_questions(exam.id))

        paper = self.folder / "legacy-paper.odt"
        paper_test_export_service.export(exam.id, paper)
        _finish_electronic(exam.id)
        protocol = exam_protocol_export_service.export(exam.id, self.folder / "legacy-protocol.odt")
        for path in (paper, protocol):
            plain = _plain(path)
            self.assertEqual(plain.count(_EXAMINEE_LABEL), 2)
            self.assertNotIn("Zkoušená", plain)
            self.assertIn("Mgr. Eva Puvodni", plain)
        self.assertEqual(_raw_value("test_exams", exam.id, "employee_gender"), "female")
        self.assertEqual(_raw_value("test_employees", employee.id, "gender"), "female")

        later = _employee("11b-after", "Jan", "Novy")
        later_exam = _prepare(later.id, name="Nová po sloupci", topic_id=topic_id)
        self.assertIsNone(_raw_value("test_exams", later_exam.id, "employee_gender"))
        self.assertIsNone(_raw_value("test_employees", later.id, "gender"))

        with _db_engine().connect() as connection:
            connection.execute(text("ALTER TABLE test_employees DROP COLUMN gender"))
            connection.execute(text("ALTER TABLE test_exams DROP COLUMN employee_gender"))
            connection.commit()


if __name__ == "__main__":
    unittest.main()
