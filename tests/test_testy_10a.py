"""TESTY-10a: papírový písemný test ze snapshotu zkoušky."""

from __future__ import annotations

import hashlib
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
from xml.etree import ElementTree as ET

from PIL import Image
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-10a-"))

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
        EXAM_ACTION_PRINT_WRITTEN,
        EXAM_COL_ID,
        EXAM_STATUS_PREPARED,
        EXAMINER_MODE_NONE,
        PAPER_TEST_INSTRUCTION,
        PAPER_TEST_KEY_OPTION,
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
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.paper_test_export_service import (
        ANSWER_KEY_BLOCK_SIZE,
        _header_paragraphs,
        paper_test_export_service,
        plain_export_text,
        render_compact_answer_key_xml,
        split_answer_key_rows,
        variant_label,
    )
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
    from moduly.testy.ui.paper_test_options_dialog import PaperTestOptionsDialog
    from moduly.testy.ui.testy_page import TestyPage


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (12, 8)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _employee(number: str, first: str, last: str, **kwargs):
    workplace = settings_service.save_workplace(name=kwargs.get("workplace", f"Provoz {number}"))
    role = responsibility_role_service.create_role(name=kwargs.get("role_name", f"Mistr {number}"))
    employee = test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
        title_before=kwargs.get("title_before", ""),
        title_after=kwargs.get("title_after", ""),
        may_examine=False,
    )
    return employee


def _odt_part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def _plain(xml: str) -> str:
    text = xml.replace("<text:line-break/>", "\n")
    text = re.sub(r"<text:s\b[^>]*/>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _paragraph_text(paragraph) -> str:
    return "".join(run.text for run in paragraph.runs)


def _fingerprint(exam_id: int) -> tuple:
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    questions = []
    for question in test_exam_service.get_written_questions(exam_id):
        answers = []
        for answer in test_exam_service.get_written_answers(question.id):
            answers.append(
                (
                    answer.id,
                    answer.letter,
                    answer.position,
                    answer.text,
                    bool(answer.is_correct),
                    answer.image_stored_path,
                    answer.image_sha256,
                )
            )
        questions.append(
            (
                question.id,
                question.position,
                question.text,
                question.answer_kind,
                question.image_stored_path,
                question.image_sha256,
                tuple(answers),
            )
        )
    return (
        exam.status,
        exam.written_result,
        exam.exam_result,
        exam.written_evaluated_at,
        exam.oral_failed_at,
        exam.written_question_count,
        exam.written_started_at,
        exam.written_finished_at,
        tuple(questions),
    )


def _key_grids(xml: str) -> list[tuple[list[str], list[str]]]:
    root = ET.fromstring(xml)
    table_tag = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    text_tag = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    grids: list[tuple[list[str], list[str]]] = []
    for table in root.iter(f"{table_tag}table"):
        style = table.attrib.get(f"{table_tag}style-name", "")
        if not style.startswith("WrittenKeyTable"):
            continue
        rows: list[list[str]] = []
        for row in table.findall(f"{table_tag}table-row"):
            cells: list[str] = []
            for cell in row.findall(f"{table_tag}table-cell"):
                pieces = [
                    "".join(node.itertext())
                    for node in cell.findall(f"{text_tag}p")
                ]
                cells.append("".join(pieces).strip())
            rows.append(cells)
        numbers = rows[0] if rows else []
        letters = rows[1] if len(rows) > 1 else []
        grids.append((numbers, letters))
    return grids


def _correct_letters(exam_id: int) -> list[str]:
    letters = []
    for question in test_exam_service.get_written_questions(exam_id):
        found = ""
        for answer in test_exam_service.get_written_answers(question.id):
            if answer.is_correct:
                found = answer.letter
                break
        letters.append(f"{question.position}. {found}")
    return letters


def _forbid_redraw():
    boom = AssertionError("Export nesmí znovu losovat ani číst banku otázek.")

    def fail(*_args, **_kwargs):
        raise boom

    return (
        patch("random.shuffle", side_effect=fail),
        patch("random.sample", side_effect=fail),
        patch("moduly.testy.sluzby.test_exam_service.select_and_shuffle", side_effect=fail),
        patch("moduly.testy.sluzby.test_exam_service.shuffle_answers", side_effect=fail),
        patch.object(written_question_service, "get_answers", side_effect=fail),
        patch.object(written_question_service, "list_questions", side_effect=fail),
        patch.object(written_question_service, "get_question", side_effect=fail),
    )


class PaperTestExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.images = _TMP / "images"

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
        self.page = TestyPage()

    def tearDown(self) -> None:
        self.page.close()

    def test_export_reads_snapshot_and_repeat_stays_identical(self) -> None:
        employee = _employee(
            "1001",
            "Jan",
            "Novák",
            title_before="Ing.",
            title_after="Ph.D.",
            role_name="TajnyOkruhRole",
            workplace="Hala Sever",
        )
        topic = written_question_topic_service.create_topic(name="TajnyOkruh")
        first = written_question_service.create_question(
            topic_id=topic.id,
            text="Otázka alfa",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            note="TajnaPoznamka",
        )
        written_question_service.create_question(
            topic_id=topic.id,
            text="Hodnota A < B & C",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            note="TajnaPoznamka",
        )
        definition = test_definition_service.create_test(
            name="Písemná zkouška BOZP",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        self.assertEqual(
            paper_test_export_service.test_filename(exam),
            "Test_Jan_Novak_2026-10-06.odt",
        )
        self.assertEqual(
            paper_test_export_service.key_filename(exam),
            "Klic_Jan_Novak_2026-10-06.odt",
        )
        questions = test_exam_service.get_written_questions(exam.id)
        self.assertEqual(
            [row.text for row in questions],
            ["Otázka alfa", "Hodnota A < B & C"],
        )
        letters = _correct_letters(exam.id)
        self.assertTrue(all(re.fullmatch(r"\d+\. [ABC]", line) for line in letters))
        before = _fingerprint(exam.id)
        image_hashes = _snapshot_image_hashes(exam.id)

        written_question_service.update_question(
            first.id,
            topic_id=topic.id,
            text="Změněné znění z banky",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            note="Nová poznámka",
        )

        first_path = _TMP / "export-a" / "test.odt"
        second_path = _TMP / "export-b" / "test.odt"
        patches = _forbid_redraw()
        for item in patches:
            item.start()
        try:
            first_result = paper_test_export_service.export(exam.id, first_path)
            second_result = paper_test_export_service.export(exam.id, second_path)
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertIsNone(first_result.key_path)
        self.assertFalse((first_path.parent / "Klic_Jan_Novak_2026-10-06.odt").exists())
        self.assertEqual(_odt_part(first_path, "content.xml"), _odt_part(second_path, "content.xml"))
        self.assertEqual(_fingerprint(exam.id), before)
        self.assertEqual(_snapshot_image_hashes(exam.id), image_hashes)
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.status, EXAM_STATUS_PREPARED)
        self.assertIsNone(fresh.written_result)
        self.assertIsNone(fresh.exam_result)

        content = _odt_part(first_path, "content.xml")
        ET.fromstring(content)
        plain = _plain(content)
        self.assertIn("Písemná zkouška BOZP", plain)
        self.assertIn("Ing. Jan Novák, Ph.D.", plain)
        self.assertIn("Osobní číslo: 1001", plain)
        self.assertIn("Pracoviště: Hala Sever", plain)
        self.assertIn("Datum: ______________________", plain)
        self.assertNotIn("Datum zkoušky", plain)
        self.assertNotIn("6. 10. 2026", plain)
        self.assertIn(PAPER_TEST_INSTRUCTION, plain)
        self.assertIn("Čas na písemnou část: 2 min", plain)
        self.assertNotIn(variant_label(exam), plain)
        self.assertIn(variant_label(exam), _odt_part(first_path, "styles.xml"))
        self.assertLess(plain.index("Otázka alfa"), plain.index("Hodnota A < B & C"))
        self.assertNotIn("Změněné znění z banky", plain)
        self.assertNotIn("TajnaPoznamka", plain)
        self.assertNotIn("TajnyOkruh", plain)
        self.assertNotIn("None", plain)
        self.assertNotIn("is_correct", content)
        self.assertNotIn('fo:break-before="page"', content)
        self.assertNotIn('fo:break-after="page"', content)
        self.assertEqual(content.count('text:style-name="WrittenSpacer"'), len(questions) - 1)
        tail = content[content.rfind("</table:table>") :]
        self.assertNotIn("WrittenSpacer", tail)
        self.assertIn('text:style-name="WrittenDocumentEnd"', tail)
        end_style = content.split('style:name="WrittenDocumentEnd"', 1)[1][:400]
        self.assertIn('fo:font-size="2pt"', end_style)
        self.assertIn('fo:margin-bottom="0cm"', end_style)
        self.assertIn('fo:keep-together="auto"', end_style)
        self.assertNotIn('fo:keep-together="always"', end_style)
        self.assertIn('fo:keep-together="always"', content)
        self.assertIn('style:may-break-between-rows="false"', content)
        for line in letters:
            self.assertNotIn(line, plain)
        for question in questions:
            answers = test_exam_service.get_written_answers(question.id)
            ordered = sorted(answers, key=lambda item: item.position)
            self.assertEqual([item.letter for item in ordered], ["A", "B", "C"])
            cursor = 0
            for answer in ordered:
                marker = f"{answer.letter})  {answer.text}"
                found = plain.find(marker, cursor)
                self.assertGreaterEqual(found, 0)
                cursor = found + len(marker)
        self.assertEqual(content.count('text:style-name="WrittenAnswer"'), 6)
        self._assert_question_blocks_stay_together(content, image_choices=False)

    def test_images_come_from_snapshot_and_keep_aspect(self) -> None:
        employee = _employee("1002", "Eva", "Malá")
        prompt = _png(self.images / "zadani.png", (20, 40, 80), (800, 800))
        topic = written_question_topic_service.create_topic(name="Obrazky")
        question = written_question_service.create_question(
            topic_id=topic.id,
            text="Poznej značku na obrázku",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(prompt),
        )
        definition = test_definition_service.create_test(
            name="Test s obrázkem",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        row = test_exam_service.get_written_questions(exam.id)[0]
        snapshot = test_exam_service.resolve_snapshot_image(row.image_stored_path)
        assert snapshot is not None
        frozen = snapshot.read_bytes()
        replacement = _png(self.images / "zadani-nove.png", (200, 10, 10), (32, 32))
        written_question_service.update_question(
            question.id,
            topic_id=topic.id,
            text="Jiné zadání z banky",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(replacement),
        )

        paths = [
            _png(self.images / "a.png", (180, 0, 0), (800, 200)),
            _png(self.images / "b.png", (0, 140, 0), (200, 800)),
            _png(self.images / "c.png", (0, 0, 160), (400, 400)),
        ]
        image_topic = written_question_topic_service.create_topic(name="Volby")
        image_question = written_question_service.create_question(
            topic_id=image_topic.id,
            text="Vyberte správnou značku",
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
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(image_topic.id, 1)],
        )
        image_exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=image_test.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        image_row = test_exam_service.get_written_questions(image_exam.id)[0]
        frozen_answers = []
        for answer in test_exam_service.get_written_answers(image_row.id):
            path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            assert path is not None
            frozen_answers.append((answer.letter, path.read_bytes(), answer.image_sha256))
        bank_answers = written_question_service.get_answers(image_question.id)
        new_c = _png(self.images / "c-nove.png", (9, 9, 9), (16, 16))
        written_question_service.update_question(
            image_question.id,
            topic_id=image_topic.id,
            text="Jiná značka z banky",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(
                    image_attachment_id=bank_answers[0].image_attachment_id,
                    is_correct=bank_answers[0].is_correct,
                ),
                WrittenAnswerInput(
                    image_attachment_id=bank_answers[1].image_attachment_id,
                    is_correct=bank_answers[1].is_correct,
                ),
                WrittenAnswerInput(image_source_path=str(new_c), is_correct=bank_answers[2].is_correct),
            ],
        )
        before = _fingerprint(image_exam.id)
        target = _TMP / "obrazky.odt"
        choice_target = _TMP / "volby.odt"
        patches = _forbid_redraw()
        for item in patches:
            item.start()
        try:
            paper_test_export_service.export(exam.id, target)
            paper_test_export_service.export(image_exam.id, choice_target)
        finally:
            for item in reversed(patches):
                item.stop()

        self.assertEqual(snapshot.read_bytes(), frozen)
        self.assertEqual(_fingerprint(image_exam.id), before)
        content = _odt_part(target, "content.xml")
        self.assertNotIn("Jiné zadání z banky", _plain(content))
        self.assertNotIn("test_written_question", content)
        self._assert_embedded_bytes(target, [frozen])
        frames = _frames(content)
        self.assertEqual(len(frames), 1)
        width, height, _href = frames[0]
        self.assertAlmostEqual(width, height, delta=0.05)
        self.assertLessEqual(width, 9.05)
        self.assertGreaterEqual(width, 6.0)
        self._assert_question_blocks_stay_together(content, image_choices=False)

        choice_xml = _odt_part(choice_target, "content.xml")
        ET.fromstring(choice_xml)
        self.assertNotIn("Jiná značka z banky", _plain(choice_xml))
        self.assertNotIn("test_written_answer", choice_xml)
        self.assertNotIn("is_correct", choice_xml)
        for line in _correct_letters(image_exam.id):
            self.assertNotIn(line, _plain(choice_xml))
        self._assert_embedded_bytes(choice_target, [item[1] for item in frozen_answers])
        self.assertNotIn(new_c.read_bytes(), _embedded_payloads(choice_target))
        choice_frames = _frames(choice_xml)
        self.assertEqual(len(choice_frames), 3)
        expected_ratios = (800 / 200, 200 / 800, 400 / 400)
        # PrefixReverse otočí A/B/C, poměry stran jdou v pořadí snímku ve výstupu.
        # Ověříme každý snímek proti jeho pixelům přes pořadí v balíčku.
        self.assertEqual(len(choice_frames), 3)
        for width, height, _href in choice_frames:
            self.assertLessEqual(width, 5.05)
            self.assertLessEqual(height, 6.55)
            self.assertGreater(width, 0.5)
            self.assertGreater(height, 0.5)
        ratios = [width / height for width, height, _href in choice_frames]
        self.assertEqual(len(ratios), 3)
        # Tři různé poměry, žádný snímek není roztažený mimo svůj zdroj.
        source_ratios = sorted(expected_ratios)
        self.assertEqual(sorted(round(item, 2) for item in ratios), [round(item, 2) for item in source_ratios])
        block = _choice_table(choice_xml)
        self.assertEqual(block.count("<table:table-row"), 1)
        self.assertEqual(block.count("<draw:frame"), 3)
        self.assertIn('table:style-name="WrittenBlockRow"', block)
        self.assertIn("A)", _plain(choice_xml))
        self.assertIn("B)", _plain(choice_xml))
        self.assertIn("C)", _plain(choice_xml))
        self._assert_question_blocks_stay_together(choice_xml, image_choices=True)

    def test_key_is_optional_and_matches_the_same_variant(self) -> None:
        employee = _employee("1003", "Petr", "Svoboda")
        topic = written_question_topic_service.create_topic(name="Klic")
        written_question_service.create_question(
            topic_id=topic.id,
            text="První otázka klíče",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        written_question_service.create_question(
            topic_id=topic.id,
            text="Druhá otázka klíče",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        definition = test_definition_service.create_test(
            name="Test ke klíči",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        with get_session() as session:
            row = session.get(TestExam, exam.id)
            assert row is not None
            row.employee_workplace_name = ""
            row.employee_personal_number = ""
            row.written_duration_seconds = 0
            session.commit()
        before = _fingerprint(exam.id)
        target = _TMP / "klic" / "Test_Petr_Svoboda_2026-10-06.odt"
        key_path = target.with_name("Klic_Petr_Svoboda_2026-10-06.odt")
        result = paper_test_export_service.export(
            exam.id,
            target,
            include_key=True,
            key_path=key_path,
        )
        self.assertEqual(result.key_path, key_path.resolve())
        self.assertTrue(target.is_file())
        self.assertTrue(key_path.is_file())
        self.assertEqual(_fingerprint(exam.id), before)
        test_plain = _plain(_odt_part(target, "content.xml"))
        key_plain = _plain(_odt_part(key_path, "content.xml"))
        self.assertNotIn("None", test_plain)
        self.assertNotIn("None", key_plain)
        self.assertNotIn("Osobní číslo", test_plain)
        self.assertNotIn("Pracoviště", test_plain)
        self.assertNotIn("Čas na písemnou část", test_plain)
        self.assertIn("Petr Svoboda", test_plain)
        self.assertIn("Datum: ______________________", test_plain)
        self.assertNotIn("Datum zkoušky", test_plain)
        self.assertNotIn("6. 10. 2026", test_plain)
        letters = _correct_letters(exam.id)
        for line in letters:
            self.assertNotIn(line, test_plain)
        self.assertNotIn(variant_label(exam), test_plain)
        self.assertIn(variant_label(exam), _odt_part(target, "styles.xml"))
        self.assertIn(variant_label(exam), key_plain)
        self.assertIn(variant_label(exam), _odt_part(key_path, "styles.xml"))
        self.assertIn("Test ke klíči", key_plain)
        self.assertIn("Klíč správných odpovědí", key_plain)
        self.assertNotIn(PAPER_TEST_INSTRUCTION, key_plain)
        self.assertNotIn("Petr Svoboda", key_plain)
        self.assertNotIn("Osobní číslo", key_plain)
        self.assertNotIn("Pracoviště", key_plain)
        self.assertNotIn("Datum zkoušky", key_plain)
        key_xml = _odt_part(key_path, "content.xml")
        grids = _key_grids(key_xml)
        self.assertEqual(len(grids), 1)
        numbers, key_letters = grids[0]
        questions = test_exam_service.get_written_questions(exam.id)
        self.assertEqual(numbers, [str(question.position) for question in questions])
        self.assertEqual(
            key_letters,
            [line.split(". ", 1)[1] for line in letters],
        )
        self.assertLessEqual(len(numbers), ANSWER_KEY_BLOCK_SIZE)
        self.assertIn('fo:text-align="center"', key_xml)

        anonymous = SimpleNamespace(
            id=exam.id,
            test_name="Test",
            employee_display_name=None,
            employee_title_before=None,
            employee_first_name="Jan",
            employee_last_name="Novák",
            employee_title_after=None,
            employee_personal_number=None,
            employee_workplace_name=None,
            exam_date=None,
            written_duration_seconds=None,
        )
        header = "\n".join(_paragraph_text(item) for item in _header_paragraphs(anonymous, for_key=False))
        self.assertNotIn("None", header)
        self.assertIn("Jan Novák", header)
        self.assertNotIn("Osobní číslo", header)
        self.assertNotIn("Pracoviště", header)
        self.assertNotIn("Datum zkoušky", header)
        self.assertNotIn("Čas na písemnou část", header)
        self.assertEqual(plain_export_text(None), "")

        oral_topic = oral_question_topic_service.create_topic(name="Ustni")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Povězte postup")
        oral_test = test_definition_service.create_test(
            name="Jen ústní",
            uses_written=False,
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        oral_exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=oral_test.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        self.assertFalse(paper_test_export_service.can_export(oral_exam.id))
        with self.assertRaises(Exception):
            paper_test_export_service.export(oral_exam.id, _TMP / "ustni.odt")
        self.assertFalse((_TMP / "ustni.odt").exists())

    def test_compact_key_splits_blocks_without_redrawing(self) -> None:
        self.assertEqual(
            [len(block) for block in split_answer_key_rows([(index, "A") for index in range(1, 16)])],
            [15],
        )
        thirty = [(index, "ABC"[(index - 1) % 3]) for index in range(1, 31)]
        thirty_blocks = split_answer_key_rows(thirty)
        self.assertEqual([len(block) for block in thirty_blocks], [15, 15])
        self.assertEqual(thirty_blocks[0][0], (1, "A"))
        self.assertEqual(thirty_blocks[0][-1], (15, "C"))
        self.assertEqual(thirty_blocks[1][0], (16, "A"))
        self.assertEqual(thirty_blocks[1][-1], (30, "C"))
        longer = split_answer_key_rows([(index, "B") for index in range(1, 32)])
        self.assertEqual([len(block) for block in longer], [15, 15, 1])
        xml = render_compact_answer_key_xml(thirty)
        self.assertEqual(xml.count("<table:table "), 2)
        self.assertEqual(xml.count('table:number-columns-repeated="15"'), 2)
        self.assertIn(">1</text:p>", xml)
        self.assertIn(">15</text:p>", xml)
        self.assertIn(">16</text:p>", xml)
        self.assertIn(">30</text:p>", xml)
        self.assertNotIn("WrittenDocumentEnd", xml)
        self.assertEqual(xml.count("WrittenKeyGap"), 1)

        employee = _employee(
            "1010",
            "Klara",
            "Horak",
            workplace="Dílna klíčů",
        )
        topic = written_question_topic_service.create_topic(name="Blok klice")
        for index in range(6):
            written_question_service.create_question(
                topic_id=topic.id,
                text=f"Otázka klíče {index}",
                answer_kind=ANSWER_KIND_TEXT,
                answers=_text_answers(),
            )
        definition = test_definition_service.create_test(
            name="Šest otázek",
            uses_written=True,
            allowed_wrong_answers=1,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 6)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 7),
            rng=PrefixReverse(),
        )
        before = _fingerprint(exam.id)
        target = _TMP / "kompakt" / "test.odt"
        key_path = target.with_name("klic.odt")
        patches = _forbid_redraw()
        for item in patches:
            item.start()
        try:
            paper_test_export_service.export(
                exam.id,
                target,
                include_key=True,
                key_path=key_path,
            )
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(_fingerprint(exam.id), before)
        key_plain = _plain(_odt_part(key_path, "content.xml"))
        self.assertIn("Šest otázek", key_plain)
        self.assertIn(variant_label(exam), key_plain)
        self.assertNotIn("Klara Horak", key_plain)
        self.assertNotIn("1010", key_plain)
        self.assertNotIn("Dílna klíčů", key_plain)
        self.assertNotIn("Datum zkoušky", key_plain)
        self.assertNotIn("Osobní číslo", key_plain)
        self.assertNotIn("Pracoviště", key_plain)
        grids = _key_grids(_odt_part(key_path, "content.xml"))
        key_xml = _odt_part(key_path, "content.xml")
        self.assertIn('text:style-name="WrittenDocumentEnd"', key_xml)
        self.assertEqual(len(grids), 1)
        numbers, key_letters = grids[0]
        questions = test_exam_service.get_written_questions(exam.id)
        self.assertEqual(numbers, [str(question.position) for question in questions])
        expected = []
        for question in questions:
            letter = next(
                answer.letter
                for answer in test_exam_service.get_written_answers(question.id)
                if answer.is_correct
            )
            expected.append(letter)
        self.assertEqual(key_letters, expected)
        self.assertEqual(len(numbers), 6)

    def test_print_action_is_available_only_for_written_snapshot(self) -> None:
        dialog = PaperTestOptionsDialog()
        self.assertEqual(dialog.key_checkbox.text(), PAPER_TEST_KEY_OPTION)
        self.assertFalse(dialog.include_key)
        dialog.close()

        employee = _employee("1004", "Jana", "Veselá")
        topic = written_question_topic_service.create_topic(name="Tisk")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Otázka pro tisk",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        definition = test_definition_service.create_test(
            name="Test k tisku",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 6),
            rng=PrefixReverse(),
        )
        second = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 7),
            rng=PrefixReverse(),
        )
        oral_topic = oral_question_topic_service.create_topic(name="Ustni tisk")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Ústní otázka")
        oral_test = test_definition_service.create_test(
            name="Ústní zkouška",
            uses_written=False,
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        oral_exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=oral_test.id,
            exam_date=date(2026, 10, 8),
            rng=PrefixReverse(),
        )
        tab = self.page.exams_tab
        tab.refresh()
        self.assertEqual(tab.print_btn.text(), EXAM_ACTION_PRINT_WRITTEN)
        self.assertFalse(tab.print_btn.isEnabled())
        _select_exam(tab.table, oral_exam.id)
        self.assertFalse(tab.print_btn.isEnabled())
        _select_exam(tab.table, exam.id)
        self.assertTrue(tab.print_btn.isEnabled())
        _select_rows(tab.table, [exam.id, second.id])
        self.assertFalse(tab.print_btn.isEnabled())

        _select_exam(tab.table, exam.id)
        before = _fingerprint(exam.id)
        with patch.object(PaperTestOptionsDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            tab.print_paper_test()
        self.assertEqual(_fingerprint(exam.id), before)

        target = _TMP / "ui" / "vystup.odt"
        key_target = target.with_name(paper_test_export_service.key_filename(exam))

        def accept_without_key(self):
            self.key_checkbox.setChecked(False)
            return QDialog.DialogCode.Accepted

        with (
            patch.object(PaperTestOptionsDialog, "exec", accept_without_key),
            patch(
                "moduly.testy.ui.test_exams_tab.QFileDialog.getSaveFileName",
                return_value=(str(target), "OpenDocument (*.odt)"),
            ) as save_dialog,
            patch("moduly.testy.ui.test_exams_tab.open_export_file") as opener,
        ):
            tab.print_paper_test()
        save_dialog.assert_called_once()
        self.assertTrue(target.is_file())
        self.assertFalse(key_target.exists())
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(_fingerprint(exam.id), before)

        def accept_with_key(self):
            self.key_checkbox.setChecked(True)
            return QDialog.DialogCode.Accepted

        with (
            patch.object(PaperTestOptionsDialog, "exec", accept_with_key),
            patch(
                "moduly.testy.ui.test_exams_tab.QFileDialog.getSaveFileName",
                return_value=(str(target), "OpenDocument (*.odt)"),
            ),
            patch("moduly.testy.ui.test_exams_tab.open_export_file") as opener,
        ):
            tab.print_paper_test()
        self.assertTrue(key_target.is_file())
        self.assertEqual(opener.call_count, 2)
        self.assertNotIn(variant_label(exam), _plain(_odt_part(target, "content.xml")))
        self.assertIn(variant_label(exam), _odt_part(target, "styles.xml"))
        self.assertIn(variant_label(exam), _plain(_odt_part(key_target, "content.xml")))
        self.assertEqual(_fingerprint(exam.id), before)
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.status, EXAM_STATUS_PREPARED)

    def _assert_question_blocks_stay_together(self, xml: str, *, image_choices: bool) -> None:
        style = re.search(
            r'<style:style style:name="WrittenBlockRow".*?</style:style>',
            xml,
            re.DOTALL,
        )
        self.assertIsNotNone(style)
        assert style is not None
        self.assertIn('fo:keep-together="always"', style.group(0))
        table_style = re.search(
            r'<style:style style:name="WrittenBlock".*?</style:style>',
            xml,
            re.DOTALL,
        )
        self.assertIsNotNone(table_style)
        assert table_style is not None
        self.assertIn('style:may-break-between-rows="false"', table_style.group(0))
        blocks = xml.split('<table:table table:style-name="WrittenBlock">')[1:]
        self.assertGreaterEqual(len(blocks), 1)
        for block in blocks:
            self.assertIn('table:style-name="WrittenBlockRow"', block)
            if image_choices:
                self.assertIn('table:style-name="WrittenChoices"', block)
                choices = _choice_table(block)
                self.assertEqual(choices.count("<table:table-row"), 1)
                self.assertEqual(choices.count("<draw:frame"), 3)
            else:
                self.assertEqual(block.split("</table:table>")[0].count("<table:table-row"), 1)

    def _assert_embedded_bytes(self, path: Path, expected: list[bytes]) -> None:
        payloads = _embedded_payloads(path)
        self.assertEqual(
            {hashlib.sha256(item).hexdigest() for item in payloads},
            {hashlib.sha256(item).hexdigest() for item in expected},
        )


def _choice_table(xml: str) -> str:
    start = xml.index('table:style-name="WrittenChoices"')
    end = xml.index("</table:table>", start)
    return xml[start:end]


def _frames(xml: str) -> list[tuple[float, float, str]]:
    return [
        (float(width), float(height), href)
        for width, height, href in re.findall(
            r'svg:width="([0-9.]+)cm" svg:height="([0-9.]+)cm".{0,240}?xlink:href="([^"]+)"',
            xml,
        )
    ]


def _embedded_payloads(path: Path) -> list[bytes]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.startswith("Pictures/")]
        return [archive.read(name) for name in sorted(names)]


def _snapshot_image_hashes(exam_id: int) -> tuple:
    hashes = []
    for question in test_exam_service.get_written_questions(exam_id):
        path = test_exam_service.resolve_snapshot_image(question.image_stored_path)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() if path else "")
        for answer in test_exam_service.get_written_answers(question.id):
            answer_path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            hashes.append(
                hashlib.sha256(answer_path.read_bytes()).hexdigest() if answer_path else ""
            )
    return tuple(hashes)


def _select_exam(table, exam_id: int) -> None:
    table.clearSelection()
    for row in range(table.rowCount()):
        item = table.item(row, EXAM_COL_ID)
        if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
            table.selectRow(row)
            return
    raise AssertionError(f"Zkouška {exam_id} není v tabulce.")


def _select_rows(table, exam_ids: list[int]) -> None:
    table.clearSelection()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    model = table.selectionModel()
    assert model is not None
    for exam_id in exam_ids:
        for row in range(table.rowCount()):
            item = table.item(row, EXAM_COL_ID)
            if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
                model.select(table.model().index(row, 0), flags)
                break


if __name__ == "__main__":
    unittest.main()
