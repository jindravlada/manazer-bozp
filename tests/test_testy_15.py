"""TESTY-15: tisk studijních otázek se správnými odpověďmi."""

from __future__ import annotations

import html
import importlib
import os
import random
import re
import shutil
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-15-"))

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
        EXAMINER_MODE_NONE,
        STUDY_ORAL_HEADING,
        STUDY_QUESTIONS_ACTION,
        STUDY_QUESTIONS_EMPTY,
        STUDY_QUESTIONS_TITLE,
        STUDY_WRITTEN_HEADING,
        TEST_COL_ID,
        TEST_COL_NAME,
        VALIDITY_UNIT_YEARS,
    )
    from moduly.testy.modely.oral_question import OralQuestion
    from moduly.testy.modely.oral_question_topic import OralQuestionTopic
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import TestDefinitionWrittenTopic
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.study_questions_export_service import (
        StudyQuestionsError,
        study_questions_export_service,
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
    from moduly.testy.ui.test_definitions_tab import TestDefinitionsTab


def _wipe() -> None:
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
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


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _fields(name: str, **kwargs):
    data = {
        "name": name,
        "examiner_mode": EXAMINER_MODE_NONE,
        "validity_value": 1,
        "validity_unit": VALIDITY_UNIT_YEARS,
    }
    data.update(kwargs)
    return data


def _text_question(topic_id: int, text: str, *, correct: str = "B", active: bool = True):
    letters = {
        "A": WrittenAnswerInput(text="odpověď A", is_correct=correct == "A"),
        "B": WrittenAnswerInput(text="odpověď B", is_correct=correct == "B"),
        "C": WrittenAnswerInput(text="odpověď C", is_correct=correct == "C"),
    }
    return written_question_service.create_question(
        topic_id=topic_id,
        text=text,
        answer_kind=ANSWER_KIND_TEXT,
        answers=[letters["A"], letters["B"], letters["C"]],
        active=active,
    )


def _plain(xml: str) -> str:
    text = xml.replace("<text:line-break/>", "\n")
    text = re.sub(r"<text:s\b[^>]*/>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _frames(xml: str) -> list[tuple[float, float, str]]:
    return [
        (float(width), float(height), href)
        for width, height, href in re.findall(
            r'svg:width="([0-9.]+)cm" svg:height="([0-9.]+)cm".{0,240}?xlink:href="([^"]+)"',
            xml,
        )
    ]


class StudyQuestionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.files = Path(tempfile.mkdtemp(prefix="testy-15-src-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.files, ignore_errors=True)

    def test_document_lists_catalog_questions_with_marked_answers(self) -> None:
        fire = written_question_topic_service.create_topic(name="Požár")
        heights = written_question_topic_service.create_topic(name="Výšky")
        hidden_topic = written_question_topic_service.create_topic(name="Vyřazený okruh")
        foreign = written_question_topic_service.create_topic(name="Jiný test")
        alfa = _text_question(fire.id, "Alfa hlásič")
        zeta = _text_question(fire.id, "Zeta hasicí přístroj")
        extra = _text_question(heights.id, "Jištění na střeše")
        hidden = _text_question(fire.id, "Neaktivní otázka", active=False)
        dropped = _text_question(hidden_topic.id, "Otázka vyřazeného okruhu")
        other = _text_question(foreign.id, "Cizí otázka")
        oral_topic = oral_question_topic_service.create_topic(name="Pohovor")
        quiet_topic = oral_question_topic_service.create_topic(name="Tichý okruh")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Ústní alfa postup")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Ústní zeta postup")
        skipped = oral_question_service.create_question(
            topic_id=oral_topic.id,
            text="Ústní neaktivní",
        )
        oral_question_service.deactivate(skipped.id)
        oral_question_service.create_question(topic_id=quiet_topic.id, text="Ústní vyřazená")

        definition = test_definition_service.create_test(
            **_fields(
                "Školení BOZP",
                uses_written=True,
                uses_oral=True,
                allowed_wrong_answers=0,
                written_topics=[
                    TestTopicQuota(fire.id, 1),
                    TestTopicQuota(heights.id, 1),
                    TestTopicQuota(hidden_topic.id, 1),
                ],
                oral_topics=[
                    TestTopicQuota(oral_topic.id, 1),
                    TestTopicQuota(quiet_topic.id, 1),
                ],
            )
        )
        test_definition_service.create_test(
            **_fields(
                "Jiná agenda",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(foreign.id, 1)],
            )
        )
        written_question_topic_service.deactivate(hidden_topic.id)
        oral_question_topic_service.deactivate(quiet_topic.id)
        self.assertEqual(test_definition_service.written_question_count(definition.id), 3)

        target = self.files / "studium.odt"
        written = study_questions_export_service.export(definition.id, target)
        self._assert_valid_odt(written)
        content = _content(written)
        plain = _plain(content)
        self.assertIn(STUDY_QUESTIONS_TITLE, plain)
        self.assertIn("Školení BOZP", plain)
        self.assertIn(STUDY_WRITTEN_HEADING, plain)
        self.assertIn(STUDY_ORAL_HEADING, plain)
        self.assertLess(plain.find("Požár"), plain.find("Alfa hlásič"))
        self.assertLess(plain.find("Alfa hlásič"), plain.find("Zeta hasicí přístroj"))
        self.assertLess(plain.find("Požár"), plain.find("Výšky"))
        self.assertLess(plain.find("Výšky"), plain.find("Jištění na střeše"))
        self.assertLess(plain.find(STUDY_WRITTEN_HEADING), plain.find(STUDY_ORAL_HEADING))
        self.assertIn("Ústní alfa postup", plain)
        self.assertIn("Ústní zeta postup", plain)
        for absent in (
            "Neaktivní otázka",
            "Otázka vyřazeného okruhu",
            "Cizí otázka",
            "Ústní neaktivní",
            "Ústní vyřazená",
            "Vyřazený okruh",
            "Tichý okruh",
            "Zaměstnanec",
            "Osobní číslo",
            "Výsledek zkoušky",
        ):
            self.assertNotIn(absent, plain)
        self.assertEqual(plain.count("Alfa hlásič"), 1)
        self.assertLess(plain.find("odpověď A"), plain.find("odpověď B"))
        self.assertLess(plain.find("odpověď B"), plain.find("odpověď C"))
        self.assertEqual(plain.count("✓ B)"), 3)
        self.assertNotIn("✓ A)", plain)
        self.assertNotIn("✓ C)", plain)
        self.assertEqual(content.count('text:style-name="ProtocolAnswerCorrect"'), 3)
        self.assertIn('fo:font-weight="bold"', content)
        self.assertNotIn("fo:break-before", content)
        self.assertNotIn("fo:break-after", content)
        self.assertIn('text:style-name="WrittenDocumentEnd"', content)
        material = study_questions_export_service.collect(definition.id)
        printed = [
            question.question_id
            for topic in material.written
            for question in topic.questions
        ]
        self.assertCountEqual(printed, [alfa.id, zeta.id, extra.id])
        self.assertNotIn(hidden.id, printed)
        self.assertNotIn(dropped.id, printed)
        self.assertNotIn(other.id, printed)
        stored = test_definition_service.get_test(definition.id)
        self.assertEqual(stored.name, "Školení BOZP")
        self.assertEqual(test_definition_service.written_question_count(definition.id), 3)

    def test_study_sheet_uses_current_catalog_not_exam_snapshot(self) -> None:
        topic = written_question_topic_service.create_topic(name="Aktuální banka")
        first = _text_question(topic.id, "Původní znění otázky")
        second = _text_question(topic.id, "Druhá katalogová otázka")
        third = _text_question(topic.id, "Třetí katalogová otázka")
        definition = test_definition_service.create_test(
            **_fields(
                "Jeden z katalogu",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(topic.id, 1)],
            )
        )
        workplace = settings_service.save_workplace(name="Hala studia")
        role = responsibility_role_service.create_role(name="Mistr studia")
        employee = test_employee_service.create_employee(
            personal_number="15001",
            first_name="Karel",
            last_name="Studna",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=definition.id,
            exam_date=date(2026, 10, 8),
            rng=random.Random(4),
        )
        drawn = test_exam_service.get_written_questions(exam.id)
        self.assertEqual(len(drawn), 1)
        old_snapshot = drawn[0].text
        before = test_exam_service.get_exam(exam.id)
        replacements = {
            first.id: "Nové znění z katalogu",
            second.id: "Nová druhá otázka",
            third.id: "Nová třetí otázka",
        }
        for question_id, text in replacements.items():
            written_question_service.update_question(
                question_id,
                topic_id=topic.id,
                text=text,
                answer_kind=ANSWER_KIND_TEXT,
                answers=[
                    WrittenAnswerInput(text="odpověď A"),
                    WrittenAnswerInput(text="odpověď B", is_correct=True),
                    WrittenAnswerInput(text="odpověď C"),
                ],
            )
        target = self.files / "katalog.odt"
        study_questions_export_service.export(definition.id, target)
        plain = _plain(_content(target))
        for text in replacements.values():
            self.assertIn(text, plain)
        self.assertNotIn(old_snapshot, plain)
        self.assertNotIn("Karel", plain)
        self.assertNotIn("Studna", plain)
        self.assertNotIn(STUDY_ORAL_HEADING, plain)
        snapshot = test_exam_service.get_written_questions(exam.id)
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0].text, old_snapshot)
        after = test_exam_service.get_exam(exam.id)
        self.assertEqual(after.status, before.status)
        self.assertEqual(after.exam_result, before.exam_result)
        self.assertEqual(test_definition_service.written_question_count(definition.id), 1)

    def test_images_keep_aspect_and_mark_the_correct_choice(self) -> None:
        topic = written_question_topic_service.create_topic(name="Značky")
        prompt = _png(self.files / "zadani.png", (20, 40, 80), (800, 400))
        choices = [
            _png(self.files / "a.png", (180, 0, 0), (800, 200)),
            _png(self.files / "b.png", (0, 140, 0), (200, 800)),
            _png(self.files / "c.png", (0, 0, 160), (400, 400)),
        ]
        question = written_question_service.create_question(
            topic_id=topic.id,
            text="Vyberte správnou značku",
            answer_kind=ANSWER_KIND_IMAGE,
            question_image_source_path=str(prompt),
            answers=[
                WrittenAnswerInput(image_source_path=str(choices[0])),
                WrittenAnswerInput(image_source_path=str(choices[1]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(choices[2])),
            ],
        )
        stored_prompt = written_question_service.attachment_path(question.image_attachment_id)
        stored_answers = [
            written_question_service.attachment_path(answer.image_attachment_id)
            for answer in sorted(
                written_question_service.get_answers(question.id),
                key=lambda item: item.position,
            )
        ]
        assert stored_prompt is not None
        assert all(path is not None for path in stored_answers)
        definition = test_definition_service.create_test(
            **_fields(
                "Obrázky",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(topic.id, 1)],
            )
        )
        target = self.files / "obrazky.odt"
        study_questions_export_service.export(definition.id, target)
        content = _content(target)
        plain = _plain(content)
        self.assertIn("✓ B)", plain)
        self.assertNotIn("✓ A)", plain)
        self.assertNotIn("✓ C)", plain)
        self.assertLess(plain.find("A)"), plain.find("✓ B)"))
        self.assertLess(plain.find("✓ B)"), plain.find("C)"))
        frames = _frames(content)
        self.assertEqual(len(frames), 4)
        expected_sizes = []
        for path in (stored_prompt, *stored_answers):
            with Image.open(path) as image:
                expected_sizes.append(image.size)
        for (width, height, _href), (px_w, px_h) in zip(frames, expected_sizes):
            self.assertAlmostEqual(width / height, px_w / px_h, places=2)
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
        with zipfile.ZipFile(target) as archive:
            pictures = [name for name in archive.namelist() if name.startswith("Pictures/")]
            self.assertEqual(len(pictures), 4)
            stored = {archive.read(name) for name in pictures}
        self.assertEqual(
            stored,
            {path.read_bytes() for path in (stored_prompt, *stored_answers)},
        )

    def test_duplicate_catalog_rows_are_printed_once_and_empty_test_is_refused(self) -> None:
        topic = written_question_topic_service.create_topic(name="Jednou")
        _text_question(topic.id, "Jen jedna věta")
        definition = test_definition_service.create_test(
            **_fields(
                "Bez duplicit",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(topic.id, 1)],
            )
        )
        real = written_question_service.list_questions

        def doubled(**kwargs):
            rows = real(**kwargs)
            return list(rows) + list(rows)

        with patch.object(written_question_service, "list_questions", side_effect=doubled):
            material = study_questions_export_service.collect(definition.id)
        self.assertEqual(len(material.written), 1)
        self.assertEqual(len(material.written[0].questions), 1)
        target = self.files / "jednou.odt"
        with patch.object(written_question_service, "list_questions", side_effect=doubled):
            study_questions_export_service.export(definition.id, target)
        self.assertEqual(_plain(_content(target)).count("Jen jedna věta"), 1)

        empty_topic = written_question_topic_service.create_topic(name="Bez aktivních")
        inactive = _text_question(empty_topic.id, "Už není aktivní")
        empty = test_definition_service.create_test(
            **_fields(
                "Prázdný test",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(empty_topic.id, 1)],
            )
        )
        written_question_service.deactivate(inactive.id)
        missing = self.files / "prazdny.odt"
        with self.assertRaises(StudyQuestionsError) as error:
            study_questions_export_service.export(empty.id, missing)
        self.assertEqual(str(error.exception), STUDY_QUESTIONS_EMPTY)
        self.assertFalse(missing.exists())

    def test_button_follows_selection_and_writes_the_document(self) -> None:
        topic = written_question_topic_service.create_topic(name="Tlačítko")
        _text_question(topic.id, "Otázka z tlačítka")
        ready = test_definition_service.create_test(
            **_fields(
                "Připravený test",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(topic.id, 1)],
            )
        )
        empty_topic = written_question_topic_service.create_topic(name="Prázdný okruh")
        inactive = _text_question(empty_topic.id, "Vypnutá otázka")
        empty = test_definition_service.create_test(
            **_fields(
                "Prázdný výběr",
                uses_written=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(empty_topic.id, 1)],
            )
        )
        written_question_service.deactivate(inactive.id)
        tab = TestDefinitionsTab()
        self.assertEqual(tab.study_btn.text(), STUDY_QUESTIONS_ACTION)
        self.assertFalse(tab.study_btn.isEnabled())
        self._select(tab, ready.id)
        self.assertTrue(tab.study_btn.isEnabled())
        self.assertTrue(tab.edit_btn.isEnabled())
        tab.table.clearSelection()
        self.assertFalse(tab.study_btn.isEnabled())

        self._select(tab, ready.id)
        self._select_also(tab, empty.id)
        self.assertFalse(tab.study_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())

        self._select(tab, empty.id)
        with (
            patch("moduly.testy.ui.test_definitions_tab.QFileDialog.getSaveFileName") as save,
            patch("moduly.testy.ui.test_definitions_tab.QMessageBox.warning") as warning,
        ):
            tab.study_btn.click()
        save.assert_not_called()
        warning.assert_called_once()
        self.assertIn(STUDY_QUESTIONS_EMPTY, warning.call_args.args)

        target = self.files / "z-tlacitka.odt"
        self._select(tab, ready.id)
        with (
            patch(
                "moduly.testy.ui.test_definitions_tab.QFileDialog.getSaveFileName",
                return_value=(str(target), "OpenDocument (*.odt)"),
            ),
            patch("moduly.testy.ui.test_definitions_tab.open_export_file") as opener,
            patch("moduly.testy.ui.test_definitions_tab.QMessageBox.warning") as warning,
        ):
            tab.study_btn.click()
        warning.assert_not_called()
        opener.assert_called_once()
        self._assert_valid_odt(target)
        self.assertIn("Otázka z tlačítka", _plain(_content(target)))
        self.assertIn(STUDY_QUESTIONS_TITLE, _plain(_content(target)))
        tab.deleteLater()

    def _select(self, tab: TestDefinitionsTab, test_id: int) -> None:
        tab.refresh()
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, TEST_COL_ID)
            if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == test_id:
                tab.table.selectRow(row)
                return
        self.fail(f"test {test_id} není v tabulce")

    def _select_also(self, tab: TestDefinitionsTab, test_id: int) -> None:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, TEST_COL_ID)
            if item is None or int(item.data(Qt.ItemDataRole.UserRole)) != test_id:
                continue
            tab.table.selectionModel().select(
                tab.table.model().index(row, TEST_COL_NAME),
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            return
        self.fail(f"test {test_id} není v tabulce")

    def _assert_valid_odt(self, path: Path) -> None:
        self.assertTrue(zipfile.is_zipfile(path))
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.namelist()[0], "mimetype")
            self.assertEqual(
                archive.read("mimetype"),
                b"application/vnd.oasis.opendocument.text",
            )
            xml = archive.read("content.xml")
        ET.fromstring(xml)


if __name__ == "__main__":
    unittest.main()
