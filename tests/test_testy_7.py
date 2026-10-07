"""TESTY-7: příprava zkoušky a neměnný snapshot."""

from __future__ import annotations

import hashlib
import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-7-"))

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
    from core.services.storage_service import storage_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        AGENDA_EXAMS,
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAM_COL_EMPLOYEE,
        EXAM_COL_STATUS,
        EXAM_COL_TEST,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_PREPARED_LABEL,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        VALIDITY_UNIT_MONTHS,
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
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        TestExamError,
        calculate_valid_until,
        select_and_shuffle,
        shuffle_answers,
        test_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog
    from moduly.testy.ui.testy_page import TestyPage


class PrefixReverse:
    """Prvních k položek a otočené pořadí. Testuje výběr i promíchání."""

    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


class _Item:
    def __init__(self, item_id: int, name: str):
        self.id = item_id
        self.name = name


class _Answer:
    def __init__(self, text: str, is_correct: bool):
        self.text = text
        self.is_correct = is_correct


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _png(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (12, 8), color).save(path, "PNG")
    return path


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _employee(
    number: str,
    first: str,
    last: str,
    *,
    title_before: str = "",
    title_after: str = "",
    may_examine: bool = False,
    role_name: str = "Mistr",
):
    workplace = settings_service.save_workplace(name=f"Provoz {number}")
    role = responsibility_role_service.create_role(name=f"{role_name} {number}")
    employee = test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
        title_before=title_before,
        title_after=title_after,
        may_examine=may_examine,
    )
    return employee, workplace, role


def _written(topic_name: str, texts: list[str], *, image: Path | None = None):
    topic = written_question_topic_service.create_topic(name=topic_name)
    questions = []
    for text in texts:
        questions.append(
            written_question_service.create_question(
                topic_id=topic.id,
                text=text,
                answer_kind=ANSWER_KIND_TEXT,
                answers=_text_answers(),
                question_image_source_path=str(image) if image is not None else None,
            )
        )
    return topic, questions


class ExamSnapshotTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.images = _TMP / "images"

    def setUp(self) -> None:
        with get_session() as session:
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
        self.page = TestyPage()

    def tearDown(self) -> None:
        self.page.close()

    def test_validity_calendar_and_manual_override(self) -> None:
        self.assertEqual(
            calculate_valid_until(date(2026, 12, 15), 2, VALIDITY_UNIT_YEARS),
            date(2028, 12, 15),
        )
        self.assertEqual(
            calculate_valid_until(date(2026, 12, 15), 6, VALIDITY_UNIT_MONTHS),
            date(2027, 6, 15),
        )
        self.assertEqual(
            calculate_valid_until(date(2024, 1, 31), 1, VALIDITY_UNIT_MONTHS),
            date(2024, 2, 29),
        )

        employee, _workplace, _role = _employee("71001", "Jan", "Novák")
        topic, _questions = _written("Platnost", ["Otázka platnosti"])
        test = test_definition_service.create_test(
            name="Platnost test",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=2,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        computed = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2026, 12, 15),
            rng=PrefixReverse(),
        )
        self.assertEqual(computed.valid_until, date(2028, 12, 15))
        self.assertEqual(computed.validity_value, 2)
        self.assertEqual(computed.validity_unit, VALIDITY_UNIT_YEARS)

        months = test_definition_service.create_test(
            name="Platnost měsíce",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=6,
            validity_unit=VALIDITY_UNIT_MONTHS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        by_months = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=months.id,
            exam_date=date(2026, 12, 15),
            rng=PrefixReverse(),
        )
        self.assertEqual(by_months.valid_until, date(2027, 6, 15))
        self.assertEqual(by_months.validity_unit, VALIDITY_UNIT_MONTHS)

        with self.assertRaises(TestExamError) as too_early:
            test_exam_service.prepare_exam(
                employee_id=employee.id,
                test_id=test.id,
                exam_date=date(2026, 12, 15),
                valid_until=date(2026, 12, 14),
                rng=PrefixReverse(),
            )
        self.assertIn("před", str(too_early.exception))

        overridden = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2026, 12, 15),
            valid_until=date(2028, 12, 31),
            rng=PrefixReverse(),
        )
        self.assertEqual(overridden.valid_until, date(2028, 12, 31))
        self.assertEqual(overridden.validity_value, 2)
        self.assertEqual(_count(TestExam), 3)

    def test_selection_shuffle_answers_and_shortage(self) -> None:
        mixed = select_and_shuffle(
            [
                ("A", [_Item(1, "A1"), _Item(2, "A2")], 2),
                ("B", [_Item(3, "B1")], 1),
            ],
            PrefixReverse(),
        )
        self.assertEqual([item.name for item in mixed], ["B1", "A2", "A1"])
        shuffled = shuffle_answers(
            [_Answer("první", True), _Answer("druhá", False), _Answer("třetí", False)],
            PrefixReverse(),
        )
        self.assertEqual([item.text for item in shuffled], ["třetí", "druhá", "první"])
        self.assertEqual(sum(item.is_correct for item in shuffled), 1)

        with self.assertRaises(TestExamError) as pure_shortage:
            select_and_shuffle([("OOPP", [_Item(1, "jen jedna")], 5)], PrefixReverse())
        self.assertIn("OOPP", str(pure_shortage.exception))
        self.assertIn("5", str(pure_shortage.exception))

        employee, _workplace, _role = _employee("71002", "Eva", "Malá")
        topic_a, _ = _written("Okruh A", ["A1", "A2", "A3"])
        topic_b, _ = _written("Okruh B", ["B1"])
        test = test_definition_service.create_test(
            name="Výběr",
            uses_written=True,
            allowed_wrong_answers=1,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[
                TestTopicQuota(topic_a.id, 2),
                TestTopicQuota(topic_b.id, 1),
            ],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2026, 5, 1),
            rng=PrefixReverse(),
        )
        rows = test_exam_service.get_written_questions(exam.id)
        self.assertEqual([row.text for row in rows], ["B1", "A2", "A1"])
        self.assertEqual([row.topic_name for row in rows], ["Okruh B", "Okruh A", "Okruh A"])
        self.assertEqual(exam.written_duration_seconds, 90)
        for row in rows:
            answers = test_exam_service.get_written_answers(row.id)
            self.assertEqual([answer.letter for answer in answers], ["A", "B", "C"])
            correct = [answer for answer in answers if answer.is_correct]
            self.assertEqual(len(correct), 1)
            self.assertEqual(correct[0].letter, "C")
            self.assertEqual(correct[0].text, "první")

        enough_topic, enough_questions = _written("Dost", ["D1", "D2"])
        enough_test = test_definition_service.create_test(
            name="Nedostatek",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(enough_topic.id, 2)],
        )
        written_question_service.deactivate(enough_questions[1].id)
        before = _count(TestExam)
        with self.assertRaises(TestExamError) as shortage:
            test_exam_service.prepare_exam(
                employee_id=employee.id,
                test_id=enough_test.id,
                exam_date=date(2026, 5, 1),
                rng=PrefixReverse(),
            )
        self.assertIn("Dost", str(shortage.exception))
        self.assertIn("1", str(shortage.exception))
        self.assertEqual(_count(TestExam), before)
        self.assertEqual(_count(TestExamWrittenQuestion), 3)
        self.assertEqual(_count(TestExamWrittenAnswer), 9)

        written_question_topic_service.deactivate(topic_b.id)
        with self.assertRaises(TestExamError) as inactive_topic:
            test_exam_service.prepare_exam(
                employee_id=employee.id,
                test_id=test.id,
                exam_date=date(2026, 5, 2),
                rng=PrefixReverse(),
            )
        self.assertIn("Okruh B", str(inactive_topic.exception))
        self.assertIn("0", str(inactive_topic.exception))
        self.assertEqual(_count(TestExam), before)

    def test_image_snapshots_stay_after_bank_change(self) -> None:
        employee, _workplace, _role = _employee("71003", "Petr", "Svoboda")
        prompt = _png(self.images / "zadani.png", (10, 20, 30))
        topic, questions = _written("Obrázky", ["Zadání s obrázkem"], image=prompt)
        picture_test = test_definition_service.create_test(
            name="Obrázek zadání",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=picture_test.id,
            exam_date=date(2026, 6, 1),
            rng=PrefixReverse(),
        )
        row = test_exam_service.get_written_questions(exam.id)[0]
        self.assertEqual(row.text, "Zadání s obrázkem")
        self.assertEqual(row.answer_kind, ANSWER_KIND_TEXT)
        self.assertTrue(row.image_stored_path)
        self.assertNotIn("test_written_question", row.image_stored_path)
        snapshot_path = test_exam_service.resolve_snapshot_image(row.image_stored_path)
        assert snapshot_path is not None
        frozen = snapshot_path.read_bytes()
        self.assertEqual(hashlib.sha256(frozen).hexdigest(), row.image_sha256)
        source = written_question_service.attachment_path(questions[0].image_attachment_id)
        assert source is not None
        self.assertNotEqual(snapshot_path.resolve(), source.resolve())

        replacement = _png(self.images / "zadani-nove.png", (200, 10, 10))
        written_question_service.update_question(
            questions[0].id,
            topic_id=topic.id,
            text="Změněné zadání",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(replacement),
        )
        again = test_exam_service.get_written_questions(exam.id)[0]
        self.assertEqual(again.text, "Zadání s obrázkem")
        self.assertEqual(again.image_sha256, row.image_sha256)
        self.assertEqual(snapshot_path.read_bytes(), frozen)

        image_topic = written_question_topic_service.create_topic(name="Volby")
        paths = [
            _png(self.images / "a.png", (1, 0, 0)),
            _png(self.images / "b.png", (0, 1, 0)),
            _png(self.images / "c.png", (0, 0, 1)),
        ]
        image_question = written_question_service.create_question(
            topic_id=image_topic.id,
            text="Vyberte značku",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(paths[0]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(paths[1])),
                WrittenAnswerInput(image_source_path=str(paths[2])),
            ],
        )
        image_test = test_definition_service.create_test(
            name="Obrázkové odpovědi",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(image_topic.id, 1)],
        )
        image_exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=image_test.id,
            exam_date=date(2026, 6, 2),
            rng=PrefixReverse(),
        )
        image_row = test_exam_service.get_written_questions(image_exam.id)[0]
        answers = test_exam_service.get_written_answers(image_row.id)
        self.assertEqual(len(answers), 3)
        self.assertEqual(sum(answer.is_correct for answer in answers), 1)
        frozen_answers = []
        for answer in answers:
            path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            assert path is not None
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), answer.image_sha256)
            self.assertNotIn("test_written_answer", answer.image_stored_path)
            frozen_answers.append((path, data, answer.image_sha256))

        new_c = _png(self.images / "c-nove.png", (9, 9, 9))
        bank_answers = written_question_service.get_answers(image_question.id)
        written_question_service.update_question(
            image_question.id,
            topic_id=image_topic.id,
            text="Jiná značka",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(
                    image_attachment_id=bank_answers[0].image_attachment_id,
                    is_correct=False,
                ),
                WrittenAnswerInput(
                    image_attachment_id=bank_answers[1].image_attachment_id,
                    is_correct=True,
                ),
                WrittenAnswerInput(image_source_path=str(new_c), is_correct=False),
            ],
        )
        stored = test_exam_service.get_written_answers(image_row.id)
        self.assertEqual([answer.image_sha256 for answer in stored], [item[2] for item in frozen_answers])
        self.assertEqual(sum(answer.is_correct for answer in stored), 1)
        for path, data, _digest in frozen_answers:
            self.assertEqual(path.read_bytes(), data)

        orphan_topic, orphan_questions = _written(
            "Chybí soubor",
            ["Bez souboru"],
            image=_png(self.images / "ztratit.png", (4, 4, 4)),
        )
        lost = written_question_service.attachment_path(orphan_questions[0].image_attachment_id)
        assert lost is not None
        lost.unlink()
        lost_test = test_definition_service.create_test(
            name="Chybějící obrázek",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(orphan_topic.id, 1)],
        )
        before = _count(TestExam)
        with self.assertRaises(TestExamError):
            test_exam_service.prepare_exam(
                employee_id=employee.id,
                test_id=lost_test.id,
                exam_date=date(2026, 6, 3),
                rng=PrefixReverse(),
            )
        self.assertEqual(_count(TestExam), before)

    def test_people_snapshot_and_later_edits_do_not_change_it(self) -> None:
        candidate, workplace, role = _employee(
            "71004",
            "Jan",
            "Novák",
            title_before="Ing.",
            title_after="Ph.D.",
            role_name="Mistr",
        )
        examiner, _ex_workplace, _ex_role = _employee(
            "71005",
            "Klára",
            "Černá",
            title_before="Bc.",
            may_examine=True,
            role_name="Zkoušející",
        )
        chair, _chair_workplace, _chair_role = _employee(
            "71006",
            "Adam",
            "Dvořák",
            may_examine=True,
            role_name="Předseda",
        )
        member, _member_workplace, _member_role = _employee(
            "71007",
            "Iva",
            "Holá",
            may_examine=True,
            role_name="Člen",
        )
        blocked, _blocked_workplace, _blocked_role = _employee(
            "71008",
            "Petr",
            "Malý",
            may_examine=False,
        )
        topic, questions = _written("BOZP historie", ["Co je riziko?", "Druhá kontrola"])
        oral_topic = oral_question_topic_service.create_topic(name="Ústní BOZP")
        oral = oral_question_service.create_question(
            topic_id=oral_topic.id,
            text="Popište postup",
        )
        single = test_definition_service.create_test(
            name="Jeden zkoušející",
            description="původní popis",
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=2,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        with self.assertRaises(TestExamError) as not_examiner:
            test_exam_service.prepare_exam(
                employee_id=candidate.id,
                test_id=single.id,
                exam_date=date(2026, 7, 1),
                examiner_id=blocked.id,
                rng=PrefixReverse(),
            )
        self.assertIn("zkoušet", str(not_examiner.exception))
        test_employee_service.deactivate(examiner.id)
        with self.assertRaises(TestExamError):
            test_exam_service.prepare_exam(
                employee_id=candidate.id,
                test_id=single.id,
                exam_date=date(2026, 7, 1),
                examiner_id=examiner.id,
                rng=PrefixReverse(),
            )
        test_employee_service.activate(examiner.id)
        self.assertEqual(_count(TestExam), 0)

        exam = test_exam_service.prepare_exam(
            employee_id=candidate.id,
            test_id=single.id,
            exam_date=date(2026, 7, 1),
            examiner_id=examiner.id,
            rng=PrefixReverse(),
        )
        self.assertEqual(exam.status, EXAM_STATUS_PREPARED)
        self.assertEqual(exam.employee_personal_number, "71004")
        self.assertEqual(exam.employee_display_name, "Ing. Jan Novák, Ph.D.")
        self.assertEqual(exam.employee_workplace_name, workplace.name)
        self.assertIn("Mistr", exam.employee_roles_text)
        self.assertEqual(exam.test_name, "Jeden zkoušející")
        self.assertEqual(exam.allowed_wrong_answers, 0)
        self.assertEqual(exam.seconds_per_question, 30)
        self.assertEqual(exam.written_duration_seconds, 60)
        people = test_exam_service.get_examiners(exam.id)
        self.assertEqual([(person.role, person.display_name) for person in people], [
            (EXAM_ROLE_EXAMINER, "Bc. Klára Černá"),
        ])
        written_rows = test_exam_service.get_written_questions(exam.id)
        written = next(row for row in written_rows if row.source_question_id == questions[0].id)
        self.assertEqual(written.text, "Co je riziko?")
        self.assertEqual(written.topic_name, "BOZP historie")
        oral_row = test_exam_service.get_oral_questions(exam.id)[0]
        self.assertEqual(oral_row.text, "Popište postup")
        self.assertEqual(oral_row.topic_name, "Ústní BOZP")
        self.assertEqual(oral_row.source_question_id, oral.id)

        commission = test_definition_service.create_test(
            name="Komise",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_COMMISSION,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        with self.assertRaises(TestExamError) as duplicate:
            test_exam_service.prepare_exam(
                employee_id=candidate.id,
                test_id=commission.id,
                exam_date=date(2026, 7, 2),
                chair_id=chair.id,
                member_ids=[chair.id],
                rng=PrefixReverse(),
            )
        self.assertIn("Předseda", str(duplicate.exception))
        with self.assertRaises(TestExamError) as repeated:
            test_exam_service.prepare_exam(
                employee_id=candidate.id,
                test_id=commission.id,
                exam_date=date(2026, 7, 2),
                chair_id=chair.id,
                member_ids=[member.id, member.id],
                rng=PrefixReverse(),
            )
        self.assertIn("vícekrát", str(repeated.exception))
        board = test_exam_service.prepare_exam(
            employee_id=candidate.id,
            test_id=commission.id,
            exam_date=date(2026, 7, 2),
            chair_id=chair.id,
            member_ids=[member.id, examiner.id],
            rng=PrefixReverse(),
        )
        board_people = test_exam_service.get_examiners(board.id)
        self.assertEqual(
            [(person.role, person.display_name) for person in board_people],
            [
                (EXAM_ROLE_CHAIR, "Adam Dvořák"),
                (EXAM_ROLE_MEMBER, "Iva Holá"),
                (EXAM_ROLE_MEMBER, "Bc. Klára Černá"),
            ],
        )

        test_employee_service.update_employee_details(
            candidate.id,
            personal_number="71004",
            first_name="Honza",
            last_name="Novotný",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
            active=True,
            title_before="MUDr.",
            title_after="",
            may_examine=False,
        )
        settings_service.save_workplace(id=workplace.id, name="Jiný provoz")
        responsibility_role_service.update_role(role.id, name="Vedoucí směny")
        test_definition_service.update_test(
            single.id,
            name="Přejmenovaný test",
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=1,
            seconds_per_question=90,
            examiner_mode=EXAMINER_MODE_SINGLE,
            validity_value=2,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        written_question_topic_service.update_topic(topic.id, name="Nový okruh", description="")
        written_question_service.update_question(
            questions[0].id,
            topic_id=topic.id,
            text="Úplně jiná otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=False),
                WrittenAnswerInput(text="druhá", is_correct=True),
                WrittenAnswerInput(text="třetí", is_correct=False),
            ],
        )
        oral_question_topic_service.update_topic(oral_topic.id, name="Jiný ústní", description="")
        oral_question_service.update_question(
            oral.id,
            topic_id=oral_topic.id,
            text="Jiný postup",
        )
        test_employee_service.update_employee_details(
            examiner.id,
            personal_number="71005",
            first_name="Karla",
            last_name="Bílá",
            workplace_id=_ex_workplace.id,
            responsibility_role_ids=[_ex_role.id],
            active=True,
            title_before="",
            title_after="",
            may_examine=True,
        )

        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.employee_display_name, "Ing. Jan Novák, Ph.D.")
        self.assertEqual(fresh.employee_first_name, "Jan")
        self.assertEqual(fresh.employee_last_name, "Novák")
        self.assertEqual(fresh.employee_title_before, "Ing.")
        self.assertEqual(fresh.employee_title_after, "Ph.D.")
        self.assertEqual(fresh.employee_workplace_name, "Provoz 71004")
        self.assertIn("Mistr", fresh.employee_roles_text)
        self.assertNotIn("Vedoucí", fresh.employee_roles_text)
        self.assertEqual(fresh.test_name, "Jeden zkoušející")
        self.assertEqual(fresh.allowed_wrong_answers, 0)
        self.assertEqual(fresh.seconds_per_question, 30)
        self.assertEqual(fresh.written_duration_seconds, 60)
        self.assertEqual(test_exam_service.get_examiners(exam.id)[0].display_name, "Bc. Klára Černá")
        fresh_written = next(
            row
            for row in test_exam_service.get_written_questions(exam.id)
            if row.source_question_id == questions[0].id
        )
        self.assertEqual(fresh_written.text, "Co je riziko?")
        self.assertEqual(fresh_written.topic_name, "BOZP historie")
        correct = [
            answer
            for answer in test_exam_service.get_written_answers(fresh_written.id)
            if answer.is_correct
        ]
        self.assertEqual(correct[0].text, "první")
        self.assertEqual(test_exam_service.get_oral_questions(exam.id)[0].text, "Popište postup")
        self.assertEqual(
            test_exam_service.get_oral_questions(exam.id)[0].topic_name,
            "Ústní BOZP",
        )
        self.assertEqual(test_exam_service.get_examiners(board.id)[0].display_name, "Adam Dvořák")

    def test_list_detail_and_prepare_dialog(self) -> None:
        employee, _workplace, _role = _employee(
            "71009",
            "Jan",
            "Novák",
            title_before="Ing.",
        )
        topic, _questions = _written("Detail", ["Text pro detail"], image=_png(self.images / "detail.png", (8, 8, 8)))
        oral_topic = oral_question_topic_service.create_topic(name="Ústní detail")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Ústní text detailu")
        test = test_definition_service.create_test(
            name="Detail test",
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=2,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        dialog = TestExamPrepareDialog()
        try:
            completer = dialog.employee.completer()
            completer.setCompletionPrefix("71009")
            self.assertGreater(completer.completionCount(), 0)
            completer.setCompletionPrefix("novák")
            self.assertGreater(completer.completionCount(), 0)
            label = f"{employee.personal_number} – {employee.display_name}"
            dialog.employee.setCurrentText(label)
            self.assertEqual(dialog.employee.person_id(), employee.id)
            dialog.exam_date.setDate(QDate(2026, 12, 15))
            dialog.test.setCurrentIndex(dialog.test.findData(test.id))
            self.assertEqual(dialog.valid_until.date().toPython(), date(2028, 12, 15))
            dialog.valid_until.setDate(QDate(2028, 12, 31))
            dialog.exam_date.setDate(QDate(2026, 12, 16))
            self.assertEqual(dialog.valid_until.date().toPython(), date(2028, 12, 31))
            dialog.accept()
            self.assertIsNotNone(dialog.saved_exam_id)
        finally:
            dialog.close()

        exam_id = dialog.saved_exam_id
        assert exam_id is not None
        stored = test_exam_service.get_exam(exam_id)
        assert stored is not None
        self.assertEqual(stored.valid_until, date(2028, 12, 31))
        self.assertEqual(stored.exam_date, date(2026, 12, 16))

        self.page.exams_tab.refresh()
        table = self.page.exams_tab.table
        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(table.item(0, EXAM_COL_EMPLOYEE).text(), "Ing. Jan Novák")
        self.assertEqual(table.item(0, EXAM_COL_TEST).text(), "Detail test")
        self.assertEqual(table.item(0, EXAM_COL_STATUS).text(), EXAM_STATUS_PREPARED_LABEL)
        self.assertFalse(self.page.exams_tab.detail_btn.isEnabled())
        self.page.exams_tab.text_filter.search_edit.setText("71009")
        self.assertFalse(table.isRowHidden(0))
        self.page.exams_tab.text_filter.search_edit.setText("neexistuje")
        self.assertTrue(table.isRowHidden(0))
        self.page.exams_tab.text_filter.search_edit.clear()
        table.selectRow(0)
        self.assertTrue(self.page.exams_tab.detail_btn.isEnabled())
        self.assertEqual(self.page.tabs.tabText(6), AGENDA_EXAMS)
        self.assertEqual(self.page.exams_tab.prepare_btn.text(), "Připravit zkoušku")

        detail = TestExamDetailDialog(exam_id=exam_id)
        try:
            labels = [label.text() for label in detail.findChildren(QLabel)]
            joined = "\n".join(labels)
            self.assertIn("Ing. Jan Novák", joined)
            self.assertIn("71009", joined)
            self.assertIn("Text pro detail", joined)
            self.assertIn("Ústní text detailu", joined)
            self.assertIn("první", joined)
            self.assertNotIn("(správná)", joined)
            self.assertIn("Povolené chyby: 0", joined)
            image = detail.findChild(QLabel, "written-image-1")
            assert image is not None
            self.assertFalse(image.pixmap().isNull())
        finally:
            detail.close()


if __name__ == "__main__":
    unittest.main()
