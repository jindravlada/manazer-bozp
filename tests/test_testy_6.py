"""TESTY-6: definice Testů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-6-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.testy.constants import (
        AGENDA_EMPLOYEES,
        AGENDA_EXAM_VALIDITY,
        AGENDA_EXAMS,
        AGENDA_ORAL_QUESTIONS,
        AGENDA_ORAL_TOPICS,
        AGENDA_QUESTIONS,
        AGENDA_TESTS,
        AGENDA_WRITTEN_TOPICS,
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_COMMISSION,
        EXAMINER_MODE_NONE,
        EXAMINER_MODE_SINGLE,
        PART_NO_LABEL,
        PART_YES_LABEL,
        STATUS_INACTIVE_LABEL,
        TEST_COL_NAME,
        TEST_COL_ORAL,
        TEST_COL_QUESTION_COUNT,
        TEST_COL_STATUS,
        TEST_COL_VALIDITY,
        TEST_COL_WRITTEN,
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
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.test_definition_service import (
        TestDefinitionError,
        TestTopicQuota,
        format_test_duration,
        format_validity,
        test_definition_service,
        total_written_questions,
        total_written_seconds,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_definition_dialog import TestDefinitionDialog
    from moduly.testy.ui.testy_page import TestyPage


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="ano", is_correct=True),
        WrittenAnswerInput(text="ne"),
        WrittenAnswerInput(text="nevím"),
    ]


def _written_topic(name: str, questions: int):
    topic = written_question_topic_service.create_topic(name=name)
    for index in range(questions):
        written_question_service.create_question(
            topic_id=topic.id,
            text=f"{name} {index}",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_answers(),
        )
    return topic


def _oral_topic(name: str, questions: int):
    topic = oral_question_topic_service.create_topic(name=name)
    for index in range(questions):
        oral_question_service.create_question(
            topic_id=topic.id,
            text=f"{name} ústní {index}",
        )
    return topic


def _fields(**overrides):
    data = {
        "name": "Periodické školení",
        "description": "",
        "active": True,
        "uses_written": False,
        "allowed_wrong_answers": 0,
        "seconds_per_question": 30,
        "uses_oral": False,
        "examiner_mode": EXAMINER_MODE_NONE,
        "validity_value": 2,
        "validity_unit": VALIDITY_UNIT_YEARS,
        "written_topics": [],
        "oral_topics": [],
    }
    data.update(overrides)
    return data


class TestDefinitionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(TestDefinitionWrittenTopic))
            session.execute(delete(TestDefinitionOralTopic))
            session.execute(delete(TestDefinition))
            session.execute(delete(WrittenQuestionAnswer))
            session.execute(delete(WrittenQuestion))
            session.execute(delete(OralQuestion))
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(OralQuestionTopic))
            session.commit()
        self.page = TestyPage()
        self.tests = self.page.tests_tab

    def tearDown(self) -> None:
        self.page.close()

    def test_written_composition_count_and_duration(self) -> None:
        self.assertIn("name", _table_columns("test_definitions"))
        self.assertIn("question_count", _table_columns("test_definition_written_topics"))
        general = _written_topic("Obecná BOZP", 10)
        ppe = _written_topic("OOPP", 5)
        created = test_definition_service.create_test(
            **_fields(
                name="  Písemný test  ",
                description="  jen písemně  ",
                uses_written=True,
                allowed_wrong_answers=3,
                written_topics=[
                    TestTopicQuota(general.id, 10),
                    TestTopicQuota(ppe.id, 5),
                ],
            )
        )
        self.assertEqual(created.name, "Písemný test")
        self.assertEqual(created.description, "jen písemně")
        self.assertTrue(created.uses_written)
        self.assertFalse(created.uses_oral)
        self.assertEqual(created.allowed_wrong_answers, 3)
        self.assertEqual(created.seconds_per_question, 30)
        self.assertIsNotNone(created.created_at)
        self.assertIsNotNone(created.updated_at)

        lines = test_definition_service.get_written_topics(created.id)
        self.assertEqual([(line.topic_id, line.question_count) for line in lines], [
            (general.id, 10),
            (ppe.id, 5),
        ])
        self.assertEqual(test_definition_service.get_oral_topics(created.id), [])
        self.assertEqual(test_definition_service.written_question_count(created.id), 15)
        self.assertEqual(test_definition_service.written_duration_seconds(created.id), 450)
        self.assertEqual(total_written_questions([
            TestTopicQuota(1, 10),
            TestTopicQuota(2, 5),
            TestTopicQuota(3, 5),
            TestTopicQuota(4, 10),
        ]), 30)
        self.assertEqual(total_written_seconds(30, 30), 900)
        self.assertEqual(format_test_duration(900), "15 min")
        self.assertEqual(format_test_duration(450), "7 min 30 s")

        replaced = test_definition_service.update_test(
            created.id,
            **_fields(
                name="Písemný test",
                uses_written=True,
                allowed_wrong_answers=1,
                written_topics=[TestTopicQuota(ppe.id, 5)],
            ),
        )
        self.assertEqual(test_definition_service.written_question_count(replaced.id), 5)
        self.assertEqual(len(test_definition_service.get_written_topics(replaced.id)), 1)

        dialog = TestDefinitionDialog()
        dialog.written_group.setChecked(True)
        dialog.seconds.setValue(30)
        dialog.written_composition.set_rows([
            (1, "Obecná BOZP", 10),
            (2, "OOPP", 5),
            (3, "Požární ochrana", 5),
            (4, "Řidiči", 10),
        ])
        self.assertEqual(dialog.total_questions_label.text(), "Celkem otázek: 30")
        self.assertEqual(dialog.duration_label.text(), "Čas testu: 15 min")
        dialog.seconds.setValue(20)
        self.assertEqual(dialog.duration_label.text(), "Čas testu: 10 min")
        dialog.written_group.setChecked(False)
        self.assertEqual(dialog.total_questions_label.text(), "Celkem otázek: 0")
        self.assertEqual(dialog.duration_label.text(), "Čas testu: 0 min")
        dialog.close()

    def test_oral_only_and_both_parts(self) -> None:
        self.assertIn("question_count", _table_columns("test_definition_oral_topics"))
        first = _oral_topic("První pomoc", 2)
        second = _oral_topic("Požár", 2)
        oral_only = test_definition_service.create_test(
            **_fields(
                name="Ústní zkouška",
                uses_oral=True,
                oral_topics=[
                    TestTopicQuota(first.id, 1),
                    TestTopicQuota(second.id, 2),
                ],
            )
        )
        self.assertFalse(oral_only.uses_written)
        self.assertTrue(oral_only.uses_oral)
        self.assertEqual(test_definition_service.written_question_count(oral_only.id), 0)
        oral_lines = test_definition_service.get_oral_topics(oral_only.id)
        self.assertEqual(
            [(line.topic_id, line.question_count) for line in oral_lines],
            [(first.id, 1), (second.id, 2)],
        )

        written = _written_topic("BOZP", 3)
        both = test_definition_service.create_test(
            **_fields(
                name="Kombinovaný",
                uses_written=True,
                uses_oral=True,
                allowed_wrong_answers=1,
                written_topics=[TestTopicQuota(written.id, 2)],
                oral_topics=[TestTopicQuota(first.id, 1)],
            )
        )
        self.assertTrue(both.uses_written)
        self.assertTrue(both.uses_oral)
        self.assertEqual(test_definition_service.written_question_count(both.id), 2)
        self.assertEqual(len(test_definition_service.get_oral_topics(both.id)), 1)

    def test_validation_rules(self) -> None:
        topic = _written_topic("BOZP", 3)
        oral = _oral_topic("Ústní", 2)

        with self.assertRaises(TestDefinitionError) as empty_name:
            test_definition_service.create_test(**_fields(name="   ", uses_written=True))
        self.assertIn("název", str(empty_name.exception).casefold())

        test_definition_service.create_test(
            **_fields(
                name="BOZP",
                uses_written=True,
                written_topics=[TestTopicQuota(topic.id, 1)],
            )
        )
        with self.assertRaises(TestDefinitionError) as duplicate_name:
            test_definition_service.create_test(
                **_fields(
                    name="bozp",
                    uses_written=True,
                    written_topics=[TestTopicQuota(topic.id, 1)],
                )
            )
        self.assertIn("již existuje", str(duplicate_name.exception))

        with self.assertRaises(TestDefinitionError) as neither:
            test_definition_service.create_test(**_fields(name="Prázdný"))
        self.assertIn("písemnou nebo ústní", str(neither.exception))

        with self.assertRaises(TestDefinitionError) as no_written:
            test_definition_service.create_test(
                **_fields(name="Bez okruhu", uses_written=True)
            )
        self.assertIn("alespoň jeden okruh", str(no_written.exception))

        with self.assertRaises(TestDefinitionError) as no_oral:
            test_definition_service.create_test(
                **_fields(name="Bez ústního", uses_oral=True)
            )
        self.assertIn("alespoň jeden okruh", str(no_oral.exception))

        with self.assertRaises(TestDefinitionError) as duplicate_topic:
            test_definition_service.create_test(
                **_fields(
                    name="Duplicita",
                    uses_written=True,
                    written_topics=[
                        TestTopicQuota(topic.id, 1),
                        TestTopicQuota(topic.id, 1),
                    ],
                )
            )
        self.assertIn("vícekrát", str(duplicate_topic.exception))

        with self.assertRaises(TestDefinitionError) as duplicate_oral:
            test_definition_service.create_test(
                **_fields(
                    name="Duplicita ústní",
                    uses_oral=True,
                    oral_topics=[
                        TestTopicQuota(oral.id, 1),
                        TestTopicQuota(oral.id, 1),
                    ],
                )
            )
        self.assertIn("vícekrát", str(duplicate_oral.exception))

        with self.assertRaises(TestDefinitionError) as zero_count:
            test_definition_service.create_test(
                **_fields(
                    name="Nula",
                    uses_written=True,
                    written_topics=[TestTopicQuota(topic.id, 0)],
                )
            )
        self.assertIn("větší než 0", str(zero_count.exception))

        with self.assertRaises(TestDefinitionError) as seconds:
            test_definition_service.create_test(
                **_fields(
                    name="Bez času",
                    uses_written=True,
                    seconds_per_question=0,
                    written_topics=[TestTopicQuota(topic.id, 1)],
                )
            )
        self.assertIn("otázku", str(seconds.exception).casefold())

        with self.assertRaises(TestDefinitionError) as validity:
            test_definition_service.create_test(
                **_fields(
                    name="Bez platnosti",
                    uses_written=True,
                    validity_value=0,
                    written_topics=[TestTopicQuota(topic.id, 1)],
                )
            )
        self.assertIn("platnosti", str(validity.exception).casefold())

        dialog = TestDefinitionDialog(self.page)
        dialog.name.setText("Prázdný dialog")
        with patch(
            "moduly.testy.ui.test_definition_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("písemnou nebo ústní", str(warning.call_args[0][2]))
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.close()

    def test_available_questions_and_inactive_topic(self) -> None:
        topic = _written_topic("OOPP", 3)
        other = _written_topic("Řidiči", 2)
        with self.assertRaises(TestDefinitionError) as shortage:
            test_definition_service.create_test(
                **_fields(
                    name="Málo otázek",
                    uses_written=True,
                    written_topics=[TestTopicQuota(topic.id, 5)],
                )
            )
        self.assertIn("OOPP", str(shortage.exception))
        self.assertIn("3", str(shortage.exception))
        self.assertIn("5", str(shortage.exception))
        self.assertEqual(_count(TestDefinition), 0)

        questions = written_question_service.list_questions(topic_id=topic.id)
        written_question_service.deactivate(questions[0].id)
        created = test_definition_service.create_test(
            **_fields(
                name="Dostatečný",
                uses_written=True,
                written_topics=[TestTopicQuota(topic.id, 2)],
            )
        )
        written_question_service.deactivate(questions[1].id)
        self.assertEqual(test_definition_service.written_question_count(created.id), 2)
        self.assertEqual(
            test_definition_service.get_written_topics(created.id)[0].question_count,
            2,
        )
        with self.assertRaises(TestDefinitionError):
            test_definition_service.update_test(
                created.id,
                **_fields(
                    name="Dostatečný",
                    uses_written=True,
                    written_topics=[TestTopicQuota(topic.id, 2)],
                ),
            )
        self.assertEqual(
            test_definition_service.get_written_topics(created.id)[0].question_count,
            2,
        )

        oral = _oral_topic("Ústní OOPP", 1)
        with self.assertRaises(TestDefinitionError) as oral_shortage:
            test_definition_service.create_test(
                **_fields(
                    name="Málo ústních",
                    uses_oral=True,
                    oral_topics=[TestTopicQuota(oral.id, 2)],
                )
            )
        self.assertIn("Ústní okruh", str(oral_shortage.exception))

        written_question_topic_service.deactivate(topic.id)
        kept = test_definition_service.update_test(
            created.id,
            **_fields(
                name="Dostatečný",
                uses_written=True,
                written_topics=[TestTopicQuota(topic.id, 2)],
            ),
        )
        self.assertEqual(kept.id, created.id)
        self.assertEqual(
            test_definition_service.get_written_topics(kept.id)[0].topic_id,
            topic.id,
        )
        with self.assertRaises(TestDefinitionError) as inactive_new:
            test_definition_service.create_test(
                **_fields(
                    name="Nový na neaktivní",
                    uses_written=True,
                    written_topics=[TestTopicQuota(topic.id, 1)],
                )
            )
        self.assertIn("aktivní okruh", str(inactive_new.exception))

        edit = TestDefinitionDialog(test=kept)
        fresh = TestDefinitionDialog()
        try:
            self.assertIn("(neaktivní)", " ".join(edit.written_composition.topic_labels()))
            self.assertLess(fresh.written_composition.topic_combo.findData(topic.id), 0)
            self.assertGreaterEqual(
                fresh.written_composition.topic_combo.findData(other.id),
                0,
            )
        finally:
            edit.close()
            fresh.close()

    def test_errors_examiner_mode_and_validity(self) -> None:
        topic = _written_topic("BOZP", 4)
        with self.assertRaises(TestDefinitionError) as negative:
            test_definition_service.create_test(
                **_fields(
                    uses_written=True,
                    allowed_wrong_answers=-1,
                    written_topics=[TestTopicQuota(topic.id, 4)],
                )
            )
        self.assertIn("záporný", str(negative.exception))

        with self.assertRaises(TestDefinitionError) as too_many:
            test_definition_service.create_test(
                **_fields(
                    name="Moc chyb",
                    uses_written=True,
                    allowed_wrong_answers=4,
                    written_topics=[TestTopicQuota(topic.id, 4)],
                )
            )
        self.assertIn("menší", str(too_many.exception))

        created = test_definition_service.create_test(
            **_fields(
                name="Tři chyby",
                uses_written=True,
                allowed_wrong_answers=3,
                examiner_mode=EXAMINER_MODE_SINGLE,
                validity_value=18,
                validity_unit=VALIDITY_UNIT_MONTHS,
                written_topics=[TestTopicQuota(topic.id, 4)],
            )
        )
        self.assertEqual(created.allowed_wrong_answers, 3)
        self.assertEqual(created.examiner_mode, EXAMINER_MODE_SINGLE)
        self.assertEqual(created.validity_value, 18)
        self.assertEqual(created.validity_unit, VALIDITY_UNIT_MONTHS)
        self.assertEqual(format_validity(18, VALIDITY_UNIT_MONTHS), "18 měsíců")
        self.assertNotEqual(created.validity_value, 18 * 30)

        single = test_definition_service.update_test(
            created.id,
            **_fields(
                name="Tři chyby",
                uses_written=True,
                allowed_wrong_answers=3,
                examiner_mode=EXAMINER_MODE_NONE,
                validity_value=2,
                validity_unit=VALIDITY_UNIT_YEARS,
                written_topics=[TestTopicQuota(topic.id, 4)],
            ),
        )
        self.assertEqual(single.examiner_mode, EXAMINER_MODE_NONE)
        commission = test_definition_service.update_test(
            created.id,
            **_fields(
                name="Tři chyby",
                uses_written=True,
                allowed_wrong_answers=3,
                examiner_mode=EXAMINER_MODE_COMMISSION,
                validity_value=2,
                validity_unit=VALIDITY_UNIT_YEARS,
                written_topics=[TestTopicQuota(topic.id, 4)],
            ),
        )
        self.assertEqual(commission.examiner_mode, EXAMINER_MODE_COMMISSION)
        self.assertEqual(commission.validity_value, 2)
        self.assertEqual(commission.validity_unit, VALIDITY_UNIT_YEARS)
        self.assertEqual(format_validity(2, VALIDITY_UNIT_YEARS), "2 roky")
        self.assertEqual(format_validity(1, VALIDITY_UNIT_YEARS), "1 rok")
        self.assertEqual(format_validity(5, VALIDITY_UNIT_YEARS), "5 let")
        self.assertEqual(format_validity(1, VALIDITY_UNIT_MONTHS), "1 měsíc")
        self.assertEqual(format_validity(3, VALIDITY_UNIT_MONTHS), "3 měsíce")
        self.assertNotEqual(commission.validity_value, 730)

        dialog = TestDefinitionDialog(test=commission)
        try:
            self.assertTrue(dialog.mode_commission.isChecked())
            self.assertEqual(dialog.validity_value.value(), 2)
            self.assertEqual(dialog.validity_unit.currentData(), VALIDITY_UNIT_YEARS)
        finally:
            dialog.close()

    def test_active_flag_list_and_search(self) -> None:
        topic = _written_topic("BOZP", 2)
        oral = _oral_topic("Pohovor", 1)
        active = test_definition_service.create_test(
            **_fields(
                name="Aktivní test",
                description="veřejný popis",
                uses_written=True,
                uses_oral=True,
                allowed_wrong_answers=0,
                written_topics=[TestTopicQuota(topic.id, 2)],
                oral_topics=[TestTopicQuota(oral.id, 1)],
            )
        )
        hidden = test_definition_service.create_test(
            **_fields(
                name="Archiv",
                description="tajná poznámka",
                uses_oral=True,
                validity_value=6,
                validity_unit=VALIDITY_UNIT_MONTHS,
                oral_topics=[TestTopicQuota(oral.id, 1)],
            )
        )
        test_definition_service.deactivate(hidden.id)
        self.assertEqual(_count(TestDefinition), 2)
        self.assertIsNotNone(test_definition_service.get_test(hidden.id))
        self.assertFalse(test_definition_service.get_test(hidden.id).active)

        self.tests.refresh()
        self.assertEqual(self.tests.table.rowCount(), 1)
        self.assertEqual(self.tests.table.item(0, TEST_COL_NAME).text(), "Aktivní test")
        self.assertEqual(self.tests.table.item(0, TEST_COL_WRITTEN).text(), PART_YES_LABEL)
        self.assertEqual(self.tests.table.item(0, TEST_COL_ORAL).text(), PART_YES_LABEL)
        self.assertEqual(self.tests.table.item(0, TEST_COL_QUESTION_COUNT).text(), "2")
        self.assertEqual(self.tests.table.item(0, TEST_COL_VALIDITY).text(), "2 roky")

        self.tests.show_inactive.setChecked(True)
        self.assertEqual(self.tests.table.rowCount(), 2)
        self.tests.text_filter.search_edit.setText("tajná")
        visible = [
            row
            for row in range(self.tests.table.rowCount())
            if not self.tests.table.isRowHidden(row)
        ]
        self.assertEqual(len(visible), 1)
        shown = self.tests.table.item(visible[0], TEST_COL_NAME).text()
        self.assertEqual(shown, "Archiv")
        self.assertEqual(
            self.tests.table.item(visible[0], TEST_COL_WRITTEN).text(),
            PART_NO_LABEL,
        )
        self.assertEqual(
            self.tests.table.item(visible[0], TEST_COL_QUESTION_COUNT).text(),
            "0",
        )
        self.assertEqual(
            self.tests.table.item(visible[0], TEST_COL_VALIDITY).text(),
            "6 měsíců",
        )
        self.assertEqual(
            self.tests.table.item(visible[0], TEST_COL_STATUS).text(),
            STATUS_INACTIVE_LABEL,
        )
        self.assertFalse(self.tests.edit_btn.isEnabled())
        self.tests.table.selectRow(visible[0])
        self.assertTrue(self.tests.edit_btn.isEnabled())
        self.assertEqual(self.page.tabs.count(), 8)
        self.assertEqual(self.page.tabs.tabText(0), AGENDA_EMPLOYEES)
        self.assertEqual(self.page.tabs.tabText(1), AGENDA_WRITTEN_TOPICS)
        self.assertEqual(self.page.tabs.tabText(2), AGENDA_QUESTIONS)
        self.assertEqual(self.page.tabs.tabText(3), AGENDA_ORAL_TOPICS)
        self.assertEqual(self.page.tabs.tabText(4), AGENDA_ORAL_QUESTIONS)
        self.assertEqual(self.page.tabs.tabText(5), AGENDA_TESTS)
        self.assertEqual(self.page.tabs.tabText(6), AGENDA_EXAMS)
        self.assertEqual(self.page.tabs.tabText(7), AGENDA_EXAM_VALIDITY)
        self.assertEqual(self.tests.new_btn.text(), "Nový test")
        self.assertEqual(active.id, test_definition_service.get_test(active.id).id)


if __name__ == "__main__":
    unittest.main()
