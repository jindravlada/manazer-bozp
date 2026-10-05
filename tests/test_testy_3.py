"""TESTY-3: okruhy písemných otázek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication, QDialog, QLabel
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-3-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        AGENDA_EMPLOYEES,
        AGENDA_ORAL_QUESTIONS,
        AGENDA_ORAL_TOPICS,
        AGENDA_QUESTIONS,
        AGENDA_WRITTEN_TOPICS,
        COL_FIRST_NAME,
        COL_PERSONAL_NUMBER,
        MODULE_NAME,
        PAGE_SUBTITLE,
        STATUS_ACTIVE_LABEL,
        STATUS_INACTIVE_LABEL,
        TOPIC_ACTION_NEW,
        TOPIC_COL_NAME,
        TOPIC_COL_STATUS,
        TOPIC_COLUMN_HEADERS,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.written_question_topic_service import (
        WrittenQuestionTopicError,
        written_question_topic_service,
    )
    from moduly.testy.ui.testy_page import TestyPage
    from moduly.testy.ui.written_question_topic_dialog import WrittenQuestionTopicDialog


def _count_topics() -> int:
    with get_session() as session:
        return int(
            session.scalar(select(func.count()).select_from(WrittenQuestionTopic)) or 0
        )


class WrittenQuestionTopicTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.commit()
        self.page = TestyPage()
        self.topics = self.page.topics_tab

    def tearDown(self) -> None:
        self.page.close()

    def test_create_active_topic(self) -> None:
        self.assertIn("name", _table_columns("test_written_question_topics"))
        topic = written_question_topic_service.create_topic(
            name="  BOZP  ",
            description="  ochrana\npracovníků  ",
        )
        self.assertEqual(topic.name, "BOZP")
        self.assertEqual(topic.description, "ochrana\npracovníků")
        self.assertTrue(topic.active)

        loaded = written_question_topic_service.get_topic(topic.id)
        assert loaded is not None
        self.assertEqual(loaded.name, "BOZP")
        self.assertTrue(loaded.active)
        self.assertIsNotNone(loaded.created_at)
        self.assertIsNotNone(loaded.updated_at)

    def test_empty_and_duplicate_name(self) -> None:
        with self.assertRaises(WrittenQuestionTopicError) as empty:
            written_question_topic_service.create_topic(name="   ")
        self.assertIn("název", str(empty.exception).casefold())
        self.assertEqual(_count_topics(), 0)

        written_question_topic_service.create_topic(name="BOZP")
        with self.assertRaises(WrittenQuestionTopicError) as duplicate:
            written_question_topic_service.create_topic(name="bozp")
        self.assertIn("již existuje", str(duplicate.exception))
        self.assertEqual(_count_topics(), 1)

        dialog = WrittenQuestionTopicDialog(self.page)
        self.assertTrue(dialog.active_checkbox.isChecked())
        dialog.name.setText(" ")
        with patch(
            "moduly.testy.ui.written_question_topic_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("název", str(warning.call_args[0][2]).casefold())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

        dialog.name.setText("BOZP")
        with patch(
            "moduly.testy.ui.written_question_topic_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("již existuje", str(warning.call_args[0][2]))
        self.assertEqual(_count_topics(), 1)
        dialog.close()

    def test_update_name_and_description(self) -> None:
        topic = written_question_topic_service.create_topic(
            name="BOZP",
            description="původní",
        )
        updated = written_question_topic_service.update_topic(
            topic.id,
            name="BOZP provoz",
            description="nový popis",
            active=True,
        )
        self.assertEqual(updated.name, "BOZP provoz")
        self.assertEqual(updated.description, "nový popis")
        loaded = written_question_topic_service.get_topic(topic.id)
        assert loaded is not None
        self.assertEqual(loaded.description, "nový popis")

    def test_deactivate_keeps_row_and_list_filter(self) -> None:
        active = written_question_topic_service.create_topic(
            name="BOZP",
            description="helmy a školení",
        )
        written_question_topic_service.create_topic(
            name="OOPP",
            description="rukavice",
        )
        deactivated = written_question_topic_service.deactivate(active.id)
        self.assertFalse(deactivated.active)
        self.assertEqual(_count_topics(), 2)
        self.assertIsNotNone(written_question_topic_service.get_topic(active.id))

        self.topics.refresh()
        self.assertEqual(self.topics.table.rowCount(), 1)
        self.assertEqual(self.topics.table.item(0, TOPIC_COL_NAME).text(), "OOPP")
        self.assertEqual(
            self.topics.table.item(0, TOPIC_COL_STATUS).text(),
            STATUS_ACTIVE_LABEL,
        )

        self.topics.show_inactive.setChecked(True)
        self.assertEqual(self.topics.table.rowCount(), 2)
        statuses = {
            self.topics.table.item(row, TOPIC_COL_NAME).text(): self.topics.table.item(
                row, TOPIC_COL_STATUS
            ).text()
            for row in range(self.topics.table.rowCount())
        }
        self.assertEqual(statuses["BOZP"], STATUS_INACTIVE_LABEL)
        self.assertEqual(statuses["OOPP"], STATUS_ACTIVE_LABEL)

        self.topics.text_filter.search_edit.setText("helmy")
        hidden = {
            self.topics.table.item(row, TOPIC_COL_NAME).text(): self.topics.table.isRowHidden(row)
            for row in range(self.topics.table.rowCount())
        }
        self.assertFalse(hidden["BOZP"])
        self.assertTrue(hidden["OOPP"])

    def test_edit_button_and_double_click(self) -> None:
        self.assertEqual(
            [
                self.topics.table.horizontalHeaderItem(column).text()
                for column in range(self.topics.table.columnCount())
            ],
            TOPIC_COLUMN_HEADERS,
        )
        self.assertEqual(self.topics.new_btn.text(), TOPIC_ACTION_NEW)
        self.assertTrue(self.topics.new_btn.isEnabled())
        self.assertFalse(self.topics.edit_btn.isEnabled())
        self.assertFalse(self.topics.show_inactive.isChecked())

        topic = written_question_topic_service.create_topic(name="BOZP", description="starý")
        written_question_topic_service.create_topic(name="OOPP")
        self.topics.refresh()

        self.topics.table.clearSelection()
        self.assertFalse(self.topics.edit_btn.isEnabled())
        self.topics.table.selectRow(0)
        self.assertTrue(self.topics.edit_btn.isEnabled())
        self.topics.table.selectionModel().select(
            self.topics.table.model().index(1, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.assertFalse(self.topics.edit_btn.isEnabled())

        self.topics.table.selectRow(0)
        selected_name = self.topics.table.item(0, TOPIC_COL_NAME).text()

        class _Edit(WrittenQuestionTopicDialog):
            def exec(self):  # noqa: A003
                self.name.setText(f"{selected_name} upraveno")
                self.description.setPlainText("nový popis")
                self.accept()
                return int(QDialog.DialogCode.Accepted)

        with patch(
            "moduly.testy.ui.written_question_topics_tab.WrittenQuestionTopicDialog",
            _Edit,
        ):
            self.topics.table.doubleClicked.emit(self.topics.table.model().index(0, 1))

        loaded = written_question_topic_service.get_topic(topic.id)
        assert loaded is not None
        if selected_name == "BOZP":
            self.assertEqual(loaded.name, "BOZP upraveno")
            self.assertEqual(loaded.description, "nový popis")
        else:
            other = written_question_topic_service.list_topics(include_inactive=True)
            names = {item.name for item in other}
            self.assertIn("OOPP upraveno", names)

    def test_switch_agendas_keeps_employees(self) -> None:
        labels = {label.objectName(): label.text() for label in self.page.findChildren(QLabel)}
        self.assertEqual(labels.get("PageTitle"), MODULE_NAME)
        self.assertEqual(labels.get("InfoText"), PAGE_SUBTITLE)
        self.assertEqual(self.page.tabs.count(), 5)
        self.assertEqual(self.page.tabs.tabText(0), AGENDA_EMPLOYEES)
        self.assertEqual(self.page.tabs.tabText(1), AGENDA_WRITTEN_TOPICS)
        self.assertEqual(self.page.tabs.tabText(2), AGENDA_QUESTIONS)
        self.assertEqual(self.page.tabs.tabText(3), AGENDA_ORAL_TOPICS)
        self.assertEqual(self.page.tabs.tabText(4), AGENDA_ORAL_QUESTIONS)

        workplace = settings_service.save_workplace(name="Provoz 3")
        role = responsibility_role_service.create_role(name="Mistr 3")
        test_employee_service.create_employee(
            personal_number="00300",
            first_name="Eva",
            last_name="Malá",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        self.page.refresh()
        self.assertEqual(self.page.table.item(0, COL_PERSONAL_NUMBER).text(), "00300")

        self.page.tabs.setCurrentWidget(self.topics)
        written_question_topic_service.create_topic(name="BOZP")
        self.topics.refresh()
        self.assertEqual(self.topics.table.rowCount(), 1)

        self.page.tabs.setCurrentWidget(self.page.employees_tab)
        self.assertEqual(self.page.tabs.tabText(self.page.tabs.currentIndex()), AGENDA_EMPLOYEES)
        self.assertEqual(self.page.table.rowCount(), 1)
        self.assertEqual(self.page.table.item(0, COL_PERSONAL_NUMBER).text(), "00300")
        self.assertEqual(self.page.table.item(0, COL_FIRST_NAME).text(), "Eva")
        self.assertTrue(self.page.new_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
