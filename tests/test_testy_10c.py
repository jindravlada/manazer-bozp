"""TESTY-10c: hromadná příprava papírových testů."""

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
from xml.etree import ElementTree as ET

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-10c-"))
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
        EXAM_ACTION_BATCH_PAPER,
        EXAM_ROLE_CHAIR,
        EXAM_ROLE_EXAMINER,
        EXAM_ROLE_MEMBER,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        PAPER_BATCH_KEY_OPTION,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_PAPER,
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
    from moduly.testy.sluzby.paper_batch_service import (
        format_batch_summary,
        prepare_and_export_paper_batch,
    )
    from moduly.testy.sluzby.paper_test_export_service import (
        assign_batch_key_path,
        paper_test_export_service,
        render_batch_answer_key_xml,
        variant_label,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        TestExamError,
        TestExamService,
        test_exam_service,
    )
    from moduly.testy.sluzby.written_exam_service import written_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.paper_batch_dialog import PaperBatchDialog
    from moduly.testy.ui.test_exams_tab import TestExamsTab

_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


class Alternate:
    """Každé další losování vezme opačný konec banky."""

    def __init__(self) -> None:
        self.calls = 0

    def sample(self, population, k):
        items = list(population)
        self.calls += 1
        if self.calls % 2 == 0:
            items.reverse()
        return items[:k]

    def shuffle(self, items) -> None:
        self.calls += 1
        if self.calls % 2 == 0:
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
        active=kwargs.get("active", True),
    )


def _answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _written_test(name: str, topic_id: int, count: int, **kwargs):
    return test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=kwargs.get("uses_oral", False),
        allowed_wrong_answers=kwargs.get("allowed_wrong_answers", 1),
        seconds_per_question=30,
        examiner_mode=kwargs.get("examiner_mode", EXAMINER_MODE_NONE),
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic_id, count)],
        oral_topics=kwargs.get("oral_topics"),
    )


def _questions(topic_id: int, count: int) -> None:
    for index in range(count):
        written_question_service.create_question(
            topic_id=topic_id,
            text=f"Otázka {index}",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_answers(),
        )


def _exam_count() -> int:
    return len(test_exam_service.list_exams())


def _letters(exam_id: int) -> list[str]:
    letters = []
    for question in test_exam_service.get_written_questions(exam_id):
        found = ""
        for answer in test_exam_service.get_written_answers(question.id):
            if answer.is_correct:
                found = answer.letter
                break
        letters.append(found)
    return letters


def _odt_part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def _plain(xml: str) -> str:
    text = xml.replace("<text:line-break/>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _batch_sections(xml: str) -> list[tuple[str, list[tuple[list[str], list[str]]]]]:
    root = ET.fromstring(xml)
    sections = []
    for node in root.iter(f"{_TABLE}table"):
        if node.attrib.get(f"{_TABLE}style-name") != "WrittenKeyBatch":
            continue
        cell = node.find(f"{_TABLE}table-row/{_TABLE}table-cell")
        heading = ""
        grids = []
        if cell is None:
            sections.append((heading, grids))
            continue
        for child in list(cell):
            if child.tag == f"{_TEXT}p" and not heading:
                heading = "".join(child.itertext()).strip()
            if child.tag != f"{_TABLE}table":
                continue
            rows = []
            for row in child.findall(f"{_TABLE}table-row"):
                rows.append(
                    [
                        "".join(item.itertext()).strip()
                        for item in row.findall(f"{_TABLE}table-cell")
                    ]
                )
            if len(rows) >= 2:
                grids.append((rows[0], rows[1]))
        sections.append((heading, grids))
    return sections


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


class PaperBatchTestCase(unittest.TestCase):
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
        self.folder = _TMP / "vystup" / self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def test_employee_picker_filters_without_clearing_checks(self) -> None:
        active_a = _employee("201", "Jan", "Novak", workplace="Hala")
        active_b = _employee("202", "Petr", "Svoboda", workplace="Dílna")
        inactive = _employee("203", "Karel", "Maly", active=False, workplace="Hala")
        oral_topic = oral_question_topic_service.create_topic(name="Jen ústní okruh")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Řekněte postup")
        topic = written_question_topic_service.create_topic(name="Písemný okruh")
        _questions(topic.id, 3)
        written = _written_test("Písemný", topic.id, 2)
        test_definition_service.create_test(
            name="Jen ústní",
            uses_written=False,
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        test_definition_service.create_test(
            name="Neaktivní písemný",
            active=False,
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
        )
        dialog = PaperBatchDialog()
        self.addCleanup(dialog.close)
        numbers = [
            dialog.employees.item(row, 1).text()
            for row in range(dialog.employees.rowCount())
        ]
        self.assertIn(active_a.personal_number, numbers)
        self.assertIn(active_b.personal_number, numbers)
        self.assertNotIn(inactive.personal_number, numbers)
        offered = [dialog.test.itemText(index) for index in range(dialog.test.count())]
        self.assertIn(written.name, offered)
        self.assertNotIn("Jen ústní", offered)
        self.assertNotIn("Neaktivní písemný", offered)
        self.assertFalse(dialog.shared_key.isChecked())
        self.assertEqual(dialog.shared_key.text(), PAPER_BATCH_KEY_OPTION)

        self._set_checked(dialog, "201", True)
        self._set_checked(dialog, "202", True)
        dialog.search.setText("Svoboda")
        self.assertTrue(self._row_hidden(dialog, "201"))
        self.assertFalse(self._row_hidden(dialog, "202"))
        self.assertEqual(dialog.selected_employee_ids(), [active_a.id, active_b.id])
        dialog.search.clear()
        dialog.workplace.setCurrentIndex(self._workplace_index(dialog, "Hala"))
        self.assertFalse(self._row_hidden(dialog, "201"))
        self.assertTrue(self._row_hidden(dialog, "202"))
        dialog.select_visible_btn.click()
        dialog.clear_visible_btn.click()
        self.assertNotIn(active_a.id, dialog.selected_employee_ids())
        self.assertIn(active_b.id, dialog.selected_employee_ids())
        dialog.workplace.setCurrentIndex(0)
        dialog.select_visible_btn.click()
        self.assertCountEqual(dialog.selected_employee_ids(), [active_a.id, active_b.id])

        tab = TestExamsTab()
        self.addCleanup(tab.close)
        button = tab.findChild(QPushButton, "exam-batch-paper-button")
        self.assertIsNotNone(button)
        self.assertEqual(button.text(), EXAM_ACTION_BATCH_PAPER)
        self.assertTrue(button.isEnabled())
        tab._update_action_buttons()
        self.assertTrue(button.isEnabled())

    def test_each_employee_gets_an_independent_exam_and_files(self) -> None:
        first = _employee("301", "Jan", "Novak", workplace="Hala")
        second = _employee("302", "Petr", "Svoboda", workplace="Dílna")
        topic = written_question_topic_service.create_topic(name="Dávka")
        _questions(topic.id, 4)
        oral_topic = oral_question_topic_service.create_topic(name="Ústní dávka")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Popište postup")
        definition = _written_test(
            "Společný test",
            topic.id,
            3,
            uses_oral=True,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        result = prepare_and_export_paper_batch(
            employee_ids=[first.id, second.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            valid_until=date(2028, 1, 15),
            directory=self.folder,
            include_shared_key=False,
            rng=Alternate(),
        )
        self.assertEqual(len(result.exams), 2)
        self.assertEqual(len(result.files.test_paths), 2)
        self.assertIsNone(result.files.key_path)
        self.assertFalse(result.files.failures)
        self.assertEqual(list(self.folder.glob("Klic_*.odt")), [])
        ids = [int(exam.id) for exam in result.exams]
        self.assertEqual(len(set(ids)), 2)
        snapshots = []
        for exam in result.exams:
            self.assertEqual(exam.exam_date, _EXAM_DAY)
            self.assertEqual(exam.valid_until, date(2028, 1, 15))
            self.assertEqual(exam.test_name, "Společný test")
            questions = test_exam_service.get_written_questions(exam.id)
            self.assertTrue(questions)
            self.assertTrue(all(int(question.exam_id) == int(exam.id) for question in questions))
            self.assertTrue(test_exam_service.get_oral_questions(exam.id))
            snapshots.append({int(question.source_question_id) for question in questions})
        self.assertNotEqual(snapshots[0], snapshots[1])
        for exam, path in zip(result.exams, result.files.test_paths, strict=True):
            self.assertEqual(path.parent, self.folder)
            self.assertIn(variant_label(exam), _plain(_odt_part(path, "content.xml")))
            self.assertIn(exam.employee_last_name, _plain(_odt_part(path, "content.xml")))

    def test_name_collision_uses_personal_number_and_keeps_existing_file(self) -> None:
        first = _employee("401", "Jan", "Novak")
        second = _employee("402", "Jan", "Novak")
        topic = written_question_topic_service.create_topic(name="Kolize")
        _questions(topic.id, 3)
        definition = _written_test("Kolize jmen", topic.id, 2)
        placeholder = self.folder / "Test_Jan_Novak_2026-10-07.odt"
        placeholder.write_bytes(b"stare")
        result = prepare_and_export_paper_batch(
            employee_ids=[first.id, second.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            directory=self.folder,
            include_shared_key=False,
            rng=Alternate(),
        )
        self.assertEqual(placeholder.read_bytes(), b"stare")
        names = sorted(path.name for path in result.files.test_paths)
        self.assertEqual(
            names,
            [
                "Test_Jan_Novak_2026-10-07_401.odt",
                "Test_Jan_Novak_2026-10-07_402.odt",
            ],
        )
        self.assertTrue(all(path.is_file() and path.stat().st_size > len(b"stare") for path in result.files.test_paths))

    def test_examiner_rules_and_conflict_reject_the_whole_batch(self) -> None:
        examinee = _employee("501", "Jana", "Malá")
        other = _employee("502", "Eva", "Krátká")
        examiner = _employee("801", "Adam", "Zkoušející", may_examine=True)
        chair = _employee("802", "Iva", "Předsedkyně", may_examine=True)
        member = _employee("803", "Otto", "Člen", may_examine=True)
        topic = written_question_topic_service.create_topic(name="Režim")
        _questions(topic.id, 3)
        single = _written_test("Jeden", topic.id, 2, examiner_mode=EXAMINER_MODE_SINGLE)
        commission = _written_test("Komise", topic.id, 2, examiner_mode=EXAMINER_MODE_COMMISSION)
        plain = _written_test("Bez", topic.id, 2, examiner_mode=EXAMINER_MODE_NONE)

        created = prepare_and_export_paper_batch(
            employee_ids=[examinee.id],
            test_id=single.id,
            exam_date=_EXAM_DAY,
            directory=self.folder,
            examiner_id=examiner.id,
            rng=Alternate(),
        )
        people = test_exam_service.get_examiners(created.exams[0].id)
        self.assertEqual([(person.role, person.employee_id) for person in people], [(EXAM_ROLE_EXAMINER, examiner.id)])

        before = _exam_count()
        with self.assertRaises(TestExamError) as conflict:
            prepare_and_export_paper_batch(
                employee_ids=[examiner.id, other.id],
                test_id=single.id,
                exam_date=_EXAM_DAY,
                directory=self.folder,
                examiner_id=examiner.id,
                rng=Alternate(),
            )
        self.assertIn("Adam", str(conflict.exception))
        self.assertIn("801", str(conflict.exception))
        self.assertIn("Nevytvořila se žádná zkouška.", str(conflict.exception))
        self.assertEqual(_exam_count(), before)

        with self.assertRaises(TestExamError) as commission_conflict:
            prepare_and_export_paper_batch(
                employee_ids=[member.id, other.id],
                test_id=commission.id,
                exam_date=_EXAM_DAY,
                directory=self.folder,
                chair_id=chair.id,
                member_ids=[member.id],
                rng=Alternate(),
            )
        self.assertIn("Otto", str(commission_conflict.exception))
        self.assertEqual(_exam_count(), before)

        commission_dir = self.folder / "komise"
        commission_dir.mkdir()
        commission_ok = prepare_and_export_paper_batch(
            employee_ids=[examinee.id],
            test_id=commission.id,
            exam_date=_EXAM_DAY,
            directory=commission_dir,
            chair_id=chair.id,
            member_ids=[member.id],
            rng=Alternate(),
        )
        roles = [(person.role, person.employee_id) for person in test_exam_service.get_examiners(commission_ok.exams[0].id)]
        self.assertEqual(roles, [(EXAM_ROLE_CHAIR, chair.id), (EXAM_ROLE_MEMBER, member.id)])

        plain_dir = self.folder / "bez"
        plain_dir.mkdir()
        none_ok = prepare_and_export_paper_batch(
            employee_ids=[examinee.id],
            test_id=plain.id,
            exam_date=_EXAM_DAY,
            directory=plain_dir,
            rng=Alternate(),
        )
        self.assertEqual(test_exam_service.get_examiners(none_ok.exams[0].id), [])

    def test_validation_error_writes_nothing(self) -> None:
        active = _employee("601", "Lea", "Aktivní")
        inactive = _employee("602", "Ivo", "Neaktivní", active=False)
        topic = written_question_topic_service.create_topic(name="Málo")
        _questions(topic.id, 2)
        definition = _written_test("Málo otázek", topic.id, 2)
        before = _exam_count()
        with self.assertRaises(TestExamError) as inactive_error:
            test_exam_service.prepare_paper_batch(
                employee_ids=[active.id, inactive.id],
                test_id=definition.id,
                exam_date=_EXAM_DAY,
            )
        self.assertIn("Ivo", str(inactive_error.exception))
        self.assertIn("Nevytvořila se žádná zkouška.", str(inactive_error.exception))
        self.assertEqual(_exam_count(), before)

        questions = written_question_service.list_questions(topic_id=topic.id)
        written_question_service.deactivate(questions[0].id)
        with self.assertRaises(TestExamError) as missing:
            test_exam_service.prepare_paper_batch(
                employee_ids=[active.id],
                test_id=definition.id,
                exam_date=_EXAM_DAY,
            )
        self.assertIn("Nevytvořila se žádná zkouška.", str(missing.exception))
        self.assertEqual(_exam_count(), before)

        written_question_service.set_active(questions[0].id, active=True)
        original = TestExamService._insert_prepared_exam
        state = {"n": 0}

        def fail_second(self, *args, **kwargs):
            state["n"] += 1
            if state["n"] == 2:
                raise TestExamError("druhý zápis selhal")
            return original(self, *args, **kwargs)

        other = _employee("603", "Nela", "Druhá")
        with patch.object(TestExamService, "_insert_prepared_exam", fail_second):
            with self.assertRaises(TestExamError):
                test_exam_service.prepare_paper_batch(
                    employee_ids=[active.id, other.id],
                    test_id=definition.id,
                    exam_date=_EXAM_DAY,
                    rng=Alternate(),
                )
        self.assertEqual(_exam_count(), before)

    def test_shared_key_matches_each_snapshot_and_splits_blocks(self) -> None:
        exam = SimpleNamespace(
            id=77,
            employee_first_name="Jan",
            employee_last_name="Novak",
            employee_title_before="",
            employee_title_after="",
            employee_personal_number="42",
        )
        thirty = [(index, "ABC"[(index - 1) % 3]) for index in range(1, 31)]
        fifty = [(index, "B") for index in range(1, 51)]
        thirty_xml = render_batch_answer_key_xml([(exam, thirty)])
        fifty_xml = render_batch_answer_key_xml([(exam, fifty)])
        self.assertEqual(thirty_xml.count('table:number-columns-repeated="15"'), 2)
        self.assertEqual(thirty_xml.count("<table:table "), 3)
        self.assertEqual(fifty_xml.count('table:number-columns-repeated="15"'), 3)
        self.assertIn('table:number-columns-repeated="5"', fifty_xml)
        self.assertIn("WrittenKeyBatchRow", thirty_xml)
        self.assertNotIn('fo:break-before="page"', thirty_xml)
        self.assertIn("Varianta 77", thirty_xml)
        self.assertIn("Jan Novak", thirty_xml)
        self.assertIn("– 42", thirty_xml)

        first = _employee("701", "Jan", "Novak", workplace="Hala klíčů")
        second = _employee("702", "Petr", "Svoboda", workplace="Dílna klíčů")
        topic = written_question_topic_service.create_topic(name="Klíč dávky")
        _questions(topic.id, 4)
        definition = _written_test("Test ke společnému klíči", topic.id, 3)
        result = prepare_and_export_paper_batch(
            employee_ids=[first.id, second.id],
            test_id=definition.id,
            exam_date=_EXAM_DAY,
            directory=self.folder,
            include_shared_key=True,
            rng=Alternate(),
        )
        fingerprints = {
            int(exam.id): _letters(exam.id)
            for exam in result.exams
        }
        repeat_dir = self.folder / "znovu"
        repeat_dir.mkdir()
        patches = _forbid_redraw()
        for item in patches:
            item.start()
        try:
            again = paper_test_export_service.export_batch(
                [int(exam.id) for exam in result.exams],
                repeat_dir,
                include_shared_key=True,
            )
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(
            {int(exam.id): _letters(exam.id) for exam in result.exams},
            fingerprints,
        )
        self.assertIsNotNone(result.files.key_path)
        self.assertEqual(result.files.key_path.name, "Klic_testu_2026-10-07.odt")
        self.assertEqual(
            [path.name for path in self.folder.glob("Klic_*.odt")],
            ["Klic_testu_2026-10-07.odt"],
        )
        key_xml = _odt_part(result.files.key_path, "content.xml")
        plain = _plain(key_xml)
        self.assertIn("Klíč správných odpovědí", plain)
        self.assertIn("Test ke společnému klíči", plain)
        self.assertIn("Datum zkoušky", plain)
        self.assertNotIn("Hala klíčů", plain)
        self.assertNotIn("Dílna klíčů", plain)
        self.assertNotIn("Pracoviště", plain)
        sections = _batch_sections(key_xml)
        self.assertEqual(len(sections), 2)
        for exam, (heading, grids) in zip(result.exams, sections, strict=True):
            self.assertIn(variant_label(exam), heading)
            self.assertIn(exam.employee_first_name, heading)
            self.assertIn(exam.employee_last_name, heading)
            self.assertIn(exam.employee_personal_number, heading)
            self.assertEqual(len(grids), 1)
            numbers, letters = grids[0]
            questions = test_exam_service.get_written_questions(exam.id)
            self.assertEqual(numbers, [str(question.position) for question in questions])
            self.assertEqual(letters, _letters(exam.id))
            self.assertLessEqual(len(numbers), 15)
        self.assertIn('fo:keep-together="always"', key_xml)
        self.assertNotIn('fo:break-before="page"', key_xml)
        self.assertEqual(
            assign_batch_key_path(self.folder, _EXAM_DAY).name,
            "Klic_testu_2026-10-07_2.odt",
        )
        self.assertEqual(len(again.test_paths), 2)
        self.assertIsNotNone(again.key_path)

    def test_failed_odt_keeps_exams_and_paper_entry_still_works(self) -> None:
        first = _employee("901", "Jana", "První")
        second = _employee("902", "Karel", "Druhý")
        topic = written_question_topic_service.create_topic(name="Selhání souboru")
        _questions(topic.id, 3)
        definition = _written_test("Po selhání", topic.id, 2)
        original = paper_test_export_service.export
        calls = {"n": 0}

        def flaky(exam_id, test_path, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise TestExamError("Soubor se nepodařilo zapsat.")
            return original(exam_id, test_path, **kwargs)

        paper_test_export_service.export = flaky
        try:
            result = prepare_and_export_paper_batch(
                employee_ids=[first.id, second.id],
                test_id=definition.id,
                exam_date=_EXAM_DAY,
                directory=self.folder,
                include_shared_key=False,
                rng=Alternate(),
            )
        finally:
            paper_test_export_service.export = original

        self.assertEqual(len(result.exams), 2)
        self.assertEqual(_exam_count(), 2)
        self.assertEqual(len(result.files.test_paths), 1)
        self.assertEqual(len(result.files.failures), 1)
        self.assertIn("Karel", result.files.failures[0].employee_label)
        self.assertIn("902", result.files.failures[0].employee_label)
        summary = format_batch_summary(result)
        self.assertIn("Vytvořeno zkoušek: 2", summary)
        self.assertIn("Vytvořeno testů: 1", summary)
        self.assertIn("Společný klíč: nevytvářen", summary)
        self.assertIn("Karel", summary)
        saved = result.exams[0]
        self.assertTrue(written_exam_service.can_enter_paper(saved.id))
        question = test_exam_service.get_written_questions(saved.id)[0]
        written_exam_service.save_paper_letter(saved.id, question.id, "B")
        stored = test_exam_service.get_exam(saved.id)
        self.assertEqual(stored.written_mode, WRITTEN_MODE_PAPER)
        choice = test_exam_service.get_written_choices(saved.id)[0]
        self.assertEqual(choice.selected_letter, "B")

    def _set_checked(self, dialog: PaperBatchDialog, number: str, checked: bool) -> None:
        row = self._row(dialog, number)
        dialog.employees.item(row, 0).setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )

    def _row(self, dialog: PaperBatchDialog, number: str) -> int:
        for row in range(dialog.employees.rowCount()):
            item = dialog.employees.item(row, 1)
            if item is not None and item.text() == number:
                return row
        raise AssertionError(number)

    def _row_hidden(self, dialog: PaperBatchDialog, number: str) -> bool:
        return dialog.employees.isRowHidden(self._row(dialog, number))

    def _workplace_index(self, dialog: PaperBatchDialog, name: str) -> int:
        for index in range(dialog.workplace.count()):
            if dialog.workplace.itemText(index) == name:
                return index
        raise AssertionError(name)
