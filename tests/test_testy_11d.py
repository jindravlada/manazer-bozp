"""TESTY-11d: výpis chyb elektronického protokolu a první podpis zkoušeného."""

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

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-11d-"))
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
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        GENDER_FEMALE,
        GENDER_MALE,
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
        ERROR_LIST_HEADING,
        NO_WRITTEN_ERRORS_LINE,
        WRITTEN_CONFIRM_SENTENCE,
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
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_answer_presentation import (
        ERROR_COLOR,
        ERROR_MARK,
        TONE_CORRECT,
        TONE_ERROR,
        UNANSWERED_ERROR,
        present_answer,
        qt_answer_style,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from sqlalchemy import delete


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _plain(path: Path) -> str:
    text = _xml(path).replace("<text:line-break/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


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
        may_examine=kwargs.get("may_examine", False),
        gender=kwargs.get("gender"),
    )


def _text_question(topic_id: int, text: str) -> None:
    written_question_service.create_question(
        topic_id=topic_id,
        text=text,
        answer_kind=ANSWER_KIND_TEXT,
        answers=[
            WrittenAnswerInput(text="první", is_correct=True),
            WrittenAnswerInput(text="druhá"),
            WrittenAnswerInput(text="třetí"),
        ],
    )


def _prepare(employee_id: int, *, name: str, topic_id: int, quota: int, **kwargs):
    oral_topics = kwargs.get("oral_topics")
    definition = test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=bool(oral_topics),
        allowed_wrong_answers=kwargs.get("allowed_wrong_answers", 0),
        seconds_per_question=30,
        examiner_mode=kwargs.get("examiner_mode", EXAMINER_MODE_NONE),
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic_id, quota)],
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


def _by_text(exam_id: int, text: str):
    return next(
        question
        for question in test_exam_service.get_written_questions(exam_id)
        if question.text == text
    )


def _answers(question):
    return test_exam_service.get_written_answers(question.id)


def _pick(question, *, correct: bool):
    return next(answer for answer in _answers(question) if bool(answer.is_correct) is correct)


def _choose(exam_id: int, question, answer) -> None:
    with get_session() as session:
        session.add(
            TestExamWrittenChoice(
                exam_id=int(exam_id),
                exam_question_id=int(question.id),
                exam_answer_id=int(answer.id),
                selected_letter=answer.letter,
                saved_at=datetime(2026, 10, 7, 9, 0, 0),
            )
        )
        session.commit()


def _finish(exam_id: int) -> None:
    with get_session() as session:
        row = session.get(TestExam, int(exam_id))
        assert row is not None
        row.status = EXAM_STATUS_COMPLETED
        row.written_mode = WRITTEN_MODE_ELECTRONIC
        row.written_result = WRITTEN_RESULT_PASSED
        row.exam_result = WRITTEN_RESULT_PASSED
        row.written_question_count = 3
        row.written_correct_count = 1
        row.written_incorrect_count = 1
        row.written_unanswered_count = 1
        row.written_allowed_wrong_answers = 2
        row.oral_failed_at = datetime(2026, 10, 7, 11, 0, 0)
        session.commit()


def _fingerprint(exam_id: int) -> tuple:
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    questions = [
        (question.position, question.text, question.image_sha256)
        for question in test_exam_service.get_written_questions(exam_id)
    ]
    choices = [
        (choice.exam_question_id, choice.exam_answer_id, choice.selected_letter)
        for choice in test_exam_service.get_written_choices(exam_id)
    ]
    return (
        exam.status,
        exam.written_mode,
        exam.written_result,
        exam.exam_result,
        exam.oral_failed_at,
        exam.employee_gender,
        tuple(questions),
        tuple(choices),
    )


class WrittenErrorProtocolTestCase(unittest.TestCase):
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

    def test_electronic_lists_only_errors_and_keeps_both_signatures(self) -> None:
        employee = _employee("11d-f", "Eva", "Mala", title_before="Mgr.", gender=GENDER_FEMALE)
        examiner = _employee("11d-ex", "Adam", "Zkus", may_examine=True, gender=GENDER_MALE)
        topic = written_question_topic_service.create_topic(name="Chyby 11d")
        _text_question(topic.id, "Správná otázka alfa")
        _text_question(topic.id, "Chybná otázka beta")
        _text_question(topic.id, "Nezodpovězená otázka gama")
        oral = oral_question_topic_service.create_topic(name="Ústní 11d")
        oral_question_service.create_question(topic_id=oral.id, text="První ústní")
        oral_question_service.create_question(topic_id=oral.id, text="Druhá ústní")
        exam = _prepare(
            employee.id,
            name="Protokol chyb",
            topic_id=topic.id,
            quota=3,
            allowed_wrong_answers=2,
            oral_topics=[TestTopicQuota(oral.id, 2)],
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        wrong_question = _by_text(exam.id, "Chybná otázka beta")
        missed_question = _by_text(exam.id, "Nezodpovězená otázka gama")
        right_question = _by_text(exam.id, "Správná otázka alfa")
        wrong = _pick(wrong_question, correct=False)
        right_on_wrong = _pick(wrong_question, correct=True)
        neutral = next(
            answer
            for answer in _answers(wrong_question)
            if answer.id not in {wrong.id, right_on_wrong.id}
        )
        _choose(exam.id, wrong_question, wrong)
        _choose(exam.id, right_question, _pick(right_question, correct=True))
        with get_session() as session:
            bank = session.get(WrittenQuestion, wrong_question.source_question_id)
            assert bank is not None
            bank.text = "Jiné znění z banky"
            session.commit()
        _finish(exam.id)

        paper_path = self.folder / "paper.odt"
        paper_test_export_service.export(exam.id, paper_path)
        batch_dir = self.folder / "batch"
        batch_dir.mkdir()
        batch = paper_test_export_service.export_batch([exam.id], batch_dir)
        for path in (paper_path, batch.test_paths[0]):
            plain = _plain(path)
            self.assertNotIn(ERROR_LIST_HEADING, plain)
            self.assertNotIn(NO_WRITTEN_ERRORS_LINE, plain)
            self.assertLess(plain.index("Výsledek písemné části:"), plain.index(WRITTEN_CONFIRM_SENTENCE))
            self.assertLess(plain.index("Zkoušená:"), plain.index("ÚSTNÍ ČÁST"))
            self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.rindex("Zkoušená"))
            self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.index("Zkoušející"))
            self.assertNotIn("Jiné znění z banky", plain)

        before = _fingerprint(exam.id)
        protocol = exam_protocol_export_service.export(exam.id, self.folder / "protokol.odt")
        self.assertEqual(_fingerprint(exam.id), before)
        plain = _plain(protocol)
        xml = _xml(protocol)
        self.assertIn(ERROR_LIST_HEADING, plain)
        self.assertIn("Chybná otázka beta", plain)
        self.assertIn("Nezodpovězená otázka gama", plain)
        self.assertNotIn("Správná otázka alfa", plain)
        self.assertNotIn("Jiné znění z banky", plain)
        wrong_caption = f"{wrong.letter}) {wrong.text} {ERROR_MARK}"
        right_caption = f"{right_on_wrong.letter}) {right_on_wrong.text}"
        neutral_caption = f"{neutral.letter}) {neutral.text}"
        self.assertIn(wrong_caption, plain)
        self.assertIn(right_caption, plain)
        self.assertIn(neutral_caption, plain)
        self.assertIn(UNANSWERED_ERROR, plain)
        self.assertIn(
            f'<text:span text:style-name="ProtocolAnswerError">{html.escape(wrong_caption)}</text:span>',
            xml,
        )
        self.assertIn(
            f'<text:span text:style-name="ProtocolAnswerCorrect">{html.escape(right_caption)}</text:span>',
            xml,
        )
        self.assertIn(f'<text:p text:style-name="WrittenAnswer">{html.escape(neutral_caption)}</text:p>', xml)
        self.assertIn(f'fo:color="{ERROR_COLOR}"', xml)
        self.assertIn('fo:color="#15803d"', xml)
        self.assertLess(plain.index(WRITTEN_RESULT_LINE), plain.index(ERROR_LIST_HEADING))
        self.assertLess(plain.index(ERROR_LIST_HEADING), plain.index(WRITTEN_CONFIRM_SENTENCE))
        self.assertLess(plain.index("Zkoušená:"), plain.index("ÚSTNÍ ČÁST"))
        self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.rindex("Zkoušená"))
        self.assertNotIn("Zkoušený", plain)
        oral = sorted(test_exam_service.get_oral_questions(exam.id), key=lambda item: item.position)
        self.assertEqual(xml.count('text:style-name="ProtocolOralNext"'), 2)
        self.assertEqual(xml.count('text:style-name="ProtocolOralText"'), 0)
        self.assertLess(plain.index(f"{oral[0].position}. {oral[0].text}"), plain.index(f"{oral[1].position}. {oral[1].text}"))
        between = xml[xml.index(oral[0].text) : xml.index(oral[1].text)]
        self.assertNotIn("<table:table", between)

        detail = TestExamDetailDialog(None, exam_id=exam.id)
        self.addCleanup(detail.close)
        from PySide6.QtWidgets import QLabel

        shown = present_answer(wrong_question, wrong, wrong, evaluated=True)
        label = detail.findChild(QLabel, f"answer-{wrong_question.position}-{wrong.letter}")
        assert label is not None
        self.assertEqual(label.text(), shown[0])
        self.assertEqual(label.styleSheet(), qt_answer_style(TONE_ERROR))
        correct_label = detail.findChild(QLabel, f"answer-{wrong_question.position}-{right_on_wrong.letter}")
        assert correct_label is not None
        self.assertEqual(correct_label.styleSheet(), qt_answer_style(TONE_CORRECT))
        missing = detail.findChild(QLabel, f"written-unanswered-{missed_question.position}")
        assert missing is not None
        self.assertEqual(missing.text(), UNANSWERED_ERROR)
        self.assertEqual(missing.styleSheet(), qt_answer_style(TONE_ERROR))

    def test_no_errors_prints_a_short_line_and_snapshot_images_keep_color_off_the_picture(self) -> None:
        employee = _employee("11d-m", "Jan", "Novak", gender=GENDER_MALE)
        clear_topic = written_question_topic_service.create_topic(name="Bez chyb 11d")
        _text_question(clear_topic.id, "Jediná správná otázka")
        clear_exam = _prepare(
            employee.id,
            name="Bez chyb",
            topic_id=clear_topic.id,
            quota=1,
        )
        question = test_exam_service.get_written_questions(clear_exam.id)[0]
        _choose(clear_exam.id, question, _pick(question, correct=True))
        _finish(clear_exam.id)
        clear_path = exam_protocol_export_service.export(clear_exam.id, self.folder / "bez-chyb.odt")
        clear_plain = _plain(clear_path)
        self.assertIn(NO_WRITTEN_ERRORS_LINE, clear_plain)
        self.assertNotIn("Jediná správná otázka", clear_plain)
        self.assertNotIn(ERROR_MARK, clear_plain)
        self.assertNotIn(UNANSWERED_ERROR, clear_plain)
        self.assertIn("Zkoušený:", clear_plain)
        self.assertLess(clear_plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), clear_plain.rindex("Zkoušený"))
        self.assertNotIn("ÚSTNÍ ČÁST", clear_plain)
        self.assertNotIn("Zkoušená", clear_plain)

        images = self.folder / "img"
        prompt = _png(images / "zadani.png", (10, 20, 30), (80, 40))
        paths = [
            _png(images / "a.png", (180, 0, 0), (40, 30)),
            _png(images / "b.png", (0, 140, 0), (40, 30)),
            _png(images / "c.png", (0, 0, 160), (40, 30)),
        ]
        image_topic = written_question_topic_service.create_topic(name="Obrázky 11d")
        written_question_service.create_question(
            topic_id=image_topic.id,
            text="Snapshotová značka",
            answer_kind=ANSWER_KIND_IMAGE,
            question_image_source_path=str(prompt),
            answers=[
                WrittenAnswerInput(image_source_path=str(paths[0]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(paths[1])),
                WrittenAnswerInput(image_source_path=str(paths[2])),
            ],
        )
        image_exam = _prepare(
            employee.id,
            name="Obrázková chyba",
            topic_id=image_topic.id,
            quota=1,
            allowed_wrong_answers=0,
        )
        image_question = test_exam_service.get_written_questions(image_exam.id)[0]
        wrong = _pick(image_question, correct=False)
        correct = _pick(image_question, correct=True)
        prompt_bytes = test_exam_service.resolve_snapshot_image(image_question.image_stored_path).read_bytes()
        wrong_bytes = test_exam_service.resolve_snapshot_image(wrong.image_stored_path).read_bytes()
        with get_session() as session:
            bank = session.get(WrittenQuestion, image_question.source_question_id)
            assert bank is not None
            bank.text = "Nová značka z banky"
            session.commit()
        _choose(image_exam.id, image_question, wrong)
        _finish(image_exam.id)
        image_path = exam_protocol_export_service.export(image_exam.id, self.folder / "obrazek.odt")
        image_plain = _plain(image_path)
        image_xml = _xml(image_path)
        self.assertIn("Snapshotová značka", image_plain)
        self.assertNotIn("Nová značka z banky", image_plain)
        self.assertIn(f"{wrong.letter}) {ERROR_MARK}", image_plain)
        self.assertIn(f"{correct.letter})", image_plain)
        self.assertIn(f'<text:span text:style-name="ProtocolAnswerError">{wrong.letter}) {ERROR_MARK}</text:span>', image_xml)
        self.assertIn(f'<text:span text:style-name="ProtocolAnswerCorrect">{correct.letter})</text:span>', image_xml)
        frame_at = image_xml.find("<draw:frame")
        self.assertGreater(frame_at, 0)
        self.assertNotIn("ProtocolAnswer", image_xml[frame_at - 180 : frame_at])
        with zipfile.ZipFile(image_path) as archive:
            blobs = [
                archive.read(name)
                for name in archive.namelist()
                if name.startswith("Pictures/")
            ]
        self.assertIn(prompt_bytes, blobs)
        self.assertIn(wrong_bytes, blobs)
        self.assertIn('table:style-name="WrittenBlockRow"', image_xml)

    def test_examiner_modes_keep_the_final_block_after_the_first_confirmation(self) -> None:
        employee = _employee("11d-e", "Jan", "Novak")
        examiner = _employee("11d-e2", "Adam", "Zkus", may_examine=True)
        chair = _employee("11d-e3", "Iva", "Predseda", may_examine=True)
        member = _employee("11d-e4", "Otto", "Clen", may_examine=True)
        topic = written_question_topic_service.create_topic(name="Režimy 11d")
        _text_question(topic.id, "Otázka režimu")
        none_exam = _prepare(employee.id, name="Bez zkoušejícího", topic_id=topic.id, quota=1)
        single = _prepare(
            employee.id,
            name="Jeden zkoušející",
            topic_id=topic.id,
            quota=1,
            examiner_mode=EXAMINER_MODE_SINGLE,
            examiner_id=examiner.id,
        )
        commission = _prepare(
            employee.id,
            name="Komise",
            topic_id=topic.id,
            quota=1,
            examiner_mode=EXAMINER_MODE_COMMISSION,
            chair_id=chair.id,
            member_ids=[member.id],
        )
        cases = (
            (none_exam, []),
            (single, ["Zkoušející"]),
            (commission, ["Předseda komise", "Člen komise"]),
        )
        for exam, roles in cases:
            path = self.folder / f"{exam.id}.odt"
            paper_test_export_service.export(exam.id, path)
            plain = _plain(path)
            self.assertNotIn(ERROR_LIST_HEADING, plain)
            self.assertLess(plain.index(WRITTEN_CONFIRM_SENTENCE), plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"))
            self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.rindex("Zkoušený"))
            self.assertNotIn("ÚSTNÍ ČÁST", plain)
            for role in ("Zkoušející", "Předseda komise", "Člen komise"):
                if role in roles:
                    self.assertLess(plain.index("CELKOVÝ VÝSLEDEK ZKOUŠKY"), plain.index(role))
                else:
                    self.assertNotIn(role, plain)
            if roles == ["Předseda komise", "Člen komise"]:
                self.assertLess(plain.index("Předseda komise"), plain.index("Člen komise"))


if __name__ == "__main__":
    unittest.main()
