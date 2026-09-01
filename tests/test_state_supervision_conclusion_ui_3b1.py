"""STATE-SUPERVISION-CONCLUSION-UI-3B1: závěr a uzavření kontroly."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTextEdit,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-conclusion-ui-3b1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EditorDialogController
    from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
    from core.widgets.search_combo_box import SearchComboBox
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        CLOSED_AT_REQUIRED_MESSAGE,
        CLOSED_BEFORE_ENDED_MESSAGE,
        COL_ENDED,
        COL_RESULT,
        COL_STATUS,
        GROUP_COMPLETION_CLOSE,
        GROUP_OBJECTIONS,
        GROUP_PROTOCOL,
        GROUP_RESULT,
        OBJECTIONS_BEFORE_PROTOCOL_MESSAGE,
        RESULT_SUGGESTIONS,
        STATUS_ANNOUNCED,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
        state_supervision_timeline_item_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab
    from moduly.statni_dozor.ui.state_supervision_table import format_supervision_date


def _count(table: str) -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


_CZECH_SUMMARY = (
    "Kontrola zjistila nedostatky v evidenci OOPP.\n"
    "Nutné doplnit školení obsluhy."
)


class StateSupervisionConclusionUi3b1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _tab_titles(self, dialog: StateSupervisionEditorDialog) -> list[str]:
        return [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]

    def _conclusion_page(self, dialog: StateSupervisionEditorDialog):
        scroll = dialog.tabs.widget(3)
        self.assertIsInstance(scroll, QScrollArea)
        return scroll.widget()

    def test_01_four_tabs_four_sections_and_scroll(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(
            self._tab_titles(dialog),
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertEqual(dialog.tabs.count(), 5)
        page = self._conclusion_page(dialog)
        groups = [box.title() for box in page.findChildren(QGroupBox)]
        self.assertEqual(
            groups,
            [GROUP_RESULT, GROUP_PROTOCOL, GROUP_OBJECTIONS, GROUP_COMPLETION_CLOSE],
        )
        self.assertEqual(len(page.findChildren(QTableWidget)), 0)
        self.assertEqual([btn.text() for btn in page.findChildren(QPushButton)], [])
        self.assertIsInstance(dialog.result_combo, SearchComboBox)
        self.assertTrue(dialog.result_combo.isEditable())
        combo_values = [
            dialog.result_combo.itemText(index)
            for index in range(dialog.result_combo.count())
            if dialog.result_combo.itemText(index)
        ]
        self.assertEqual(tuple(combo_values), RESULT_SUGGESTIONS)
        self.assertIsInstance(dialog.final_summary_edit, QTextEdit)
        self.assertFalse(dialog.final_summary_edit.acceptRichText())
        self.assertGreaterEqual(dialog.final_summary_edit.minimumHeight(), 90)
        self.assertIsInstance(dialog.protocol_number_edit, type(dialog.file_number_edit))
        datetime_fields = (
            dialog.protocol_received_at_edit,
            dialog.objections_due_at_edit,
            dialog.objections_submitted_at_edit,
            dialog.completion_evidence_sent_at_edit,
            dialog.authority_confirmation_at_edit,
            dialog.closed_at_edit,
        )
        for widget in datetime_fields:
            self.assertIsInstance(widget, NullableDateTimeEdit)
            self.assertIsNone(widget.get_datetime())
        self.assertIsInstance(dialog.objections_note_edit, QTextEdit)
        self.assertLessEqual(dialog.minimumWidth(), 1600)
        self.assertLessEqual(dialog.minimumHeight(), 900)
        scroll = dialog.tabs.widget(3)
        self.assertIsInstance(scroll, QScrollArea)
        self.assertTrue(scroll.widgetResizable())
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("wrap_in_scroll_area(self._build_conclusion_tab())", source)
        self.assertIn("LABEL_RESULT", source)
        self.assertIn("LABEL_FINAL_SUMMARY", source)
        self.assertIn("LABEL_PROTOCOL_NUMBER", source)
        self.assertIn("LABEL_CLOSED_AT", source)
        self.assertNotIn("PKZ", source)
        dialog.close()

    def test_02_custom_result_and_load_existing_clean(self) -> None:
        stamp = datetime(2026, 4, 1, 10, 15, 0)
        record = self._create(
            file_number="ČJ/2026/9",
            result="Vlastní přesnější výsledek",
            final_summary=_CZECH_SUMMARY,
            protocol_number="P-12/2026",
            protocol_received_at=stamp,
            objections_due_at=datetime(2026, 4, 15, 10, 0, 0),
            objections_submitted_at=datetime(2026, 4, 16, 8, 30, 0),
            objections_note="Námitky k bodu 3.",
            completion_evidence_sent_at=datetime(2026, 5, 2, 9, 0, 0),
            authority_confirmation_at=datetime(2026, 5, 10, 11, 0, 0),
            closed_at=datetime(2026, 5, 20, 12, 0, 0),
        )
        before = _count("state_supervisions")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(_count("state_supervisions"), before)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertIsInstance(dialog._editor, EditorDialogController)
        self.assertEqual(dialog.file_number_edit.text(), "ČJ/2026/9")
        self.assertEqual(dialog.result_combo.currentText(), "Vlastní přesnější výsledek")
        self.assertEqual(dialog.final_summary_edit.toPlainText(), _CZECH_SUMMARY)
        self.assertEqual(dialog.protocol_number_edit.text(), "P-12/2026")
        self.assertEqual(dialog.protocol_received_at_edit.get_datetime(), stamp)
        self.assertEqual(
            dialog.objections_due_at_edit.get_datetime(),
            datetime(2026, 4, 15, 10, 0, 0),
        )
        self.assertEqual(
            dialog.objections_submitted_at_edit.get_datetime(),
            datetime(2026, 4, 16, 8, 30, 0),
        )
        self.assertEqual(dialog.objections_note_edit.toPlainText(), "Námitky k bodu 3.")
        self.assertEqual(
            dialog.closed_at_edit.get_datetime(),
            datetime(2026, 5, 20, 12, 0, 0),
        )
        dialog.close()

    def test_03_dirty_each_field_revert_tab_and_combo_open(self) -> None:
        record = self._create(result="Bez zjištěných nedostatků")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.tabs.setCurrentIndex(3)
        dialog.tabs.setCurrentIndex(0)
        dialog.tabs.setCurrentIndex(3)
        dialog.result_combo.showPopup()
        dialog.result_combo.hidePopup()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        changes = [
            (lambda: dialog.result_combo.setCurrentText("Zjištěny nedostatky"),
             lambda: dialog.result_combo.setCurrentText("Bez zjištěných nedostatků")),
            (lambda: dialog.final_summary_edit.setPlainText("Shrnutí"),
             lambda: dialog.final_summary_edit.setPlainText("")),
            (lambda: dialog.protocol_number_edit.setText("P-1"),
             lambda: dialog.protocol_number_edit.setText("")),
            (lambda: dialog.protocol_received_at_edit.set_datetime(
                datetime(2026, 6, 1, 10, 0, 0)
            ),
             lambda: dialog.protocol_received_at_edit.clear()),
            (lambda: dialog.objections_due_at_edit.set_datetime(
                datetime(2026, 6, 10, 10, 0, 0)
            ),
             lambda: dialog.objections_due_at_edit.clear()),
            (lambda: dialog.objections_submitted_at_edit.set_datetime(
                datetime(2026, 6, 11, 8, 0, 0)
            ),
             lambda: dialog.objections_submitted_at_edit.clear()),
            (lambda: dialog.objections_note_edit.setPlainText("Poznámka"),
             lambda: dialog.objections_note_edit.setPlainText("")),
            (lambda: dialog.completion_evidence_sent_at_edit.set_datetime(
                datetime(2026, 7, 1, 9, 0, 0)
            ),
             lambda: dialog.completion_evidence_sent_at_edit.clear()),
            (lambda: dialog.authority_confirmation_at_edit.set_datetime(
                datetime(2026, 7, 8, 11, 0, 0)
            ),
             lambda: dialog.authority_confirmation_at_edit.clear()),
            (lambda: dialog.closed_at_edit.set_datetime(
                datetime(2026, 7, 15, 12, 0, 0)
            ),
             lambda: dialog.closed_at_edit.clear()),
        ]
        for change, revert in changes:
            change()
            self.assertTrue(dialog._editor.is_dirty())
            self.assertTrue(dialog._editor.save_button.isEnabled())
            revert()
            self.assertFalse(dialog._editor.is_dirty(), msg=str(dialog.get_snapshot()))
            self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_04_create_update_clear_and_second_save(self) -> None:
        before = _count("state_supervisions")
        protocol = datetime(2026, 4, 1, 10, 0, 0)
        due = datetime(2026, 4, 15, 10, 0, 0)
        submitted = datetime(2026, 4, 20, 8, 0, 0)
        past = datetime(2020, 1, 2, 7, 30, 0)
        future = datetime(2099, 12, 31, 16, 45, 0)
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"KHS {self.marker}")
        dialog.file_number_edit.setText("ČJ/2026/1")
        dialog.result_combo.setCurrentText("Zjištěny nedostatky")
        dialog.final_summary_edit.setPlainText(_CZECH_SUMMARY)
        dialog.protocol_number_edit.setText("P-99/2026")
        dialog.protocol_received_at_edit.set_datetime(protocol)
        dialog.objections_due_at_edit.set_datetime(due)
        dialog.objections_submitted_at_edit.set_datetime(submitted)
        dialog.objections_note_edit.setPlainText("Námitky po lhůtě, historicky pravdivé.")
        dialog.completion_evidence_sent_at_edit.set_datetime(past)
        dialog.authority_confirmation_at_edit.set_datetime(future)
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("state_supervisions"), before + 1)
        first_id = dialog.supervision_id
        loaded = state_supervision_service.get_supervision(first_id)
        self.assertEqual(loaded.file_number, "ČJ/2026/1")
        self.assertEqual(loaded.result, "Zjištěny nedostatky")
        self.assertEqual(loaded.final_summary, _CZECH_SUMMARY)
        self.assertEqual(loaded.protocol_number, "P-99/2026")
        self.assertEqual(loaded.protocol_received_at, protocol)
        self.assertEqual(loaded.objections_due_at, due)
        self.assertEqual(loaded.objections_submitted_at, submitted)
        self.assertEqual(loaded.completion_evidence_sent_at, past)
        self.assertEqual(loaded.authority_confirmation_at, future)
        self.assertFalse(dialog._editor.is_dirty())

        dialog.result_combo.setCurrentText("Uložena opatření")
        dialog.final_summary_edit.setPlainText("Upravené shrnutí")
        self.assertTrue(self._save(dialog))
        self.assertEqual(dialog.supervision_id, first_id)
        self.assertEqual(_count("state_supervisions"), before + 1)
        updated = state_supervision_service.get_supervision(first_id)
        self.assertEqual(updated.result, "Uložena opatření")
        self.assertEqual(updated.final_summary, "Upravené shrnutí")

        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("state_supervisions"), before + 1)

        dialog.result_combo.setCurrentText("")
        dialog.final_summary_edit.setPlainText("   ")
        dialog.protocol_number_edit.setText("")
        dialog.objections_note_edit.clear()
        dialog.protocol_received_at_edit.clear()
        self.assertTrue(self._save(dialog))
        cleared = state_supervision_service.get_supervision(first_id)
        self.assertIsNone(cleared.result)
        self.assertIsNone(cleared.final_summary)
        self.assertIsNone(cleared.protocol_number)
        self.assertIsNone(cleared.objections_note)
        self.assertIsNone(cleared.protocol_received_at)
        self.assertEqual(cleared.file_number, "ČJ/2026/1")
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=first_id)
        self.assertEqual(reopened.result_combo.currentText(), "")
        self.assertEqual(reopened.protocol_number_edit.text(), "")
        self.assertEqual(reopened.file_number_edit.text(), "ČJ/2026/1")
        self.assertIsNone(reopened.protocol_received_at_edit.get_datetime())
        reopened.close()

    def test_05_result_visible_in_overview(self) -> None:
        ended = datetime(2026, 3, 10, 15, 0, 0)
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        dialog.ended_at_edit.set_datetime(ended)
        dialog.result_combo.setCurrentText("Bez zjištěných nedostatků")
        self.assertTrue(self._save(dialog))
        supervision_id = dialog.supervision_id
        dialog.close()

        page = AgendaPage()
        page.tabs.setCurrentIndex(1)
        tab = page.state_supervision_tab
        tab.text_filter.search_edit.setText(self.marker)
        found = None
        for row in range(tab.table.rowCount()):
            if tab.table.item(row, COL_STATUS).data(Qt.ItemDataRole.UserRole) == supervision_id:
                found = row
                break
        self.assertIsNotNone(found)
        self.assertEqual(
            tab.table.item(found, COL_RESULT).text(),
            "Bez zjištěných nedostatků",
        )
        self.assertEqual(
            tab.table.item(found, COL_ENDED).text(),
            format_supervision_date(ended),
        )
        page.close()

    def test_06_closed_requires_closed_at_and_focuses_tab(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(STATUS_CLOSED))
        dialog.result_combo.setCurrentText("Jiný výsledek")
        before = _count("state_supervisions")
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self._save(dialog))
            warning.assert_called()
            self.assertIn(CLOSED_AT_REQUIRED_MESSAGE, warning.call_args.args)
        self.assertEqual(dialog.tabs.currentIndex(), 3)
        focused = dialog.focusWidget()
        self.assertIn(
            focused,
            {
                dialog.closed_at_edit,
                dialog.closed_at_edit.set_button,
                dialog.closed_at_edit.edit,
                dialog.closed_at_edit.clear_button,
            },
        )
        self.assertEqual(dialog.result_combo.currentText(), "Jiný výsledek")
        self.assertEqual(_count("state_supervisions"), before)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

    def test_07_closed_at_before_ended_rejected(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog.ended_at_edit.set_datetime(datetime(2026, 5, 10, 16, 0, 0))
        dialog.closed_at_edit.set_datetime(datetime(2026, 5, 9, 12, 0, 0))
        before = _count("state_supervisions")
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self._save(dialog))
            self.assertIn(CLOSED_BEFORE_ENDED_MESSAGE, warning.call_args.args)
        self.assertEqual(dialog.tabs.currentIndex(), 3)
        self.assertEqual(
            dialog.closed_at_edit.get_datetime(),
            datetime(2026, 5, 9, 12, 0, 0),
        )
        self.assertEqual(_count("state_supervisions"), before)
        dialog.closed_at_edit.set_datetime(datetime(2026, 5, 10, 16, 0, 0))
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.closed_at, datetime(2026, 5, 10, 16, 0, 0))
        dialog.close()

    def test_08_cancelled_and_historical_closed_at(self) -> None:
        historical = datetime(2026, 2, 1, 12, 0, 0)
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Zrušena {self.marker}")
        dialog.status_combo.setCurrentIndex(
            dialog.status_combo.findData(STATUS_CANCELLED)
        )
        self.assertTrue(self._save(dialog))
        cancelled = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(cancelled.status, STATUS_CANCELLED)
        self.assertIsNone(cancelled.closed_at)
        dialog.close()

        record = self._create(
            status=STATUS_CLOSED,
            closed_at=historical,
            ended_at=datetime(2026, 1, 31, 15, 0, 0),
        )
        editor = StateSupervisionEditorDialog(supervision_id=record.id)
        editor.status_combo.setCurrentIndex(
            editor.status_combo.findData(STATUS_ANNOUNCED)
        )
        self.assertTrue(self._save(editor))
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.status, STATUS_ANNOUNCED)
        self.assertEqual(loaded.closed_at, historical)
        editor.close()

        with self.assertRaises(StateSupervisionError):
            state_supervision_service.create_supervision(
                authority_name=f"Closed {self.marker}",
                status=STATUS_CLOSED,
            )
        ok_cancelled = state_supervision_service.create_supervision(
            authority_name=f"Cancelled API {self.marker}",
            status=STATUS_CANCELLED,
        )
        self.assertIsNone(ok_cancelled.closed_at)

    def test_09_objections_before_protocol_rejected_after_due_allowed(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Námitky {self.marker}")
        dialog.protocol_received_at_edit.set_datetime(datetime(2026, 4, 10, 10, 0, 0))
        dialog.objections_submitted_at_edit.set_datetime(
            datetime(2026, 4, 9, 16, 0, 0)
        )
        before = _count("state_supervisions")
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self._save(dialog))
            self.assertIn(OBJECTIONS_BEFORE_PROTOCOL_MESSAGE, warning.call_args.args)
        self.assertEqual(dialog.tabs.currentIndex(), 3)
        self.assertEqual(_count("state_supervisions"), before)
        dialog.objections_due_at_edit.set_datetime(datetime(2026, 4, 20, 10, 0, 0))
        dialog.objections_submitted_at_edit.set_datetime(
            datetime(2026, 4, 25, 8, 0, 0)
        )
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.objections_submitted_at, datetime(2026, 4, 25, 8, 0, 0))
        dialog.close()

    def test_10_atomic_bundle_and_single_commit(self) -> None:
        before_s = _count("state_supervisions")
        before_d = _count("state_supervision_required_documents")
        before_t = _count("state_supervision_timeline_items")
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={
                    "authority_name": "   ",
                    "result": "Zjištěny nedostatky",
                },
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="B")],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)

        existing = self._create(result="Původní závěr")
        before_s = _count("state_supervisions")
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=existing.id,
                fields={
                    "authority_name": existing.authority_name,
                    "result": "Nový závěr",
                },
                documents=[
                    StateSupervisionRequiredDocumentDraft(title="Platný"),
                    StateSupervisionRequiredDocumentDraft(title="  "),
                ],
                timeline_items=[StateSupervisionTimelineItemDraft(title="Úkon")],
            )
        self.assertEqual(
            state_supervision_service.get_supervision(existing.id).result,
            "Původní závěr",
        )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_timeline_item_service.list_timeline_items(existing.id),
            [],
        )

        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=existing.id,
                fields={
                    "authority_name": existing.authority_name,
                    "result": "Nový závěr",
                },
                documents=[StateSupervisionRequiredDocumentDraft(title="Doklad")],
                timeline_items=[
                    StateSupervisionTimelineItemDraft(title="Platný"),
                    StateSupervisionTimelineItemDraft(title="  "),
                ],
            )
        self.assertEqual(
            state_supervision_service.get_supervision(existing.id).result,
            "Původní závěr",
        )
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Rollback {self.marker}")
        dialog.result_combo.setCurrentText("Zahájeno navazující řízení")
        dialog._timeline_drafts.append(
            StateSupervisionTimelineItemDraft(title="Pracovní")
        )
        with patch.object(
            state_supervision_timeline_item_service,
            "save_timeline_batch",
            side_effect=StateSupervisionError("umělá chyba průběhu"),
        ):
            with patch.object(QMessageBox, "warning"):
                self.assertFalse(self._save(dialog))
        self.assertIsNone(dialog.supervision_id)
        self.assertEqual(
            dialog.result_combo.currentText(),
            "Zahájeno navazující řízení",
        )
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

        source = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertIn("save_supervision_bundle", inspect.getsource(StateSupervisionEditorDialog))

        from sqlalchemy.orm import Session

        commits = []
        original = Session.commit

        def _spy(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", _spy):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={
                    "authority_name": f"Commit {self.marker}",
                    "result": "Bez zjištěných nedostatků",
                },
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="X")],
            )
        self.assertEqual(len(commits), 1)

    def test_11_no_write_on_open_and_agenda_four_tabs(self) -> None:
        record = self._create(
            result="Načíst",
            protocol_number="P-open",
        )
        before_s = _count("state_supervisions")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.tabs.setCurrentIndex(3)
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.result, "Načíst")
        self.assertEqual(loaded.protocol_number, "P-open")

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)
        page.close()


if __name__ == "__main__":
    unittest.main()
