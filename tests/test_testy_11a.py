"""TESTY-11a: protokol papírového testu a samostatný protokol elektronické zkoušky."""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-11a-"))
_EXAM_DAY = date(2026, 10, 7)

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
        ANSWER_KIND_TEXT,
        EXAM_ACTION_PRINT_PROTOCOL,
        EXAM_COL_ID,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_MODE_PAPER,
        WRITTEN_RESULT_FAILED,
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
        BLANK_EXAM_DATE_LINE,
        MANUAL_RESULT_LINE,
        WRITTEN_RESULT_LINE,
    )
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exams_tab import TestExamsTab
    from PySide6.QtCore import QItemSelectionModel


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


def _answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _written_topic(name: str) -> int:
    topic = written_question_topic_service.create_topic(name=name)
    for index in range(3):
        written_question_service.create_question(
            topic_id=topic.id,
            text=f"Písemná otázka {name} {index}",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_answers(),
        )
    return topic.id


def _prepare(employee_id: int, **kwargs):
    topic_id = kwargs.get("topic_id") or _written_topic(kwargs.get("topic_name", "Okruh"))
    oral_topics = kwargs.get("oral_topics")
    definition = test_definition_service.create_test(
        name=kwargs.get("name", "Zkouška protokolu"),
        uses_written=True,
        uses_oral=bool(oral_topics),
        allowed_wrong_answers=1,
        seconds_per_question=30,
        examiner_mode=kwargs.get("examiner_mode", EXAMINER_MODE_NONE),
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic_id, 2)],
        oral_topics=oral_topics,
    )
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=definition.id,
        exam_date=_EXAM_DAY,
        examiner_id=kwargs.get("examiner_id"),
        chair_id=kwargs.get("chair_id"),
        member_ids=kwargs.get("member_ids"),
        rng=PrefixReverse(),
    )


def _oral_topics() -> list[TestTopicQuota]:
    topic = oral_question_topic_service.create_topic(name="Ústní protokol")
    oral_question_service.create_question(topic_id=topic.id, text="Popište únikový plán")
    oral_question_service.create_question(topic_id=topic.id, text="Vysvětlete hlášení úrazu")
    return [TestTopicQuota(topic.id, 2)]


def _plain(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("content.xml").decode("utf-8")
    text = xml.replace("<text:line-break/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _state(exam_id: int) -> tuple:
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    oral = [
        (question.position, question.text)
        for question in test_exam_service.get_oral_questions(exam_id)
    ]
    people = [
        (person.role, person.display_name)
        for person in test_exam_service.get_examiners(exam_id)
    ]
    return (
        exam.status,
        exam.exam_date,
        exam.written_mode,
        exam.written_result,
        exam.exam_result,
        exam.oral_failed_at,
        exam.written_question_count,
        exam.written_correct_count,
        exam.written_incorrect_count,
        exam.written_unanswered_count,
        exam.written_allowed_wrong_answers,
        tuple(oral),
        tuple(people),
    )


def _mark(exam_id: int, **fields) -> None:
    with get_session() as session:
        row = session.get(TestExam, int(exam_id))
        assert row is not None
        for key, value in fields.items():
            setattr(row, key, value)
        session.commit()


def _select_exam(table, exam_id: int) -> None:
    table.clearSelection()
    for row in range(table.rowCount()):
        item = table.item(row, EXAM_COL_ID)
        if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
            table.selectRow(row)
            return
    raise AssertionError(exam_id)


class ExamProtocolTestCase(unittest.TestCase):
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

    def test_paper_test_is_the_protocol_and_keeps_a_blank_date(self) -> None:
        employee = _employee("1101", "Jan", "Novak", title_before="Ing.", workplace="Hala", role_name="Svářeč")
        examiner = _employee("1102", "Adam", "Zkus", title_before="Bc.", may_examine=True)
        chair = _employee("1103", "Iva", "Predseda", title_after="Ph.D.", may_examine=True)
        member = _employee("1104", "Otto", "Clen", title_before="Ing.", may_examine=True)
        oral = _oral_topics()
        topic_id = _written_topic("Papir")

        with_oral = _prepare(
            employee.id,
            name="S ústní částí",
            topic_id=topic_id,
            oral_topics=oral,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        before = _state(with_oral.id)
        target = self.folder / "test.odt"
        paper_test_export_service.export(with_oral.id, target)
        self.assertEqual(_state(with_oral.id), before)
        self.assertEqual(test_exam_service.get_exam(with_oral.id).exam_date, _EXAM_DAY)
        plain = _plain(target)
        xml = _xml(target)
        self.assertIn(BLANK_EXAM_DATE_LINE, plain)
        self.assertNotIn("Datum zkoušky", plain)
        self.assertNotIn("7. 10. 2026", plain)
        self.assertIn("PÍSEMNÁ ČÁST", plain)
        self.assertIn("Výsledek písemné části:", plain)
        self.assertIn(MANUAL_RESULT_LINE, plain)
        self.assertNotIn("\u2611", plain)
        self.assertNotIn("form:checkbox", xml)
        self.assertIn("ÚSTNÍ ČÁST", plain)
        oral_rows = test_exam_service.get_oral_questions(with_oral.id)
        first_oral = f"{oral_rows[0].position}. {oral_rows[0].text}"
        second_oral = f"{oral_rows[1].position}. {oral_rows[1].text}"
        self.assertLess(plain.index(first_oral), plain.index(second_oral))
        self.assertIn("Výsledek ústní části:", plain)
        self.assertIn("CELKOVÝ VÝSLEDEK ZKOUŠKY", plain)
        self.assertIn("Zkoušený", plain)
        self.assertIn("Ing. Jan Novak", plain)
        self.assertIn("Zkoušející", plain)
        self.assertIn("Bc. Adam Zkus", plain)
        self.assertNotIn("Předseda komise", plain)
        self.assertEqual(plain.count(MANUAL_RESULT_LINE), 3)
        self.assertEqual(xml.count('text:style-name="WrittenSpacer"'), 1)
        tail = xml[xml.rfind("</table:table>") :]
        self.assertNotIn("WrittenSpacer", tail)
        self.assertIn('text:style-name="WrittenDocumentEnd"', tail)
        self.assertIn('fo:keep-together="always"', xml)
        self.assertEqual(xml.count('text:style-name="ProtocolOralNext"'), 2)
        self.assertNotIn('text:style-name="ProtocolNote"', xml)
        self.assertNotIn('table:style-name="ProtocolOral"', xml)
        self.assertIn("ProtocolSignRow", xml)
        self.assertNotIn('fo:break-before="page"', xml)
        self.assertEqual(list(self.folder.glob("Protokol_*.odt")), [])

        plain_only = _prepare(employee.id, name="Bez ústní", topic_id=topic_id)
        only_path = self.folder / "bez-ustni.odt"
        paper_test_export_service.export(plain_only.id, only_path)
        only_plain = _plain(only_path)
        self.assertNotIn("ÚSTNÍ ČÁST", only_plain)
        self.assertNotIn("Výsledek ústní části", only_plain)
        self.assertIn("CELKOVÝ VÝSLEDEK ZKOUŠKY", only_plain)
        self.assertIn("Zkoušený", only_plain)
        self.assertNotIn("Zkoušející", only_plain)
        self.assertEqual(only_plain.count(MANUAL_RESULT_LINE), 2)

        commission = _prepare(
            employee.id,
            name="Komise",
            topic_id=topic_id,
            examiner_mode=EXAMINER_MODE_COMMISSION,
            chair_id=chair.id,
            member_ids=[member.id],
        )
        paper_test_export_service.export(commission.id, self.folder / "komise.odt")
        commission_plain = _plain(self.folder / "komise.odt")
        self.assertIn("Předseda komise", commission_plain)
        self.assertIn("Iva Predseda, Ph.D.", commission_plain)
        self.assertIn("Člen komise", commission_plain)
        self.assertIn("Ing. Otto Clen", commission_plain)
        self.assertLess(
            commission_plain.index("Předseda komise"),
            commission_plain.index("Člen komise"),
        )

        batch_dir = self.folder / "davka"
        batch_dir.mkdir()
        result = paper_test_export_service.export_batch(
            [with_oral.id],
            batch_dir,
            include_shared_key=True,
        )
        batch_plain = _plain(result.test_paths[0])
        self.assertIn("ÚSTNÍ ČÁST", batch_plain)
        self.assertIn("Popište únikový plán", batch_plain)
        self.assertIn(BLANK_EXAM_DATE_LINE, batch_plain)
        self.assertNotIn("Datum zkoušky", batch_plain)
        key_plain = _plain(result.key_path)
        self.assertIn("Datum zkoušky", key_plain)
        self.assertNotIn("ÚSTNÍ ČÁST", key_plain)
        self.assertNotIn(MANUAL_RESULT_LINE, key_plain)

    def test_electronic_protocol_is_limited_and_uses_the_stored_summary(self) -> None:
        employee = _employee(
            "1201",
            "Petra",
            "Elektronicka",
            title_before="Mgr.",
            workplace="Laboratoř",
            role_name="Laborant",
        )
        examiner = _employee("1202", "David", "Zkusici", title_before="Ing.", may_examine=True)
        topic_id = _written_topic("Elektro")
        passed = _prepare(
            employee.id,
            name="Elektronický test",
            topic_id=topic_id,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
            oral_topics=_oral_topics(),
        )
        question_text = test_exam_service.get_written_questions(passed.id)[0].text
        _mark(
            passed.id,
            status=EXAM_STATUS_COMPLETED,
            written_mode=WRITTEN_MODE_ELECTRONIC,
            written_result=WRITTEN_RESULT_PASSED,
            exam_result=WRITTEN_RESULT_PASSED,
            written_question_count=4,
            written_correct_count=3,
            written_incorrect_count=1,
            written_unanswered_count=0,
            written_allowed_wrong_answers=1,
            oral_failed_at=datetime(2026, 10, 7, 12, 0, 0),
        )
        prepared = _prepare(employee.id, name="Ještě ne", topic_id=topic_id)
        failed = _prepare(employee.id, name="Nevyhověl písemně", topic_id=topic_id)
        _mark(
            failed.id,
            status=EXAM_STATUS_COMPLETED,
            written_mode=WRITTEN_MODE_ELECTRONIC,
            written_result=WRITTEN_RESULT_FAILED,
            exam_result=WRITTEN_RESULT_FAILED,
        )
        paper = _prepare(employee.id, name="Papírová hotová", topic_id=topic_id)
        _mark(
            paper.id,
            status=EXAM_STATUS_COMPLETED,
            written_mode=WRITTEN_MODE_PAPER,
            written_result=WRITTEN_RESULT_PASSED,
            exam_result=WRITTEN_RESULT_PASSED,
        )
        started = _prepare(employee.id, name="Běží elektronicky", topic_id=topic_id)
        _mark(started.id, status=EXAM_STATUS_STARTED, written_mode=WRITTEN_MODE_ELECTRONIC)

        self.assertTrue(exam_protocol_export_service.can_export(passed.id))
        self.assertFalse(exam_protocol_export_service.can_export(prepared.id))
        self.assertFalse(exam_protocol_export_service.can_export(started.id))
        self.assertFalse(exam_protocol_export_service.can_export(failed.id))
        self.assertFalse(exam_protocol_export_service.can_export(paper.id))
        with self.assertRaises(TestExamError) as paper_error:
            exam_protocol_export_service.export(paper.id, self.folder / "paper.odt")
        self.assertIn("tištěném testu", str(paper_error.exception))
        self.assertFalse((self.folder / "paper.odt").exists())
        with self.assertRaises(TestExamError):
            exam_protocol_export_service.export(failed.id, self.folder / "failed.odt")
        with self.assertRaises(TestExamError):
            exam_protocol_export_service.export(prepared.id, self.folder / "prepared.odt")

        before = _state(passed.id)
        path = exam_protocol_export_service.export(passed.id, self.folder / "protokol.odt")
        self.assertEqual(_state(passed.id), before)
        self.assertEqual(test_exam_service.get_exam(passed.id).status, EXAM_STATUS_COMPLETED)
        plain = _plain(path)
        self.assertIn("PROTOKOL O ZKOUŠCE", plain)
        self.assertIn("Elektronický test", plain)
        self.assertIn("Mgr. Petra Elektronicka", plain)
        self.assertIn("Osobní číslo: 1201", plain)
        self.assertIn("Pracoviště: Laboratoř", plain)
        self.assertIn("Funkce: Laborant", plain)
        self.assertIn(BLANK_EXAM_DATE_LINE, plain)
        self.assertNotIn("Datum zkoušky", plain)
        self.assertNotIn("7. 10. 2026", plain)
        self.assertIn("Počet otázek: 4", plain)
        self.assertIn("Správně: 3", plain)
        self.assertIn("Chybně: 1", plain)
        self.assertIn("Nezodpovězeno: 0", plain)
        self.assertIn("Povolený počet chyb: 1", plain)
        self.assertIn(WRITTEN_RESULT_LINE, plain)
        self.assertIn("VÝPIS CHYBNĚ ZODPOVĚZENÝCH OTÁZEK", plain)
        self.assertIn("Nezodpovězeno — chyba", plain)
        self.assertIn(question_text, plain)
        self.assertIn(
            "S výsledkem písemné části souhlasím, špatné odpovědi mi byly vysvětleny:",
            plain,
        )
        self.assertLess(plain.index("Zkoušený(á):"), plain.index("ÚSTNÍ ČÁST"))
        self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.rindex("Zkoušený"))
        oral_rows = test_exam_service.get_oral_questions(passed.id)
        self.assertLess(
            plain.index(f"{oral_rows[0].position}. {oral_rows[0].text}"),
            plain.index(f"{oral_rows[1].position}. {oral_rows[1].text}"),
        )
        self.assertIn("CELKOVÝ VÝSLEDEK ZKOUŠKY", plain)
        self.assertIn(MANUAL_RESULT_LINE, plain)
        self.assertNotIn("\u2611", plain)
        self.assertEqual(plain.count(MANUAL_RESULT_LINE), 2)
        self.assertIn("Zkoušený", plain)
        self.assertIn("Zkoušející", plain)
        self.assertIn("Ing. David Zkusici", plain)

        tab = TestExamsTab()
        self.addCleanup(tab.close)
        button = tab.findChild(QPushButton, "exam-print-protocol-button")
        self.assertEqual(button.text(), EXAM_ACTION_PRINT_PROTOCOL)
        self.assertFalse(button.isEnabled())
        _select_exam(tab.table, passed.id)
        tab._update_action_buttons()
        self.assertTrue(button.isEnabled())
        _select_exam(tab.table, paper.id)
        tab._update_action_buttons()
        self.assertFalse(button.isEnabled())
        _select_exam(tab.table, failed.id)
        tab._update_action_buttons()
        self.assertFalse(button.isEnabled())
        _select_exam(tab.table, prepared.id)
        tab._update_action_buttons()
        self.assertFalse(button.isEnabled())
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        model = tab.table.selectionModel()
        tab.table.clearSelection()
        for exam_id in (passed.id, paper.id):
            for row in range(tab.table.rowCount()):
                item = tab.table.item(row, EXAM_COL_ID)
                if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
                    model.select(tab.table.model().index(row, 0), flags)
        tab._update_action_buttons()
        self.assertFalse(button.isEnabled())
