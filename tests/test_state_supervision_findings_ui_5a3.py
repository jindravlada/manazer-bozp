"""STATE-SUPERVISION-FINDINGS-UI-5A3: evidence zjištění kontroly."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
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

    import core.services.attachment_service as attachment_module

    importlib.reload(attachment_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.models.attachment_staging import AttachmentStagingState
    from core.shared.constants import (
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_OPATRENI,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.finding_display import FINDING_STATUS_LABELS, FINDING_TYPE_LABELS
    from core.widgets.nullable_date_edit import NullableDateEdit
    from core.widgets.thp_worker_selector import ThpWorkerSelector
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_ADD,
        ACTION_CREATE_TASK,
        ACTION_EDIT,
        ACTION_MOVE_DOWN,
        ACTION_MOVE_UP,
        ACTION_OPEN_TASK,
        ACTION_REMOVE,
        COL_FINDING_DESCRIPTION,
        COL_FINDING_DUE,
        COL_FINDING_PERSON,
        COL_FINDING_PLACE,
        COL_FINDING_STATUS,
        COL_FINDING_TASK,
        COL_FINDING_TYPE,
        DIALOG_FINDING_NEW,
        EMPTY_FINDINGS,
        EMPTY_VALUE,
        FINDING_COLUMN_HEADERS,
        FINDING_DESCRIPTION_REQUIRED_MESSAGE,
        FINDING_TASK_MISSING_LABEL,
        GROUP_COURSE_TIMELINE,
        GROUP_FINDINGS,
        STATE_SUPERVISION_FINDING_TYPE_LABELS,
        STATE_SUPERVISION_FINDING_TYPE_ORDER,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
        state_supervision_finding_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
        state_supervision_timeline_item_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_finding_dialog import (
        StateSupervisionFindingDialog,
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


def _draft(**fields) -> StateSupervisionFindingDraft:
    payload = {
        "finding_type": FINDING_TYPE_ZJISTENI,
        "description": "Kontrolní zjištění",
    }
    payload.update(fields)
    return StateSupervisionFindingDraft(**payload)


def _descriptions(supervision_id: int) -> list[str]:
    rows = state_supervision_finding_service.list_findings(supervision_id)
    return [str(row.description) for row in rows]


class StateSupervisionFindingsUi5a3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        importlib.reload(attachment_module)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.worker = settings_service.save_worker(
            first_name="Petr",
            last_name=f"THP-{self.marker}",
        )

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _add_working(
        self,
        dialog: StateSupervisionEditorDialog,
        **fields,
    ) -> StateSupervisionFindingDraft:
        payload = {"description": f"Zjištění {self.marker}"}
        payload.update(fields)
        payload.setdefault("display_order", len(dialog._findings_drafts) * 10)
        draft = _draft(**payload)
        dialog._findings_drafts.append(draft)
        dialog._refresh_findings_table(select_key=draft.client_key)
        dialog._editor.refresh_dirty()
        return draft

    def test_01_layout_five_tabs_findings_group_empty_state(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.tabs.count(), 5)
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertEqual(dialog._course_tab_index, 2)
        course = dialog.tabs.widget(2)
        groups = [box.title() for box in course.findChildren(QGroupBox)]
        self.assertEqual(groups, [GROUP_COURSE_TIMELINE, GROUP_FINDINGS])
        self.assertEqual(len(course.findChildren(QTabWidget)), 0)
        self.assertEqual(len(course.findChildren(QSplitter)), 0)
        self.assertEqual(course.layout().stretch(0), 1)
        self.assertEqual(course.layout().stretch(1), 1)
        self.assertFalse(dialog.timeline_table.isHidden())
        self.assertIsNotNone(dialog.timeline_table)
        self.assertEqual(dialog.findings_empty_label.text(), EMPTY_FINDINGS)
        self.assertFalse(dialog.findings_empty_label.isHidden())
        self.assertEqual(dialog.findings_table.columnCount(), 7)
        self.assertEqual(
            [
                dialog.findings_table.horizontalHeaderItem(i).text()
                for i in range(7)
            ],
            FINDING_COLUMN_HEADERS,
        )
        self.assertEqual(
            dialog.findings_table.textElideMode(), Qt.TextElideMode.ElideRight
        )
        self.assertFalse(dialog.findings_table.isSortingEnabled())
        self.assertEqual(dialog.add_finding_btn.text(), ACTION_ADD)
        self.assertEqual(dialog.edit_finding_btn.text(), ACTION_EDIT)
        self.assertEqual(dialog.remove_finding_btn.text(), ACTION_REMOVE)
        self.assertEqual(dialog.move_finding_up_btn.text(), ACTION_MOVE_UP)
        self.assertEqual(dialog.move_finding_down_btn.text(), ACTION_MOVE_DOWN)
        self.assertEqual(dialog.create_finding_task_btn.text(), ACTION_CREATE_TASK)
        self.assertEqual(dialog.open_finding_task_btn.text(), ACTION_OPEN_TASK)
        self.assertTrue(dialog.add_finding_btn.isEnabled())
        self.assertFalse(dialog.edit_finding_btn.isEnabled())
        self.assertFalse(dialog.remove_finding_btn.isEnabled())
        self.assertFalse(dialog.move_finding_up_btn.isEnabled())
        self.assertFalse(dialog.move_finding_down_btn.isEnabled())
        self.assertFalse(dialog.create_finding_task_btn.isEnabled())
        self.assertFalse(dialog.open_finding_task_btn.isEnabled())
        self.assertLessEqual(dialog.minimumWidth(), 1600)
        self.assertLessEqual(dialog.minimumHeight(), 480)
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 5)
        self.assertIn("doubleClicked.connect(self._edit_selected_finding)", source)
        self.assertIn("ACTION_CREATE_TASK", source)
        self.assertIn("ACTION_OPEN_TASK", source)
        self.assertNotIn("SourceNavigator", source)
        self.assertNotIn("QSplitter", source)
        self.assertNotIn("save_button.setEnabled(True)", source)
        self.assertNotIn("PKZ", source)
        dialog.close()

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)

    def test_02_type_labels_and_no_methodology_pkz(self) -> None:
        expected = {
            FINDING_TYPE_PRILEZITOST: "Příležitost ke zlepšení (PKZ)",
            FINDING_TYPE_OPATRENI: "Dohodnutý další postup",
            FINDING_TYPE_NEDOSTATEK: "Nedostatek",
            FINDING_TYPE_ZAVADA: "Závada",
            FINDING_TYPE_PORUSENI_PREDPISU: "Porušení požadavku",
            FINDING_TYPE_ZJISTENI: "Jiné zjištění",
        }
        self.assertEqual(STATE_SUPERVISION_FINDING_TYPE_LABELS, expected)
        self.assertEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_PRILEZITOST],
            "Příležitost ke zlepšování",
        )
        self.assertEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_PORUSENI_PREDPISU],
            "Porušení předpisu",
        )
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_ZJISTENI], "Zjištění")
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_OPATRENI], "Opatření")

        sub = StateSupervisionFindingDialog(is_new=True)
        labels = [sub.type_combo.itemText(i) for i in range(sub.type_combo.count())]
        self.assertEqual(
            labels,
            [STATE_SUPERVISION_FINDING_TYPE_LABELS[code] for code in STATE_SUPERVISION_FINDING_TYPE_ORDER],
        )
        self.assertEqual(sub.type_combo.currentData(), FINDING_TYPE_ZJISTENI)
        sub.close()

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        for code in STATE_SUPERVISION_FINDING_TYPE_ORDER:
            self._add_working(
                dialog,
                finding_type=code,
                description=f"Text {code}",
            )
        shown = [
            dialog.findings_table.item(row, COL_FINDING_TYPE).text()
            for row in range(dialog.findings_table.rowCount())
        ]
        self.assertEqual(
            shown,
            [STATE_SUPERVISION_FINDING_TYPE_LABELS[code] for code in STATE_SUPERVISION_FINDING_TYPE_ORDER],
        )
        dialog.close()

        editor_src = inspect.getsource(StateSupervisionEditorDialog)
        dialog_src = inspect.getsource(StateSupervisionFindingDialog)
        for source in (editor_src, dialog_src):
            self.assertNotIn('["pkz"]', source)
            self.assertNotIn("['pkz']", source)
            self.assertNotIn(".pkz", source)
            self.assertNotIn("ciselniky", source)
            self.assertNotIn("MeetingPersonTypeahead", source)
        self.assertNotIn("finding_task_service", dialog_src)
        self.assertNotIn("from core.shared.sluzby.finding_task_service", editor_src)
        self.assertNotIn("finding_task_service.create_task_from_finding", editor_src)

    def test_03_subdialog_fields_cancel_noop_and_task_id(self) -> None:
        original = _draft(
            description="Původní popis",
            source_area_label="Hala A",
            task_id=4242,
            id=7,
            client_key="keep-key",
            display_order=20,
        )
        sub = StateSupervisionFindingDialog(draft=replace(original), is_new=False)
        self.assertEqual(sub.windowModality(), Qt.WindowModality.WindowModal)
        self.assertEqual(sub.windowTitle(), "Zjištění kontroly")
        self.assertIsInstance(sub.description_edit, QTextEdit)
        self.assertFalse(sub.description_edit.acceptRichText())
        self.assertEqual(
            sub.description_edit.lineWrapMode(), QTextEdit.LineWrapMode.WidgetWidth
        )
        self.assertIsInstance(sub.person_selector, ThpWorkerSelector)
        self.assertIsInstance(sub.due_date_edit, NullableDateEdit)
        self.assertIsInstance(sub.resolved_at_edit, NullableDateEdit)
        self.assertIsNone(sub.due_date_edit.get_date())
        statuses = [sub.status_combo.itemText(i) for i in range(sub.status_combo.count())]
        self.assertEqual(
            statuses,
            [
                FINDING_STATUS_LABELS[FINDING_STATUS_OTEVRENE],
                FINDING_STATUS_LABELS[FINDING_STATUS_V_PROCESU],
                FINDING_STATUS_LABELS[FINDING_STATUS_VYPORADANO],
            ],
        )

        sub.description_edit.setPlainText("  ")
        with patch.object(QMessageBox, "warning") as warning:
            sub._on_save()
            warning.assert_called()
            self.assertIn(
                FINDING_DESCRIPTION_REQUIRED_MESSAGE, warning.call_args.args[2]
            )
        self.assertIsNone(sub.result_draft)

        czech = "Popis zjištění — více řádků\nDruhý řádek v hale."
        sub.description_edit.setPlainText(czech)
        sub.place_edit.setText("Sklad chemikálií")
        sub.status_combo.setCurrentIndex(
            sub.status_combo.findData(FINDING_STATUS_V_PROCESU)
        )
        sub.person_selector.set_person_id(self.worker.id)
        sub.due_date_edit.set_date_value(date(2026, 9, 15))
        sub.recommended_action_edit.setPlainText("Doplnit označení.")
        sub.resolution_note_edit.setPlainText("Poznámka k vypořádání.")
        sub.status_combo.setCurrentIndex(
            sub.status_combo.findData(FINDING_STATUS_VYPORADANO)
        )
        self.assertIsNone(sub.resolved_at_edit.get_date())
        sub._on_save()
        saved = sub.result_draft
        self.assertIsNotNone(saved)
        self.assertEqual(saved.description, czech)
        self.assertEqual(saved.source_area_label, "Sklad chemikálií")
        self.assertEqual(saved.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(saved.responsible_person_id, self.worker.id)
        self.assertTrue(saved.responsible_person_name)
        self.assertEqual(saved.due_date, date(2026, 9, 15))
        self.assertEqual(saved.recommended_action, "Doplnit označení.")
        self.assertEqual(saved.resolution_note, "Poznámka k vypořádání.")
        self.assertIsNone(saved.resolved_at)
        self.assertEqual(saved.task_id, 4242)
        self.assertEqual(saved.id, 7)
        self.assertEqual(saved.client_key, "keep-key")
        self.assertEqual(saved.display_order, 20)
        sub.close()

        new_sub = StateSupervisionFindingDialog(is_new=True)
        self.assertEqual(new_sub.windowTitle(), DIALOG_FINDING_NEW)
        new_sub.close()

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        current = self._add_working(dialog, description="Pracovní", task_id=99)
        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=None,
        ):
            dialog._edit_selected_finding()
        self.assertEqual(dialog._findings_drafts[0].description, "Pracovní")
        self.assertEqual(dialog._findings_drafts[0].task_id, 99)
        self.assertTrue(dialog._editor.is_dirty())

        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.is_dirty())
        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=replace(current),
        ):
            dialog._edit_selected_finding()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_04_new_control_add_edit_move_remove_without_write(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertIsNone(dialog.supervision_id)
        self.assertTrue(dialog.add_finding_btn.isEnabled())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")

        created = _draft(description="Nové zjištění kontroly")
        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=created,
        ):
            dialog._add_finding()
        self.assertEqual(len(dialog._findings_drafts), 1)
        self.assertIsNone(dialog._findings_drafts[0].id)
        self.assertTrue(dialog._findings_drafts[0].client_key)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog.findings_empty_label.isHidden())
        self.assertEqual(_count("findings"), 0)
        self.assertTrue(dialog.remove_finding_btn.isEnabled())

        second = self._add_working(dialog, description="Druhé")
        dialog._select_finding_key(second.client_key)
        dialog._move_selected_finding(-1)
        self.assertEqual(
            [row.description for row in dialog._findings_drafts],
            ["Druhé", "Nové zjištění kontroly"],
        )
        dialog._select_finding_key(dialog._findings_drafts[0].client_key)
        dialog._remove_selected_finding()
        self.assertEqual(
            [row.description for row in dialog._findings_drafts],
            ["Nové zjištění kontroly"],
        )
        self.assertEqual(_count("findings"), 0)
        self.assertIsNone(dialog.supervision_id)
        dialog.close()

    def test_05_new_control_bundle_save_reload_and_no_duplicate(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        self._add_working(
            dialog,
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="Uložit jedním bundle",
            source_area_label="Kotelna",
            due_date=date(2026, 10, 1),
        )
        before_s = _count("state_supervisions")
        before_f = _count("findings")
        before_t = _count("tasks")
        self.assertTrue(self._save(dialog))
        self.assertIsNotNone(dialog.supervision_id)
        self.assertEqual(_count("state_supervisions"), before_s + 1)
        self.assertEqual(_count("findings"), before_f + 1)
        self.assertEqual(_count("tasks"), before_t)
        self.assertEqual(len(dialog._findings_drafts), 1)
        self.assertIsNotNone(dialog._findings_drafts[0].id)
        self.assertEqual(dialog._findings_drafts[0].description, "Uložit jedním bundle")
        self.assertEqual(dialog._findings_drafts[0].source_area_label, "Kotelna")
        stored = state_supervision_finding_service.list_findings(dialog.supervision_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].entity_type, "state_supervision")
        self.assertEqual(stored[0].entity_id, dialog.supervision_id)
        self.assertFalse(stored[0].source_control_point_id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        self.assertTrue(self._save(dialog))
        self.assertEqual(
            len(state_supervision_finding_service.list_findings(dialog.supervision_id)),
            1,
        )
        self.assertEqual(_count("tasks"), before_t)

        with patch.object(dialog, "accept") as accept:
            dialog._save_and_close()
            accept.assert_called_once()
        dialog.close()

    def test_06_discard_does_not_create_finding(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        self._add_working(dialog, description="Nemá vzniknout")
        before = _count("findings")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        self.assertEqual(_count("findings"), before)
        dialog.close()

        record = state_supervision_service.create_supervision(
            authority_name=f"Existující {self.marker}"
        )
        state_supervision_finding_service.save_state_supervision_findings_batch(
            record.id,
            [_draft(description="Původní uložené", finding_type=FINDING_TYPE_ZAVADA)],
        )
        opened = StateSupervisionEditorDialog(supervision_id=record.id)
        opened._findings_drafts[0] = replace(
            opened._findings_drafts[0], description="Změna bez uložení"
        )
        opened._refresh_findings_table()
        opened._editor.refresh_dirty()
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ):
            self.assertFalse(opened._editor.request_close())
        self.assertTrue(opened._editor.is_dirty())
        self.assertEqual(opened._findings_drafts[0].description, "Změna bez uložení")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(opened._editor.request_close())
        opened.close()
        self.assertEqual(_descriptions(record.id), ["Původní uložené"])

    def test_07_existing_load_all_statuses_cannot_remove_preserve_task(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"KHS {self.marker}"
        )
        state_supervision_finding_service.save_state_supervision_findings_batch(
            record.id,
            [
                _draft(
                    description="Otevřené zjištění",
                    status=FINDING_STATUS_OTEVRENE,
                    display_order=0,
                ),
                _draft(
                    description="V procesu",
                    status=FINDING_STATUS_V_PROCESU,
                    finding_type=FINDING_TYPE_NEDOSTATEK,
                    display_order=10,
                    task_id=777,
                ),
                _draft(
                    description="Už vypořádané",
                    status=FINDING_STATUS_VYPORADANO,
                    finding_type=FINDING_TYPE_PORUSENI_PREDPISU,
                    display_order=20,
                    resolved_at=date(2026, 8, 1),
                ),
            ],
        )
        historical = _draft(description="Historické mimo dávku UI")
        state_supervision_finding_service.save_state_supervision_findings_batch(
            record.id,
            [historical],
        )
        # Above batch only saves the one draft; previous three remain (no delete).
        listed = state_supervision_finding_service.list_findings(record.id)
        self.assertEqual(len(listed), 4)

        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(len(dialog._findings_drafts), 4)
        self.assertFalse(dialog._editor.is_dirty())
        statuses = [row.status for row in dialog._findings_drafts]
        self.assertIn(FINDING_STATUS_OTEVRENE, statuses)
        self.assertIn(FINDING_STATUS_V_PROCESU, statuses)
        self.assertIn(FINDING_STATUS_VYPORADANO, statuses)
        linked = next(row for row in dialog._findings_drafts if row.task_id == 777)
        dialog._select_finding_key(linked.client_key)
        self.assertFalse(dialog.remove_finding_btn.isEnabled())
        self.assertIn("historii", dialog.remove_finding_btn.toolTip())
        dialog._remove_selected_finding()
        self.assertEqual(len(dialog._findings_drafts), 4)
        task_row = next(
            i
            for i, row in enumerate(dialog._findings_drafts)
            if row.task_id == 777
        )
        self.assertEqual(
            dialog.findings_table.item(task_row, COL_FINDING_TASK).text(),
            FINDING_TASK_MISSING_LABEL,
        )
        empty_task = next(
            i for i, row in enumerate(dialog._findings_drafts) if row.task_id is None
        )
        self.assertEqual(
            dialog.findings_table.item(empty_task, COL_FINDING_TASK).text(),
            EMPTY_VALUE,
        )

        target = next(
            row
            for row in dialog._findings_drafts
            if row.description == "Otevřené zjištění"
        )
        dialog._select_finding_key(target.client_key)
        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=replace(
                target,
                status=FINDING_STATUS_VYPORADANO,
                description="Otevřené zjištění",
            ),
        ):
            dialog._edit_selected_finding()
        self.assertTrue(dialog._editor.is_dirty())
        omitted = next(
            row
            for row in dialog._findings_drafts
            if row.description == "Historické mimo dávku UI"
        )
        dialog._findings_drafts = [
            item
            for item in dialog._findings_drafts
            if item.client_key != omitted.client_key
        ]
        dialog._refresh_findings_table()
        dialog._editor.refresh_dirty()
        self.assertTrue(self._save(dialog))
        reloaded = state_supervision_finding_service.list_findings(record.id)
        texts = {row.description: row for row in reloaded}
        self.assertIn("Historické mimo dávku UI", texts)
        self.assertEqual(texts["Otevřené zjištění"].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(texts["V procesu"].task_id, 777)
        self.assertEqual(_count("tasks"), 0)
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(len(reopened._findings_drafts), 4)
        reopened.close()

    def test_08_dirty_selection_tab_cancel_and_baseline(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        first = self._add_working(dialog, description="První")
        second = self._add_working(dialog, description="Druhé")
        self.assertTrue(dialog._editor.is_dirty())
        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.findings_table.selectRow(0)
        dialog.findings_table.selectRow(1)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.tabs.setCurrentIndex(0)
        dialog.tabs.setCurrentIndex(2)
        self.assertFalse(dialog._editor.is_dirty())

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=None,
        ):
            dialog._edit_selected_finding()
        self.assertFalse(dialog._editor.is_dirty())

        with patch(
            "moduly.statni_dozor.ui.state_supervision_finding_dialog.exec_finding_dialog",
            return_value=replace(second, description="Druhé upraveno"),
        ):
            dialog._select_finding_key(second.client_key)
            dialog._edit_selected_finding()
        self.assertTrue(dialog._editor.is_dirty())

        dialog._findings_drafts[1] = replace(second, description="Druhé")
        dialog._refresh_findings_table(select_key=second.client_key)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog._select_finding_key(second.client_key)
        dialog._move_selected_finding(-1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog._select_finding_key(first.client_key)
        dialog._move_selected_finding(-1)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.save_button.isEnabled())

        extra = self._add_working(dialog, description="Navíc")
        self.assertTrue(dialog._editor.is_dirty())
        dialog._select_finding_key(extra.client_key)
        dialog._remove_selected_finding()
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_09_rollback_keeps_working_collection_and_no_partial_id(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        invalid = self._add_working(
            dialog,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neplatný druh",
        )
        client_key = invalid.client_key
        before_s = _count("state_supervisions")
        before_f = _count("findings")
        dialog.tabs.setCurrentIndex(0)
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self._save(dialog))
            self.assertTrue(warning.called)
        self.assertEqual(dialog.tabs.currentIndex(), dialog._course_tab_index)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(len(dialog._findings_drafts), 1)
        self.assertEqual(dialog._findings_drafts[0].client_key, client_key)
        self.assertIsNone(dialog._findings_drafts[0].id)
        self.assertIsNone(dialog.supervision_id)
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("findings"), before_f)
        dialog.close()

        existing = state_supervision_service.create_supervision(
            authority_name=f"Rollback {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            existing.id, title="Doklad"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            existing.id, title="Úkon"
        )
        opened = StateSupervisionEditorDialog(supervision_id=existing.id)
        opened.authority_combo.setCurrentText(f"Změna {self.marker}")
        self._add_working(
            opened,
            finding_type=FINDING_TYPE_NESHODA,
            description="Rozbije bundle",
        )
        original_docs = _count("state_supervision_required_documents")
        with patch.object(QMessageBox, "warning"):
            self.assertFalse(self._save(opened))
        reloaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(reloaded.authority_name, f"Rollback {self.marker}")
        self.assertEqual(_count("findings"), before_f)
        self.assertEqual(_count("state_supervision_required_documents"), original_docs)
        self.assertTrue(opened._editor.is_dirty())
        self.assertIsNone(opened._findings_drafts[-1].id)
        opened.close()

        attach_dialog = StateSupervisionEditorDialog()
        attach_dialog.authority_combo.setCurrentText(f"Příloha {self.marker}")
        draft = self._add_working(attach_dialog, description="Má zmizet s přílohou")
        missing = _TMP / f"neni-{self.marker}.pdf"
        attach_dialog._attachment_staging.add_pending_path(missing)
        attach_dialog._editor.refresh_dirty()
        before_s2 = _count("state_supervisions")
        before_f2 = _count("findings")
        with patch.object(QMessageBox, "warning"):
            self.assertFalse(self._save(attach_dialog))
        self.assertEqual(_count("state_supervisions"), before_s2)
        self.assertEqual(_count("findings"), before_f2)
        self.assertIsNone(draft.id)
        self.assertEqual(draft.description, "Má zmizet s přílohou")
        self.assertIsNone(attach_dialog.supervision_id)
        self.assertNotEqual(
            attach_dialog.tabs.currentIndex(), attach_dialog._course_tab_index
        )
        attach_dialog.close()

    def test_10_no_tasks_empty_cells_and_controller(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        self._add_working(
            dialog,
            description="Dlouhý popis zjištění " + ("ž" * 80),
            source_area_label="",
        )
        self.assertEqual(
            dialog.findings_table.item(0, COL_FINDING_PLACE).text(), EMPTY_VALUE
        )
        self.assertEqual(
            dialog.findings_table.item(0, COL_FINDING_PERSON).text(), EMPTY_VALUE
        )
        self.assertEqual(
            dialog.findings_table.item(0, COL_FINDING_DUE).text(), EMPTY_VALUE
        )
        self.assertEqual(
            dialog.findings_table.item(0, COL_FINDING_STATUS).text(),
            FINDING_STATUS_LABELS[FINDING_STATUS_OTEVRENE],
        )
        tooltip = dialog.findings_table.item(0, COL_FINDING_DESCRIPTION).toolTip()
        self.assertIn("Dlouhý popis zjištění", tooltip)
        self.assertTrue(self._save(dialog))
        due = date(2026, 3, 8)
        row = dialog._findings_drafts[0]
        dialog._findings_drafts[0] = replace(row, due_date=due)
        dialog._refresh_findings_table()
        self.assertEqual(
            dialog.findings_table.item(0, COL_FINDING_DUE).text(),
            format_supervision_date(due),
        )
        self.assertEqual(_count("tasks"), 0)
        texts = [
            dialog.add_finding_btn.text(),
            dialog.edit_finding_btn.text(),
            dialog.remove_finding_btn.text(),
        ]
        self.assertNotIn("Vytvořit úkol", texts)
        self.assertEqual(dialog.create_finding_task_btn.text(), "Vytvořit úkol")
        self.assertEqual(dialog.open_finding_task_btn.text(), "Otevřít úkol")
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertIn("findings=self._findings_drafts_for_save()", persist)
        self.assertIn("save_supervision_bundle", persist)
        self.assertNotIn("finding_service.delete", persist)
        dialog.close()

        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("_editor.refresh_dirty()", source)
        self.assertEqual(source.count("create_supervision("), 0)
        self.assertIsInstance(AttachmentStagingState(), AttachmentStagingState)
        self.assertIn(
            "StateSupervisionRequiredDocumentDraft",
            inspect.getsource(StateSupervisionRequiredDocumentDraft),
        )
        self.assertIn(
            "StateSupervisionTimelineItemDraft",
            inspect.getsource(StateSupervisionTimelineItemDraft),
        )


if __name__ == "__main__":
    unittest.main()
