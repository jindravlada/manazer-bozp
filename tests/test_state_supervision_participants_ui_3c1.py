"""STATE-SUPERVISION-PARTICIPANTS-UI-3C1: účastníci kontroly."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QMessageBox, QTabWidget
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-participants-ui-3c1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EditorDialogController
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead
    from moduly.statni_dozor.constants import (
        ACTION_ADD,
        ACTION_EDIT,
        ACTION_MOVE_DOWN,
        ACTION_MOVE_UP,
        ACTION_REMOVE,
        ATTENDANCE_ABSENT,
        ATTENDANCE_ATTENDED,
        ATTENDANCE_UNEVALUATED_LABEL,
        EMPTY_PARTICIPANTS,
        EMPTY_VALUE,
        GROUP_INFORMING,
        GROUP_PARTICIPANTS,
        GROUP_REPRESENTATION,
        PARTICIPANT_ATTENDANCE_LABELS,
        PARTICIPANT_COLUMN_HEADERS,
        PARTICIPANT_IDENTITY_CONFLICT_MESSAGE,
        PARTICIPANT_NAME_REQUIRED_MESSAGE,
        PARTICIPANT_ROLE_LABELS,
        PARTICIPANT_ROLE_ORDER,
        PARTICIPANT_ROLE_INSPECTOR,
        PARTICIPANT_ROLE_OTHER,
        PARTICIPANT_SOURCE_PERSON,
        PARTICIPANT_SOURCE_THP_WORKER,
        PLANNED_NO_LABEL,
        PLANNED_YES_LABEL,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
        TABLE_PARTICIPANTS,
    )
    from moduly.statni_dozor.modely.state_supervision_participant_draft import (
        StateSupervisionParticipantDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
        state_supervision_participant_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        KEEP_EXISTING,
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
    from moduly.statni_dozor.ui.state_supervision_participant_dialog import (
        StateSupervisionParticipantDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab


def _count(table: str) -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _active_names(supervision_id: int) -> list[str]:
    rows = state_supervision_participant_service.list_participants(supervision_id)
    return [str(row.name_snapshot) for row in rows]


class StateSupervisionParticipantsUi3c1TestCase(unittest.TestCase):
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
        self.person = person_service.create_person(
            first_name="Jana",
            last_name=f"Osoba-{self.marker}",
        )
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
    ) -> StateSupervisionParticipantDraft:
        payload = {
            "role": PARTICIPANT_ROLE_INSPECTOR,
            "name_snapshot": f"Účastník {self.marker}",
        }
        payload.update(fields)
        draft = StateSupervisionParticipantDraft(**payload)
        dialog._participant_drafts.append(draft)
        dialog._refresh_participants_table(select_key=draft.client_key)
        dialog._editor.refresh_dirty()
        return draft

    def test_01_four_tabs_group_on_first_tab_columns_and_buttons(self) -> None:
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
        self.assertEqual(dialog.minimumWidth(), 640)
        self.assertEqual(dialog.minimumHeight(), 480)
        first = dialog.tabs.widget(0)
        groups = [box.title() for box in first.findChildren(QGroupBox)]
        self.assertIn(GROUP_PARTICIPANTS, groups)
        self.assertIn(GROUP_INFORMING, groups)
        self.assertIn(GROUP_REPRESENTATION, groups)
        self.assertGreater(
            groups.index(GROUP_PARTICIPANTS),
            groups.index(GROUP_REPRESENTATION),
        )
        self.assertGreater(
            groups.index(GROUP_REPRESENTATION),
            groups.index(GROUP_INFORMING),
        )
        second_groups = [
            box.title() for box in dialog.tabs.widget(1).findChildren(QGroupBox)
        ]
        self.assertNotIn(GROUP_PARTICIPANTS, second_groups)
        self.assertEqual(dialog.participants_empty_label.text(), EMPTY_PARTICIPANTS)
        self.assertFalse(dialog.participants_empty_label.isHidden())
        self.assertEqual(
            [
                dialog.participants_table.horizontalHeaderItem(i).text()
                for i in range(7)
            ],
            PARTICIPANT_COLUMN_HEADERS,
        )
        self.assertEqual(dialog.participants_table.columnCount(), 7)
        self.assertEqual(
            dialog.participants_table.textElideMode(),
            Qt.TextElideMode.ElideRight,
        )
        self.assertFalse(dialog.participants_table.isSortingEnabled())
        self.assertEqual(dialog.add_participant_btn.text(), ACTION_ADD)
        self.assertEqual(dialog.edit_participant_btn.text(), ACTION_EDIT)
        self.assertEqual(dialog.remove_participant_btn.text(), ACTION_REMOVE)
        self.assertEqual(dialog.move_participant_up_btn.text(), ACTION_MOVE_UP)
        self.assertEqual(dialog.move_participant_down_btn.text(), ACTION_MOVE_DOWN)
        self.assertTrue(dialog.add_participant_btn.isEnabled())
        self.assertFalse(dialog.edit_participant_btn.isEnabled())
        self.assertFalse(dialog.remove_participant_btn.isEnabled())
        self.assertFalse(dialog.move_participant_up_btn.isEnabled())
        self.assertFalse(dialog.move_participant_down_btn.isEnabled())
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(source.count("self.tabs.addTab("), 5)
        self.assertNotIn("TAB_PARTICIPANTS", source)
        self.assertIn("doubleClicked.connect(self._edit_selected_participant)", source)
        self.assertNotIn("save_button.setEnabled(True)", source)
        dialog.close()

    def test_02_add_edit_cancel_noop_and_empty_state(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")

        created = StateSupervisionParticipantDraft(
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Ing. Externí",
        )
        with patch(
            "moduly.statni_dozor.ui.state_supervision_participant_dialog."
            "exec_participant_dialog",
            return_value=created,
        ):
            dialog._add_participant()
        self.assertEqual(len(dialog._active_participants()), 1)
        self.assertIsNone(dialog._active_participants()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog.participants_empty_label.isHidden())
        self.assertEqual(_count(TABLE_PARTICIPANTS), 0)
        self.assertTrue(dialog.edit_participant_btn.isEnabled())

        with patch(
            "moduly.statni_dozor.ui.state_supervision_participant_dialog."
            "exec_participant_dialog",
            return_value=None,
        ):
            dialog._add_participant()
        self.assertEqual(len(dialog._active_participants()), 1)

        current = dialog._active_participants()[0]
        with patch(
            "moduly.statni_dozor.ui.state_supervision_participant_dialog."
            "exec_participant_dialog",
            return_value=replace(current, name_snapshot="Ing. Upravený"),
        ):
            dialog._edit_selected_participant()
        self.assertEqual(dialog._active_participants()[0].name_snapshot, "Ing. Upravený")
        self.assertIsNone(dialog._active_participants()[0].id)
        self.assertEqual(_count(TABLE_PARTICIPANTS), 0)

        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.is_dirty())
        with patch(
            "moduly.statni_dozor.ui.state_supervision_participant_dialog."
            "exec_participant_dialog",
            return_value=replace(dialog._active_participants()[0]),
        ):
            dialog._edit_selected_participant()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

    def test_03_remove_new_vs_existing_soft_delete_and_move(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"KHS {self.marker}"
        )
        existing = state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Existující",
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self._add_working(dialog, name_snapshot="Nový pracovní")
        self.assertEqual(len(dialog._active_participants()), 2)

        dialog._select_participant_key(dialog._active_participants()[1].client_key)
        dialog._remove_selected_participant()
        self.assertEqual(
            [row.name_snapshot for row in dialog._active_participants()],
            ["Existující"],
        )
        self.assertEqual(
            len(state_supervision_participant_service.list_participants(record.id)),
            1,
        )

        dialog._select_participant_key(dialog._active_participants()[0].client_key)
        dialog._remove_selected_participant()
        self.assertEqual(dialog._active_participants(), [])
        kept = [item for item in dialog._participant_drafts if item.id == existing.id]
        self.assertEqual(len(kept), 1)
        self.assertFalse(kept[0].active)
        self.assertEqual(
            len(
                state_supervision_participant_service.list_participants(
                    record.id, include_inactive=True
                )
            ),
            1,
        )
        dialog.close()

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Move {self.marker}")
        self._add_working(dialog, name_snapshot="A-první")
        second = self._add_working(dialog, name_snapshot="B-druhý")
        dialog._select_participant_key(second.client_key)
        dialog._move_selected_participant(-1)
        self.assertEqual(
            [row.name_snapshot for row in dialog._active_participants()],
            ["B-druhý", "A-první"],
        )
        self.assertTrue(dialog._editor.is_dirty())
        dialog.participants_table.clearSelection()
        dialog.participants_table.setCurrentCell(-1, -1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

    def test_04_catalog_external_roles_planned_attendance_and_snapshot(self) -> None:
        before_persons = _count("persons")
        before_workers = _count("thp_workers")
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        self._add_working(
            dialog,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Ing. Externí",
            organization_snapshot="OIP Praha",
            contact_note="externi@example.test",
            planned=True,
            attendance_status=None,
        )
        self._add_working(
            dialog,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot=self.person.display_name,
            source_type=PARTICIPANT_SOURCE_PERSON,
            source_id=self.person.id,
            planned=False,
            attendance_status=ATTENDANCE_ATTENDED,
        )
        self._add_working(
            dialog,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot=self.worker.display_name,
            source_type=PARTICIPANT_SOURCE_THP_WORKER,
            source_id=self.worker.id,
            planned=True,
            attendance_status=ATTENDANCE_ABSENT,
            note="",
        )
        self.assertEqual(
            dialog.participants_table.item(0, 0).text(),
            PARTICIPANT_ROLE_LABELS[PARTICIPANT_ROLE_INSPECTOR],
        )
        self.assertEqual(dialog.participants_table.item(0, 3).text(), PLANNED_YES_LABEL)
        self.assertEqual(
            dialog.participants_table.item(0, 4).text(),
            ATTENDANCE_UNEVALUATED_LABEL,
        )
        self.assertEqual(dialog.participants_table.item(1, 3).text(), PLANNED_NO_LABEL)
        self.assertEqual(
            dialog.participants_table.item(1, 4).text(),
            PARTICIPANT_ATTENDANCE_LABELS[ATTENDANCE_ATTENDED],
        )
        self.assertEqual(
            dialog.participants_table.item(2, 4).text(),
            PARTICIPANT_ATTENDANCE_LABELS[ATTENDANCE_ABSENT],
        )
        self.assertEqual(dialog.participants_table.item(2, 6).text(), EMPTY_VALUE)
        self.assertIn("OIP Praha", dialog.participants_table.item(0, 2).toolTip())

        for index, role in enumerate(PARTICIPANT_ROLE_ORDER):
            extra = StateSupervisionEditorDialog()
            extra.authority_combo.setCurrentText(f"Role {self.marker}-{index}")
            self._add_working(
                extra,
                role=role,
                name_snapshot=f"Role {role}",
            )
            self.assertEqual(
                extra.participants_table.item(0, 0).text(),
                PARTICIPANT_ROLE_LABELS[role],
            )
            extra.close()

        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("persons"), before_persons)
        self.assertEqual(_count("thp_workers"), before_workers)
        loaded = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        rows = loaded._active_participants()
        self.assertEqual(rows[0].source_type, None)
        self.assertEqual(rows[0].name_snapshot, "Ing. Externí")
        self.assertEqual(rows[1].source_type, PARTICIPANT_SOURCE_PERSON)
        self.assertEqual(rows[1].source_id, self.person.id)
        self.assertEqual(rows[2].source_type, PARTICIPANT_SOURCE_THP_WORKER)
        self.assertEqual(rows[2].source_id, self.worker.id)
        loaded.close()
        dialog.close()

        missing = StateSupervisionParticipantDialog(
            draft=StateSupervisionParticipantDraft(
                role=PARTICIPANT_ROLE_INSPECTOR,
                source_type=PARTICIPANT_SOURCE_PERSON,
                source_id=9_999_999,
                name_snapshot="Ing. Zmizelá",
            )
        )
        self.assertEqual(missing.person_selector.currentText(), "Ing. Zmizelá")
        self.assertFalse(missing.external_name_edit.isEnabled())
        missing.close()

    def test_05_dirty_add_edit_remove_order_tab_and_revert(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"DÚ {self.marker}"
        )
        state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Původní A",
        )
        state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_OTHER,
            name_snapshot="Původní B",
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        baseline = dialog.get_snapshot()
        self.assertIsInstance(dialog._editor, EditorDialogController)

        added = self._add_working(dialog, name_snapshot="Nový")
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog._participant_drafts = [
            item
            for item in dialog._participant_drafts
            if item.client_key != added.client_key
        ]
        dialog._refresh_participants_table()
        dialog._editor.refresh_dirty()
        self.assertEqual(dialog.get_snapshot(), baseline)
        self.assertFalse(dialog._editor.save_button.isEnabled())

        current = dialog._active_participants()[0]
        current.name_snapshot = "Původní A upraveno"
        dialog._refresh_participants_table()
        dialog._editor.refresh_dirty()
        self.assertTrue(dialog._editor.is_dirty())
        current.name_snapshot = "Původní A"
        dialog._refresh_participants_table()
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog._select_participant_key(dialog._active_participants()[1].client_key)
        dialog._move_selected_participant(-1)
        self.assertTrue(dialog._editor.is_dirty())
        dialog._select_participant_key(dialog._active_participants()[0].client_key)
        dialog._move_selected_participant(1)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())

        dialog.tabs.setCurrentIndex(3)
        dialog.tabs.setCurrentIndex(0)
        dialog.participants_table.selectRow(0)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_06_persist_bundle_ids_order_and_second_save(self) -> None:
        before = _count("state_supervisions")
        before_p = _count(TABLE_PARTICIPANTS)
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OBÚ {self.marker}")
        dialog._document_drafts.append(
            StateSupervisionRequiredDocumentDraft(title="Doklad A")
        )
        dialog._refresh_documents_table()
        dialog._timeline_drafts.append(
            StateSupervisionTimelineItemDraft(title="Zahájení")
        )
        dialog._refresh_timeline_table()
        self._add_working(dialog, name_snapshot="První")
        self._add_working(dialog, name_snapshot="Druhý")
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count("state_supervisions"), before + 1)
        self.assertIsNotNone(dialog.supervision_id)
        self.assertTrue(
            all(item.id is not None for item in dialog._active_participants())
        )
        self.assertEqual(_active_names(dialog.supervision_id), ["První", "Druhý"])
        self.assertEqual(_count(TABLE_PARTICIPANTS), before_p + 2)
        self.assertFalse(dialog._editor.is_dirty())

        dialog._active_participants()[0].name_snapshot = "První upraveno"
        self._add_working(dialog, name_snapshot="Třetí")
        self.assertTrue(self._save(dialog))
        self.assertEqual(
            _active_names(dialog.supervision_id),
            ["První upraveno", "Druhý", "Třetí"],
        )
        self.assertEqual(_count(TABLE_PARTICIPANTS), before_p + 3)

        dialog._select_participant_key(dialog._active_participants()[1].client_key)
        dialog._remove_selected_participant()
        self.assertTrue(self._save(dialog))
        self.assertEqual(
            _active_names(dialog.supervision_id),
            ["První upraveno", "Třetí"],
        )
        history = state_supervision_participant_service.list_participants(
            dialog.supervision_id, include_inactive=True
        )
        self.assertEqual(len(history), 3)
        self.assertEqual(sum(1 for row in history if row.active), 2)
        self.assertFalse(
            state_supervision_participant_service.get_participant(
                next(row.id for row in history if row.name_snapshot == "Druhý")
            ).active
        )

        self.assertFalse(dialog._editor.is_dirty())
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count(TABLE_PARTICIPANTS), before_p + 3)
        self.assertEqual(len(_active_names(dialog.supervision_id)), 2)

        reopened = StateSupervisionEditorDialog(supervision_id=dialog.supervision_id)
        self.assertEqual(
            [row.name_snapshot for row in reopened._active_participants()],
            ["První upraveno", "Třetí"],
        )
        reopened.close()
        dialog.close()

    def test_07_wrapper_keep_existing_and_empty_collection(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Keep {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Doklad"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Průběh"
        )
        row = state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Účastník",
        )

        state_supervision_service.save_supervision_with_documents(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=[
                StateSupervisionRequiredDocumentDraft(
                    id=state_supervision_required_document_service.list_documents(
                        record.id
                    )[0].id,
                    title="Doklad",
                )
            ],
        )
        self.assertEqual(_active_names(record.id), ["Účastník"])
        self.assertTrue(
            state_supervision_participant_service.get_participant(row.id).active
        )

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=KEEP_EXISTING,
            timeline_items=KEEP_EXISTING,
            participants=KEEP_EXISTING,
        )
        self.assertEqual(_active_names(record.id), ["Účastník"])

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            documents=KEEP_EXISTING,
            timeline_items=KEEP_EXISTING,
        )
        self.assertEqual(_active_names(record.id), ["Účastník"])

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": f"Keep {self.marker} upraveno"},
            participants=[],
        )
        self.assertEqual(_active_names(record.id), [])
        history = state_supervision_participant_service.list_participants(
            record.id, include_inactive=True
        )
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0].active)

    def test_08_atomic_rollback_and_single_commit(self) -> None:
        before_s = _count("state_supervisions")
        before_d = _count("state_supervision_required_documents")
        before_t = _count("state_supervision_timeline_items")
        before_p = _count(TABLE_PARTICIPANTS)
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"OIP {self.marker}"},
                documents=[StateSupervisionRequiredDocumentDraft(title="Doklad")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="Úkon")],
                participants=[
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="Platný",
                    ),
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="  ",
                    ),
                ],
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)
        self.assertEqual(_count(TABLE_PARTICIPANTS), before_p)

        existing = state_supervision_service.create_supervision(
            authority_name=f"Původní {self.marker}"
        )
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=existing.id,
                fields={"authority_name": f"Změna {self.marker}"},
                documents=[StateSupervisionRequiredDocumentDraft(title="Doklad")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="Úkon")],
                participants=[
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="  ",
                    )
                ],
            )
        self.assertEqual(
            state_supervision_service.get_supervision(existing.id).authority_name,
            f"Původní {self.marker}",
        )
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_timeline_item_service.list_timeline_items(existing.id),
            [],
        )

        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Rollback {self.marker}")
        self._add_working(dialog, name_snapshot="Pracovní")
        with patch.object(
            state_supervision_participant_service,
            "save_participant_batch",
            side_effect=StateSupervisionError("umělá chyba účastníka"),
        ):
            with patch.object(QMessageBox, "warning"):
                self.assertFalse(self._save(dialog))
        self.assertIsNone(dialog.supervision_id)
        self.assertIsNone(dialog._active_participants()[0].id)
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

        source = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        self.assertIn("save_participant_batch", source)

        commits = []
        original = Session.commit

        def _spy(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", _spy):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Commit {self.marker}"},
                documents=[StateSupervisionRequiredDocumentDraft(title="A")],
                timeline_items=[StateSupervisionTimelineItemDraft(title="X")],
                participants=[
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="Y",
                    )
                ],
            )
        self.assertEqual(len(commits), 1)

    def test_09_no_write_on_open_and_agenda_four_tabs(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Open {self.marker}"
        )
        state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Načíst",
        )
        before_s = _count("state_supervisions")
        before_p = _count(TABLE_PARTICIPANTS)
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.tabs.setCurrentIndex(1)
        dialog.close()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count(TABLE_PARTICIPANTS), before_p)

        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        self.assertIsInstance(page.state_supervision_tab, StateSupervisionTab)
        page.close()

    def test_10_subdialog_identity_rules_and_window_modal(self) -> None:
        sub = StateSupervisionParticipantDialog(is_new=True)
        self.assertEqual(sub.windowModality(), Qt.WindowModality.WindowModal)
        self.assertIsInstance(sub.person_selector, MeetingPersonTypeahead)
        self.assertEqual(
            [sub.role_combo.itemText(i) for i in range(sub.role_combo.count())],
            [PARTICIPANT_ROLE_LABELS[role] for role in PARTICIPANT_ROLE_ORDER],
        )
        self.assertEqual(
            [sub.attendance_combo.itemText(i) for i in range(sub.attendance_combo.count())],
            [
                ATTENDANCE_UNEVALUATED_LABEL,
                PARTICIPANT_ATTENDANCE_LABELS[ATTENDANCE_ATTENDED],
                PARTICIPANT_ATTENDANCE_LABELS[ATTENDANCE_ABSENT],
            ],
        )
        with patch.object(QMessageBox, "warning") as warning:
            sub._on_save()
            warning.assert_called()
            self.assertIn(PARTICIPANT_NAME_REQUIRED_MESSAGE, warning.call_args.args)
        self.assertIsNone(sub.result_draft)

        sub.person_selector.set_ref(
            {
                "source_type": PARTICIPANT_SOURCE_PERSON,
                "source_id": int(self.person.id),
            }
        )
        self.assertFalse(sub.external_name_edit.isEnabled())
        self.assertEqual(sub.external_name_edit.text(), "")
        sub.person_selector.blockSignals(True)
        sub.external_name_edit.setEnabled(True)
        sub.external_name_edit.setText("Jiné ruční jméno")
        sub.person_selector.blockSignals(False)
        with patch.object(QMessageBox, "warning") as warning:
            sub._on_save()
            warning.assert_called()
            self.assertIn(PARTICIPANT_IDENTITY_CONFLICT_MESSAGE, warning.call_args.args)
        self.assertIsNone(sub.result_draft)

        sub.person_selector.clear_selection()
        self.assertTrue(sub.external_name_edit.isEnabled())
        sub.external_name_edit.setText("Ing. Externí")
        sub._on_save()
        self.assertEqual(sub.result_draft.name_snapshot, "Ing. Externí")
        self.assertIsNone(sub.result_draft.source_type)
        self.assertIsNone(sub.result_draft.source_id)
        sub.close()

        catalog = StateSupervisionParticipantDialog(is_new=True)
        catalog.person_selector.set_ref(
            {
                "source_type": PARTICIPANT_SOURCE_THP_WORKER,
                "source_id": int(self.worker.id),
            }
        )
        catalog._on_save()
        self.assertEqual(catalog.result_draft.source_type, PARTICIPANT_SOURCE_THP_WORKER)
        self.assertEqual(catalog.result_draft.source_id, int(self.worker.id))
        self.assertIn("Petr", catalog.result_draft.name_snapshot or "")
        catalog.close()

        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("save_supervision_bundle", source)
        self.assertIn("participants=", source)
        self.assertNotIn("DELETE FROM", source)
        self.assertEqual(source.count("create_supervision("), 0)
        dialog_source = inspect.getsource(StateSupervisionParticipantDialog)
        self.assertIn("MeetingPersonTypeahead", dialog_source)
        self.assertNotIn("PersonSelector(", dialog_source)


if __name__ == "__main__":
    unittest.main()
