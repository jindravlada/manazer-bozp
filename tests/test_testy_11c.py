"""TESTY-11c: stránkování začátku a konce ústní části protokolu."""

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
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-11c-"))
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
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_NONE,
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
        MANUAL_RESULT_LINE,
        render_electronic_protocol_xml,
        render_paper_protocol_xml,
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
    from sqlalchemy import delete


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _expected(items: list[tuple[int, str]]) -> list[tuple[str, str]]:
    ordered = sorted(items, key=lambda item: int(item[0]))
    flow = [("ProtocolHeading", "ÚSTNÍ ČÁST")]
    last_index = len(ordered) - 1
    for index, (position, text) in enumerate(ordered):
        style = "ProtocolOralNext" if index == 0 or index == last_index else "ProtocolOralText"
        flow.append((style, f"{int(position)}. {text}"))
    flow.append(("ProtocolHeading", "Výsledek ústní části:"))
    flow.append(("ProtocolCheck", MANUAL_RESULT_LINE))
    return flow


def _oral_flow(xml: str) -> list[tuple[str, str]]:
    paragraphs = re.findall(r'<text:p text:style-name="([^"]+)">([^<]*)</text:p>', xml)
    start = next(index for index, (_style, text) in enumerate(paragraphs) if "ÚSTNÍ ČÁST" in text)
    flow: list[tuple[str, str]] = []
    for style, text in paragraphs[start:]:
        flow.append((style, html.unescape(text)))
        if style == "ProtocolCheck" and any(
            item.startswith("Výsledek ústní části") for _item_style, item in flow
        ):
            break
    return flow


def _style_body(xml: str, name: str) -> str:
    start = xml.find(f'style:name="{name}"')
    if start < 0:
        raise AssertionError(name)
    end = xml.find("</style:style>", start)
    return xml[start:end]


def _oral_topics(name: str, texts: list[str]) -> list[TestTopicQuota]:
    topic = oral_question_topic_service.create_topic(name=name)
    for text in texts:
        oral_question_service.create_question(topic_id=topic.id, text=text)
    return [TestTopicQuota(topic.id, len(texts))]


def _prepare(employee_id: int, topic_id: int, oral_topics, name: str):
    definition = test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=True,
        allowed_wrong_answers=0,
        seconds_per_question=30,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic_id, 1)],
        oral_topics=oral_topics,
    )
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=definition.id,
        exam_date=_EXAM_DAY,
        rng=PrefixReverse(),
    )


def _snapshot_items(exam_id: int) -> list[tuple[int, str]]:
    rows = test_exam_service.get_oral_questions(exam_id)
    return [(int(row.position), str(row.text)) for row in rows]


class OralPagingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

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

    def test_opening_middle_and_closing_stay_shared(self) -> None:
        single = [(1, "Jediná otázka")]
        pair = [(1, "První otázka"), (2, "Druhá otázka")]
        many = [
            (1, "První otázka"),
            (2, "Druhá otázka"),
            (3, "Třetí otázka"),
            (4, "Čtvrtá otázka"),
        ]
        people = [("Zkoušený(á):", "Jan Novak")]
        for items in (single, pair, many):
            paper = render_paper_protocol_xml(items, people)
            electronic = render_electronic_protocol_xml(["Počet otázek: 1"], items, people)
            expected = _expected(items)
            self.assertEqual(_oral_flow(paper), expected)
            self.assertEqual(_oral_flow(electronic), expected)
            oral_xml = paper[paper.index("ÚSTNÍ ČÁST") : paper.index("CELKOVÝ VÝSLEDEK")]
            self.assertNotIn("<table:table", oral_xml)
            self.assertNotIn('fo:break-before="page"', oral_xml)

        single_flow = _expected(single)
        self.assertEqual(
            [style for style, _text in single_flow if style.startswith("ProtocolOral")],
            ["ProtocolOralNext"],
        )
        pair_styles = [style for style, _text in _expected(pair) if style.startswith("ProtocolOral")]
        self.assertEqual(pair_styles, ["ProtocolOralNext", "ProtocolOralNext"])
        many_styles = [style for style, _text in _expected(many) if style.startswith("ProtocolOral")]
        self.assertEqual(
            many_styles,
            ["ProtocolOralNext", "ProtocolOralText", "ProtocolOralText", "ProtocolOralNext"],
        )
        self.assertEqual(many_styles[1], "ProtocolOralText")
        self.assertNotEqual(len(set(many_styles)), 1)

    def test_paper_and_electronic_documents_use_the_same_chain(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz 11c")
        role = responsibility_role_service.create_role(name="Mistr 11c")
        employee = test_employee_service.create_employee(
            personal_number="11c",
            first_name="Jan",
            last_name="Novak",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        topic = written_question_topic_service.create_topic(name="Písemné 11c")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Písemná otázka 11c",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=True),
                WrittenAnswerInput(text="druhá"),
                WrittenAnswerInput(text="třetí"),
            ],
        )
        many = _prepare(
            employee.id,
            topic.id,
            _oral_topics(
                "Čtyři ústní",
                ["První otázka", "Druhá otázka", "Třetí otázka", "Čtvrtá otázka"],
            ),
            "Čtyři otázky",
        )
        single = _prepare(
            employee.id,
            topic.id,
            _oral_topics("Jedna ústní", ["Jediná otázka"]),
            "Jedna otázka",
        )

        for exam in (many, single):
            paper_path = self.folder / f"paper-{exam.id}.odt"
            paper_test_export_service.export(exam.id, paper_path)
            with get_session() as session:
                row = session.get(TestExam, exam.id)
                assert row is not None
                row.status = EXAM_STATUS_COMPLETED
                row.written_mode = WRITTEN_MODE_ELECTRONIC
                row.written_result = WRITTEN_RESULT_PASSED
                row.exam_result = WRITTEN_RESULT_PASSED
                row.written_question_count = 1
                row.written_correct_count = 1
                row.written_incorrect_count = 0
                row.written_unanswered_count = 0
                row.written_allowed_wrong_answers = 0
                session.commit()
            protocol_path = exam_protocol_export_service.export(
                exam.id,
                self.folder / f"protocol-{exam.id}.odt",
            )
            expected = _expected(_snapshot_items(exam.id))
            paper_xml = zipfile.ZipFile(paper_path).read("content.xml").decode("utf-8")
            protocol_xml = zipfile.ZipFile(protocol_path).read("content.xml").decode("utf-8")
            self.assertEqual(_oral_flow(paper_xml), expected)
            self.assertEqual(_oral_flow(protocol_xml), expected)
            for xml in (paper_xml, protocol_xml):
                chained = _style_body(xml, "ProtocolOralNext")
                loose = _style_body(xml, "ProtocolOralText")
                heading = _style_body(xml, "ProtocolHeading")
                self.assertIn('fo:margin-top="0.04cm"', chained)
                self.assertIn('fo:margin-bottom="0.04cm"', chained)
                self.assertIn('fo:keep-together="always"', chained)
                self.assertIn('fo:keep-with-next="always"', chained)
                self.assertIn('fo:margin-top="0.04cm"', loose)
                self.assertIn('fo:margin-bottom="0.04cm"', loose)
                self.assertIn('fo:keep-together="always"', loose)
                self.assertNotIn("keep-with-next", loose)
                self.assertIn('fo:keep-with-next="always"', heading)


if __name__ == "__main__":
    unittest.main()
