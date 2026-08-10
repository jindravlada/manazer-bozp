"""UX-DIALOG-BUTTONS-AUDIT-3 – footer Editoru metodiky auditu (stay-open typ D)."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDialog

_TMP = Path(tempfile.mkdtemp(prefix="ux-dialog-buttons-audit-3-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)
_HOME_PATCHER.start()

import core.services.editable_catalog_service as editable_catalog_module
import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()
importlib.reload(editable_catalog_module)

import moduly.audity.sluzby.audit_knowledge_editor_service as editor_module
import moduly.audity.sluzby.audit_knowledge_service as knowledge_module

importlib.reload(knowledge_module)
importlib.reload(editor_module)

from core.services.editable_catalog_service import editable_catalog_service
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from core.widgets.knowledge_editor_actions import (
    KNOWLEDGE_EDITOR_APPLY_LABEL,
    KNOWLEDGE_EDITOR_CLOSE_LABEL,
    KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL,
    KNOWLEDGE_EDITOR_SAVED_MESSAGE,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_assertions_widget import _COL_VERIFICATION
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
from moduly.audity.ui.audity_page import AudityPage

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_KNOWLEDGE_FILE = "urazy_mimo_udalosti.json"


class UxDialogButtonsAudit3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / _KNOWLEDGE_FILE
        bundled = editable_catalog_service.bundled_path(f"audity/{_KNOWLEDGE_FILE}")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_audity_page_opens_real_knowledge_editor(self) -> None:
        page = AudityPage()
        with patch("moduly.audity.ui.audity_page.exec_maximized") as mock_exec:
            page.open_knowledge_editor()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args[0][0]
        self.assertIsInstance(dialog, AudityKnowledgeEditorDialog)
        self.assertEqual(dialog._apply_btn.text(), KNOWLEDGE_EDITOR_APPLY_LABEL)
        self.assertEqual(dialog._save_close_btn.text(), KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL)
        self.assertEqual(dialog._close_btn.text(), KNOWLEDGE_EDITOR_CLOSE_LABEL)

        ordered = sorted(
            (dialog._apply_btn, dialog._save_close_btn, dialog._close_btn),
            key=lambda button: button.x(),
        )
        self.assertEqual(
            [button.text() for button in ordered],
            [
                KNOWLEDGE_EDITOR_APPLY_LABEL,
                KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL,
                KNOWLEDGE_EDITOR_CLOSE_LABEL,
            ],
        )
        dialog.close()

    def test_footer_labels_match_stay_open_standard(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        dialog.show()
        self._app.processEvents()

        self.assertEqual(dialog._apply_btn.text(), "Použít")
        self.assertEqual(dialog._save_close_btn.text(), "Uložit a zavřít")
        self.assertEqual(dialog._close_btn.text(), "Zavřít")
        self.assertTrue(dialog._apply_btn.isVisible())
        self.assertTrue(dialog._save_close_btn.isVisible())
        self.assertTrue(dialog._close_btn.isVisible())
        dialog.close()

    def test_apply_saves_all_pending_and_stays_open(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("AUDIT-3 Použít draft A")
        self.assertTrue(dialog.knowledge_tree.select_node("planovani_bozp"))
        self.assertTrue(dialog._has_unsaved_changes())

        dialog._apply_changes()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog._has_unsaved_changes())
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        with self._path.open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        self.assertEqual(on_disk.get("nazev"), "AUDIT-3 Použít draft A")
        dialog.close()

    def test_save_and_close_persists_and_accepts(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("AUDIT-3 Uložit a zavřít")

        dialog._save_and_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog._has_unsaved_changes())
        with self._path.open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        self.assertEqual(on_disk.get("nazev"), "AUDIT-3 Uložit a zavřít")

    def test_close_without_changes_rejects(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes"
        ) as mock_confirm:
            dialog._request_close()

        mock_confirm.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_close_with_changes_shows_dirty_prompt(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("AUDIT-3 dirty close")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="cancel",
        ) as mock_confirm:
            dialog._request_close()

        mock_confirm.assert_called_once()
        self.assertTrue(dialog._has_unsaved_changes())
        dialog._discard_all_drafts()
        dialog.close()

    def test_window_close_with_changes_shows_dirty_prompt(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("AUDIT-3 dirty X")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="cancel",
        ) as mock_confirm:
            event = QCloseEvent()
            dialog.closeEvent(event)

        mock_confirm.assert_called_once()
        self.assertFalse(event.isAccepted())
        self.assertTrue(dialog._has_unsaved_changes())
        dialog._discard_all_drafts()
        dialog.close()

    def test_escape_with_changes_shows_dirty_prompt(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("AUDIT-3 dirty Escape")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="cancel",
        ) as mock_confirm:
            dialog.reject()

        mock_confirm.assert_called_once()
        self.assertTrue(dialog._has_unsaved_changes())
        dialog._discard_all_drafts()
        dialog.close()

    def test_verification_type_immediate_save_does_not_leave_dirty(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID))
        assertions = dialog.section_editor._assertions_widget
        self.assertGreater(assertions._table.rowCount(), 0)

        combo = assertions._table.cellWidget(0, _COL_VERIFICATION)
        self.assertIsInstance(combo, QComboBox)
        assert isinstance(combo, QComboBox)

        current = combo.currentData()
        target = (
            VERIFICATION_TYPE_TERRAIN
            if current == VERIFICATION_TYPE_DOCUMENTATION
            else VERIFICATION_TYPE_DOCUMENTATION
        )
        index = combo.findData(target)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)
        self._app.processEvents()

        self.assertFalse(dialog._has_unsaved_changes())
        dialog.close()

    def test_metadata_dirty_cleared_after_apply(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID))
        dialog.section_editor._nazev_edit.setText("AUDIT-3 oblast po Použít")
        self.assertTrue(dialog._has_unsaved_changes())

        dialog._apply_changes()

        self.assertFalse(dialog._has_unsaved_changes())
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
