"""STATE-SUPERVISION-EDITOR-LAYOUT-7B1: úspornější formulář a prostor pro doklady."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QWidget,
)
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

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
    from moduly.statni_dozor.constants import (
        ACTION_SAVE_AND_CLOSE,
        GROUP_ACTUAL_COURSE,
        GROUP_INFORMING,
        GROUP_INITIAL_INFORMATION,
        GROUP_NOTIFICATION,
        GROUP_PLANNED_START,
        GROUP_REQUIRED_DOCUMENTS,
        LABEL_PLANNED_START_PLACE,
        LABEL_PREPARATION_NOTE,
        LABEL_SUBJECT,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
        compose_subject_display_text,
    )


_CZECH_SUBJECT = "Kontrola skladování chemických látek\nv provozovně Žďár."
_CZECH_INITIAL = "Inspektor se zaměří na BL a školení.\nChce ověřit evidenci."
_MERGED = f"{_CZECH_SUBJECT}\n\n{_CZECH_INITIAL}"


def _count_supervisions() -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM state_supervisions").fetchone()[0])
    finally:
        conn.close()


class StateSupervisionEditorLayout7b1TestCase(unittest.TestCase):
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

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _close(self, dialog: StateSupervisionEditorDialog) -> None:
        editor = getattr(dialog, "_editor", None)
        if editor is not None:
            editor.force_close()
        else:
            dialog.close()

    def _group(self, dialog: StateSupervisionEditorDialog, title: str) -> QGroupBox:
        for box in dialog.findChildren(QGroupBox):
            if box.title() == title:
                return box
        self.fail(f"Skupina {title!r} chybí")

    def _group_titles(self, root) -> list[str]:
        return [box.title() for box in root.findChildren(QGroupBox)]

    def _show_at(
        self,
        dialog: StateSupervisionEditorDialog,
        width: int,
        height: int,
        *,
        tab: int = 1,
    ) -> None:
        dialog.setMaximumSize(max(width, 1920), max(height, 1080))
        dialog.resize(width, height)
        dialog.tabs.setCurrentIndex(tab)
        dialog.show()
        for _ in range(3):
            self._app.processEvents()

    def _fill_documents(self, dialog: StateSupervisionEditorDialog, count: int) -> None:
        dialog._document_drafts = [
            StateSupervisionRequiredDocumentDraft(
                title=f"Doklad {index + 1}",
                display_order=index * 10,
            )
            for index in range(count)
        ]
        dialog._refresh_documents_table()
        self._app.processEvents()

    def _last_row_rect_in_viewport(self, table) -> bool:
        last = table.rowCount() - 1
        item = table.item(last, 0)
        self.assertIsNotNone(item)
        bar = table.verticalScrollBar()
        bar.setValue(bar.maximum())
        self._app.processEvents()
        rect = table.visualItemRect(item)
        viewport = table.viewport().rect()
        return rect.top() >= 0 and rect.bottom() <= viewport.height()

    def test_01_compose_subject_rules(self) -> None:
        self.assertEqual(compose_subject_display_text("Předmět", None), "Předmět")
        self.assertEqual(compose_subject_display_text("", "Prvotní"), "Prvotní")
        self.assertEqual(compose_subject_display_text(None, "Prvotní"), "Prvotní")
        self.assertEqual(
            compose_subject_display_text("Předmět", "Prvotní"),
            "Předmět\n\nPrvotní",
        )
        self.assertEqual(
            compose_subject_display_text("  Stejné  ", "Stejné"),
            "Stejné",
        )
        self.assertEqual(compose_subject_display_text("  ", "  "), "")

    def test_02_meeting_place_label_replaces_start_place(self) -> None:
        dialog = StateSupervisionEditorDialog()
        labels = [widget.text() for widget in dialog.findChildren(QLabel)]
        self.assertEqual(LABEL_PLANNED_START_PLACE, "Místo setkání")
        self.assertIn("Místo setkání:", labels)
        self.assertNotIn("Místo zahájení:", labels)
        self.assertNotIn("Místo zahájení", " ".join(labels))
        dialog.close()

    def test_03_first_tab_two_column_groups_keep_scroll(self) -> None:
        source = inspect.getsource(StateSupervisionEditorDialog.__init__)
        self.assertIn("wrap_in_scroll_area(self._build_announcement_tab())", source)
        self.assertNotIn("wrap_in_scroll_area(self._build_subject_tab())", source)
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.findChildren(QSplitter), [])
        scroll = dialog.tabs.widget(0)
        self.assertIsInstance(scroll, QScrollArea)
        for title in (
            GROUP_NOTIFICATION,
            GROUP_PLANNED_START,
            GROUP_ACTUAL_COURSE,
            GROUP_INFORMING,
        ):
            group = self._group(dialog, title)
            rows = [
                child
                for child in group.findChildren(QWidget)
                if child.objectName() == "ss_two_column_row"
            ]
            self.assertEqual(len(rows), 1, title)
            layout = rows[0].layout()
            self.assertIsInstance(layout, QHBoxLayout)
            self.assertEqual(layout.stretch(0), 1, title)
            self.assertEqual(layout.stretch(1), 1, title)
        dialog.close()

    def test_04_nullable_datetime_stays_empty_with_calendar_and_clear(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self._show_at(dialog, 1600, 900, tab=0)
        for widget in (
            dialog.announced_at_edit,
            dialog.planned_start_at_edit,
            dialog.started_at_edit,
            dialog.ended_at_edit,
            dialog.trade_union_notified_at_edit,
            dialog.management_notified_at_edit,
        ):
            self.assertIsInstance(widget, NullableDateTimeEdit)
            self.assertIsNone(widget.get_datetime())
            self.assertFalse(widget.has_value())
            self.assertIsNotNone(widget.set_button)
            self.assertIsNotNone(widget.clear_button)
            self.assertEqual(widget.set_button.toolTip(), "Vybrat datum")
            self.assertEqual(widget.clear_button.toolTip(), "Vymazat datum a čas")
            self.assertGreater(widget.width(), 0)
            self.assertFalse(widget.edit.geometry().intersects(widget.set_button.geometry()))
            self.assertFalse(
                widget.set_button.geometry().intersects(widget.clear_button.geometry())
            )
        self._close(dialog)

    def test_05_initial_information_editor_removed(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.tabs.setCurrentIndex(1)
        titles = self._group_titles(dialog.tabs.widget(1))
        self.assertNotIn(GROUP_INITIAL_INFORMATION, titles)
        self.assertEqual(
            titles,
            [LABEL_SUBJECT, LABEL_PREPARATION_NOTE, GROUP_REQUIRED_DOCUMENTS],
        )
        self.assertFalse(hasattr(dialog, "initial_information_edit"))
        self.assertIsInstance(dialog.subject_edit, QTextEdit)
        self.assertIsInstance(dialog.preparation_note_edit, QTextEdit)
        dialog.close()

    def test_06_load_preserves_old_initial_without_write_or_dirty(self) -> None:
        record = self._create(
            subject=_CZECH_SUBJECT,
            initial_information=_CZECH_INITIAL,
        )
        with (
            patch.object(state_supervision_service, "save_supervision_bundle") as bundle,
            patch.object(state_supervision_service, "update_supervision") as update,
            patch.object(state_supervision_service, "create_supervision") as create,
            patch.object(Session, "commit") as commit,
        ):
            dialog = StateSupervisionEditorDialog(supervision_id=record.id)
            bundle.assert_not_called()
            update.assert_not_called()
            create.assert_not_called()
            commit.assert_not_called()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.subject_edit.toPlainText(), _MERGED)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.subject, _CZECH_SUBJECT)
        self.assertEqual(loaded.initial_information, _CZECH_INITIAL)
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_07_save_moves_initial_into_subject_once(self) -> None:
        record = self._create(
            subject=_CZECH_SUBJECT,
            initial_information=_CZECH_INITIAL,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.file_number_edit.setText(f"CJ-{self.marker}")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.subject, _MERGED)
        self.assertIsNone(loaded.initial_information)
        self.assertEqual(loaded.file_number, f"CJ-{self.marker}")
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(reopened.subject_edit.toPlainText(), _MERGED)
        self.assertNotIn(_CZECH_INITIAL + "\n\n" + _CZECH_INITIAL, reopened.subject_edit.toPlainText())
        self.assertEqual(reopened.subject_edit.toPlainText().count(_CZECH_INITIAL), 1)
        self.assertFalse(reopened._editor.is_dirty())
        still = state_supervision_service.get_supervision(record.id)
        self.assertEqual(still.subject, _MERGED)
        self.assertIsNone(still.initial_information)
        reopened.close()

    def test_08_identical_texts_are_not_duplicated(self) -> None:
        record = self._create(subject="Stejný text", initial_information="Stejný text")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(dialog.subject_edit.toPlainText(), "Stejný text")
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

        only_initial = self._create(subject=None, initial_information="Jen prvotní")
        dialog = StateSupervisionEditorDialog(supervision_id=only_initial.id)
        self.assertEqual(dialog.subject_edit.toPlainText(), "Jen prvotní")
        dialog.close()

    def test_09_subject_tab_stretch_gives_documents_remaining_height(self) -> None:
        dialog = StateSupervisionEditorDialog()
        page = dialog.tabs.widget(1)
        layout = page.layout()
        self.assertEqual(layout.count(), 3)
        self.assertEqual(layout.stretch(0), 0)
        self.assertEqual(layout.stretch(1), 0)
        self.assertEqual(layout.stretch(2), 1)
        self.assertEqual(
            dialog.subject_edit.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Maximum,
        )
        self.assertEqual(
            dialog.preparation_note_edit.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Maximum,
        )
        self.assertEqual(
            dialog.documents_table.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
        )
        docs = self._group(dialog, GROUP_REQUIRED_DOCUMENTS)
        self.assertEqual(docs.layout().stretch(docs.layout().count() - 1), 1)
        dialog.close()

    def test_10_last_document_row_and_scrollbar_at_common_sizes(self) -> None:
        dialog = StateSupervisionEditorDialog()
        heights: dict[tuple[int, int], int] = {}
        for width, height in ((1600, 900), (1920, 1080)):
            self._show_at(dialog, width, height, tab=1)
            self._fill_documents(dialog, 16)
            table = dialog.documents_table
            table_height = table.height()
            heights[(width, height)] = table_height
            self.assertGreaterEqual(
                table_height,
                180,
                f"Tabulka dokladů je příliš nízká při {width}×{height}: {table_height}",
            )
            mapped_bottom = table.mapTo(dialog, QPoint(0, table.height())).y()
            buttons_top = dialog._buttons.mapTo(dialog, QPoint(0, 0)).y()
            self.assertLessEqual(
                mapped_bottom,
                buttons_top,
                f"Tabulka zasahuje do lišty tlačítek při {width}×{height}",
            )
            tabs_bottom = dialog.tabs.mapTo(dialog, QPoint(0, dialog.tabs.height())).y()
            self.assertLessEqual(mapped_bottom, tabs_bottom + 2)
            self.assertTrue(
                self._last_row_rect_in_viewport(table),
                f"Poslední řádek není celý vidět při {width}×{height}",
            )
            self.assertGreater(table.verticalScrollBar().maximum(), 0)
            last = table.rowCount() - 1
            table.selectRow(last)
            self._app.processEvents()
            self.assertTrue(dialog.edit_document_btn.isEnabled())
            self.assertTrue(dialog.remove_document_btn.isEnabled())
            self.assertTrue(dialog.move_document_up_btn.isEnabled())
            self.assertFalse(dialog.move_document_down_btn.isEnabled())
            self.assertGreaterEqual(table.minimumHeight(), 80)
            self.assertLessEqual(table.minimumHeight(), 160)
        self.assertGreaterEqual(heights[(1920, 1080)], heights[(1600, 900)])
        self._close(dialog)
        print(
            "7B1 documents_table heights: "
            f"1600x900={heights[(1600, 900)]} 1920x1080={heights[(1920, 1080)]}"
        )

    def test_11_table_height_does_not_follow_document_count(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self._fill_documents(dialog, 2)
        self._show_at(dialog, 1600, 900, tab=1)
        few = dialog.documents_table.height()
        min_few = dialog.documents_table.minimumHeight()
        self._fill_documents(dialog, 16)
        self._show_at(dialog, 1600, 900, tab=1)
        many = dialog.documents_table.height()
        min_many = dialog.documents_table.minimumHeight()
        self.assertEqual(min_few, min_many)
        self.assertAlmostEqual(few, many, delta=24)
        self._close(dialog)

    def test_12_layout_does_not_clip_labels_or_overlap_controls(self) -> None:
        dialog = StateSupervisionEditorDialog()
        for width, height in ((1600, 900), (1920, 1080)):
            self._show_at(dialog, width, height, tab=0)
            labels = [
                label
                for label in dialog.findChildren(QLabel)
                if label.isVisible() and label.text().strip() and ":" in label.text()
            ]
            self.assertTrue(labels)
            for label in labels:
                self.assertGreater(label.width(), 0, label.text())
                self.assertGreater(label.height(), 0, label.text())
            rows = [
                child
                for child in dialog.findChildren(QWidget)
                if child.objectName() == "ss_two_column_row" and child.isVisible()
            ]
            for row in rows:
                left = row.layout().itemAt(0).widget()
                right = row.layout().itemAt(1).widget()
                left_rect = left.geometry()
                right_rect = right.geometry()
                self.assertFalse(
                    left_rect.intersects(right_rect),
                    f"Sloupce se překrývají při {width}×{height}",
                )
                self.assertGreater(left.width(), 80)
                self.assertGreater(right.width(), 80)
                self.assertAlmostEqual(left.width(), right.width(), delta=80)
        self._close(dialog)

    def test_13_dirty_and_all_save_paths(self) -> None:
        record = self._create(
            subject="Baseline předmět",
            initial_information="Starší informace",
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertIsInstance(dialog._editor, EditorDialogController)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        self.assertFalse(dialog._editor.is_dirty())

        merged = compose_subject_display_text("Baseline předmět", "Starší informace")
        dialog.subject_edit.setPlainText("Změna předmětu")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog.subject_edit.setPlainText(merged)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.preparation_note_edit.setPlainText("Nová příprava")
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.subject, merged)
        self.assertIsNone(loaded.initial_information)
        self.assertEqual(loaded.preparation_note, "Nová příprava")
        dialog.close()

        save_close = StateSupervisionEditorDialog(supervision_id=record.id)
        save_close.subject_edit.setPlainText("Uložit a zavřít")
        self.assertEqual(save_close._save_close_btn.text(), ACTION_SAVE_AND_CLOSE)
        save_close._save_and_close()
        self.assertEqual(save_close.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).subject,
            "Uložit a zavřít",
        )
        self.assertIsNone(
            state_supervision_service.get_supervision(record.id).initial_information
        )
        save_close.close()

        close_save = StateSupervisionEditorDialog(supervision_id=record.id)
        close_save.preparation_note_edit.setPlainText("Zavřít uloží")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            self.assertTrue(close_save._editor.request_close())
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).preparation_note,
            "Zavřít uloží",
        )
        close_save.close()

    def test_14_selecting_last_document_does_not_write(self) -> None:
        record = self._create()
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self._fill_documents(dialog, 12)
        self._show_at(dialog, 1600, 900, tab=1)
        with (
            patch.object(state_supervision_service, "save_supervision_bundle") as bundle,
            patch.object(Session, "commit") as commit,
        ):
            last = dialog.documents_table.rowCount() - 1
            dialog.documents_table.selectRow(last)
            self._app.processEvents()
            bundle.assert_not_called()
            commit.assert_not_called()
        before = _count_supervisions()
        self._close(dialog)
        self.assertEqual(_count_supervisions(), before)

    def test_15_documents_still_save_through_bundle(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        self._fill_documents(dialog, 2)
        with patch.object(
            state_supervision_service,
            "save_supervision_bundle",
            wraps=state_supervision_service.save_supervision_bundle,
        ) as bundle:
            self.assertTrue(self._save(dialog))
            bundle.assert_called_once()
        loaded_docs = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertIsNotNone(loaded_docs)
        from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
            state_supervision_required_document_service,
        )

        stored = state_supervision_required_document_service.list_documents(
            int(dialog.supervision_id)
        )
        self.assertEqual(len(stored), 2)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
