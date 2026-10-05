"""TESTY-5: ústní okruhy a ústní otázky."""

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

_TMP = Path(tempfile.mkdtemp(prefix="testy-5-"))

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
        AGENDA_ORAL_QUESTIONS,
        AGENDA_ORAL_TOPICS,
        AGENDA_QUESTIONS,
        AGENDA_WRITTEN_TOPICS,
        ORAL_QUESTION_COL_STATUS,
        ORAL_QUESTION_COL_TEXT,
        ORAL_QUESTION_COL_TOPIC,
        STATUS_ACTIVE_LABEL,
        STATUS_INACTIVE_LABEL,
        TOPIC_COL_DESCRIPTION,
        TOPIC_COL_NAME,
        TOPIC_COL_STATUS,
    )
    from moduly.testy.modely.oral_question import OralQuestion
    from moduly.testy.modely.oral_question_topic import OralQuestionTopic
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import (
        OralQuestionError,
        oral_question_service,
    )
    from moduly.testy.sluzby.oral_question_topic_service import (
        OralQuestionTopicError,
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.oral_question_dialog import OralQuestionDialog
    from moduly.testy.ui.oral_question_topic_dialog import OralQuestionTopicDialog
    from moduly.testy.ui.testy_page import TestyPage


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


class OralTopicsAndQuestionsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(OralQuestion))
            session.execute(delete(OralQuestionTopic))
            session.execute(delete(WrittenQuestionTopic))
            session.commit()
        self.page = TestyPage()
        self.topics = self.page.oral_topics_tab
        self.questions = self.page.oral_questions_tab

    def tearDown(self) -> None:
        self.page.close()

    def test_create_empty_duplicate_and_separate_from_written(self) -> None:
        self.assertIn("name", _table_columns("test_oral_question_topics"))
        self.assertIn("topic_id", _table_columns("test_oral_questions"))
        written_question_topic_service.create_topic(name="BOZP")
        topic = oral_question_topic_service.create_topic(
            name="  BOZP  ",
            description="  ústní\nčást  ",
        )
        self.assertEqual(topic.name, "BOZP")
        self.assertEqual(topic.description, "ústní\nčást")
        self.assertTrue(topic.active)
        self.assertIsNotNone(topic.created_at)
        self.assertIsNotNone(topic.updated_at)
        self.assertEqual(_count(WrittenQuestionTopic), 1)
        self.assertEqual(_count(OralQuestionTopic), 1)

        with self.assertRaises(OralQuestionTopicError) as empty:
            oral_question_topic_service.create_topic(name="   ")
        self.assertIn("název", str(empty.exception).casefold())

        with self.assertRaises(OralQuestionTopicError) as duplicate:
            oral_question_topic_service.create_topic(name="bozp")
        self.assertIn("již existuje", str(duplicate.exception))
        self.assertEqual(_count(OralQuestionTopic), 1)

        dialog = OralQuestionTopicDialog(self.page)
        self.assertTrue(dialog.active_checkbox.isChecked())
        dialog.name.setText(" ")
        with patch(
            "moduly.testy.ui.oral_question_topic_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("název", str(warning.call_args[0][2]).casefold())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.close()

    def test_update_deactivate_and_list(self) -> None:
        topic = oral_question_topic_service.create_topic(
            name="BOZP",
            description="původní",
        )
        updated = oral_question_topic_service.update_topic(
            topic.id,
            name="BOZP provoz",
            description="nový\npopis",
            active=True,
        )
        self.assertEqual(updated.name, "BOZP provoz")
        self.assertEqual(updated.description, "nový\npopis")

        oral_question_topic_service.create_topic(name="OOPP", description="rukavice")
        deactivated = oral_question_topic_service.deactivate(updated.id)
        self.assertFalse(deactivated.active)
        self.assertEqual(_count(OralQuestionTopic), 2)
        self.assertIsNotNone(oral_question_topic_service.get_topic(updated.id))

        self.topics.refresh()
        self.assertEqual(self.topics.table.rowCount(), 1)
        self.assertEqual(self.topics.table.item(0, TOPIC_COL_NAME).text(), "OOPP")
        self.assertEqual(
            self.topics.table.item(0, TOPIC_COL_STATUS).text(),
            STATUS_ACTIVE_LABEL,
        )

        self.topics.show_inactive.setChecked(True)
        self.assertEqual(self.topics.table.rowCount(), 2)
        self.topics.text_filter.search_edit.setText("provoz")
        visible_rows = [
            row
            for row in range(self.topics.table.rowCount())
            if not self.topics.table.isRowHidden(row)
        ]
        self.assertEqual(visible_rows, [0])
        self.assertEqual(self.topics.table.item(0, TOPIC_COL_NAME).text(), "BOZP provoz")
        self.assertEqual(
            self.topics.table.item(0, TOPIC_COL_STATUS).text(),
            STATUS_INACTIVE_LABEL,
        )
        self.assertIn("nový", self.topics.table.item(0, TOPIC_COL_DESCRIPTION).text())
        self.assertFalse(self.topics.edit_btn.isEnabled())
        self.topics.table.selectRow(0)
        self.assertTrue(self.topics.edit_btn.isEnabled())

    def test_question_requires_text_and_active_oral_topic(self) -> None:
        written = written_question_topic_service.create_topic(name="BOZP")
        inactive = oral_question_topic_service.create_topic(name="Vyřazený")
        oral_question_topic_service.deactivate(inactive.id)
        active = oral_question_topic_service.create_topic(name="BOZP")

        with self.assertRaises(OralQuestionError) as missing_topic:
            oral_question_service.create_question(topic_id=None, text="Co je riziko?")
        self.assertIn("okruh", str(missing_topic.exception).casefold())

        missing_topic_id = max(written.id, inactive.id, active.id) + 100
        with self.assertRaises(OralQuestionError) as foreign:
            oral_question_service.create_question(
                topic_id=missing_topic_id,
                text="Co je riziko?",
            )
        self.assertIn("neexistuje", str(foreign.exception))

        with self.assertRaises(OralQuestionError) as inactive_topic:
            oral_question_service.create_question(topic_id=inactive.id, text="Co je riziko?")
        self.assertIn("aktivních", str(inactive_topic.exception))

        with self.assertRaises(OralQuestionError) as empty:
            oral_question_service.create_question(topic_id=active.id, text="  ")
        self.assertIn("text otázky", str(empty.exception).casefold())
        self.assertEqual(_count(OralQuestion), 0)

        question = oral_question_service.create_question(
            topic_id=active.id,
            text="  Co je\nriziko?  ",
            note="  jen pro komisi  ",
        )
        self.assertEqual(question.topic_id, active.id)
        self.assertEqual(question.text, "Co je\nriziko?")
        self.assertEqual(question.note, "jen pro komisi")
        self.assertTrue(question.active)
        self.assertIsNotNone(question.created_at)

        dialog = OralQuestionDialog(self.page)
        dialog.topic.setCurrentIndex(dialog.topic.findData(active.id))
        dialog.question_text.setPlainText("   ")
        with patch(
            "moduly.testy.ui.oral_question_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("text otázky", str(warning.call_args[0][2]).casefold())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.close()

    def test_inactive_topic_stays_and_question_filter(self) -> None:
        topic = oral_question_topic_service.create_topic(name="BOZP")
        other = oral_question_topic_service.create_topic(name="OOPP")
        question = oral_question_service.create_question(
            topic_id=topic.id,
            text="Historická otázka",
        )
        oral_question_topic_service.deactivate(topic.id)
        kept = oral_question_service.update_question(
            question.id,
            topic_id=topic.id,
            text="Historická otázka",
            note="poznámka",
            active=True,
        )
        self.assertEqual(kept.topic_id, topic.id)

        edit = OralQuestionDialog(question=kept)
        try:
            self.assertIn("(neaktivní)", edit.topic.currentText())
            self.assertEqual(edit._topic_id(), topic.id)
        finally:
            edit.close()

        fresh = OralQuestionDialog()
        try:
            self.assertLess(fresh.topic.findData(topic.id), 0)
            self.assertGreaterEqual(fresh.topic.findData(other.id), 0)
        finally:
            fresh.close()

        with self.assertRaises(OralQuestionError):
            oral_question_service.create_question(
                topic_id=topic.id,
                text="Nová na neaktivní",
            )

        oral_question_service.create_question(topic_id=other.id, text="Aktivní otázka")
        self.questions.refresh()
        self.assertEqual(self.questions.table.rowCount(), 2)
        index = self.questions.topic_filter.findData(topic.id)
        self.assertGreaterEqual(index, 0)
        self.assertIn("(neaktivní)", self.questions.topic_filter.itemText(index))
        self.questions.topic_filter.setCurrentIndex(index)
        self.assertEqual(self.questions.table.rowCount(), 1)
        self.assertEqual(
            self.questions.table.item(0, ORAL_QUESTION_COL_TEXT).text(),
            "Historická otázka",
        )
        self.assertEqual(
            self.questions.table.item(0, ORAL_QUESTION_COL_TOPIC).text(),
            "BOZP (neaktivní)",
        )

        oral_question_service.deactivate(kept.id)
        self.assertEqual(_count(OralQuestion), 2)
        self.questions.refresh()
        self.assertEqual(self.questions.table.rowCount(), 0)
        self.questions.show_inactive.setChecked(True)
        self.assertEqual(self.questions.table.rowCount(), 1)
        self.assertEqual(
            self.questions.table.item(0, ORAL_QUESTION_COL_STATUS).text(),
            STATUS_INACTIVE_LABEL,
        )
        self.assertFalse(self.questions.edit_btn.isEnabled())
        self.questions.table.selectRow(0)
        self.assertTrue(self.questions.edit_btn.isEnabled())

    def test_agendas_order(self) -> None:
        self.assertEqual(self.page.tabs.count(), 5)
        self.assertEqual(self.page.tabs.tabText(0), AGENDA_EMPLOYEES)
        self.assertEqual(self.page.tabs.tabText(1), AGENDA_WRITTEN_TOPICS)
        self.assertEqual(self.page.tabs.tabText(2), AGENDA_QUESTIONS)
        self.assertEqual(self.page.tabs.tabText(3), AGENDA_ORAL_TOPICS)
        self.assertEqual(self.page.tabs.tabText(4), AGENDA_ORAL_QUESTIONS)
        self.assertEqual(self.topics.new_btn.text(), "Nový okruh")
        self.assertEqual(self.questions.new_btn.text(), "Nová otázka")


if __name__ == "__main__":
    unittest.main()
