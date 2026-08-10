"""UX-DIALOG-BUTTONS-AUDIT-2: sjednocení dialogů Auditů dle standardu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ux-dialog-buttons-audit-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import (
        EDITOR_CANCEL_LABEL,
        EDITOR_CLOSE_LABEL,
        EDITOR_SAVE_LABEL,
    )
    from core.widgets.knowledge_editor_actions import (
        KNOWLEDGE_EDITOR_APPLY_LABEL,
        KNOWLEDGE_EDITOR_CLOSE_LABEL,
        KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL,
    )
    from moduly.audity.sluzby.audit_program_service import MissingAuditableWorkplace
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_program_create_dialog import AuditProgramCreateDialog
    from moduly.audity.ui.audit_program_supplement_workplaces_dialog import (
        AuditProgramSupplementWorkplacesDialog,
    )
    from moduly.audity.ui.audity_knowledge_assertion_dialog import (
        AudityKnowledgeAssertionDialog,
    )
    from moduly.audity.ui.audity_knowledge_editor_dialog import (
        AudityKnowledgeEditorDialog,
    )


class UxDialogButtonsAudit2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _dirty_audit_dialog(self, title: str) -> AuditDialog:
        audit = audit_service.create_audit(title=title, workplace_name="X")
        dialog = AuditDialog(audit=audit)
        combo = dialog.spis_widget.type_combo
        if combo.count() > 1:
            combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())
        else:
            dialog.spis_widget.year_combo.setCurrentIndex(
                max(0, dialog.spis_widget.year_combo.count() - 1)
            )
        self.assertTrue(dialog._editor.is_dirty())
        return dialog

    def test_new_audit_shows_save_and_cancel(self) -> None:
        dialog = AuditDialog()
        self.assertEqual(dialog._editor.save_button.text(), EDITOR_SAVE_LABEL)
        self.assertEqual(dialog._editor.close_button.text(), EDITOR_CANCEL_LABEL)
        dialog.close()

    def test_existing_audit_shows_save_and_close(self) -> None:
        audit = audit_service.create_audit(title="UX2 audit", workplace_name="X")
        dialog = AuditDialog(audit=audit)
        self.assertEqual(dialog._editor.save_button.text(), EDITOR_SAVE_LABEL)
        self.assertEqual(dialog._editor.close_button.text(), EDITOR_CLOSE_LABEL)
        dialog.close()

    def test_audit_close_without_dirty_skips_prompt(self) -> None:
        audit = audit_service.create_audit(title="Čistý", workplace_name="X")
        dialog = AuditDialog(audit=audit)
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
        ) as prompt:
            self.assertTrue(dialog._editor.request_close())
            prompt.assert_not_called()
        dialog.close()

    def test_audit_close_with_dirty_shows_prompt(self) -> None:
        dialog = self._dirty_audit_dialog("Špinavý")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog._editor.request_close())
            prompt.assert_called_once()
        dialog.close()

    def test_audit_dirty_prompt_save_accepts(self) -> None:
        dialog = self._dirty_audit_dialog("Uložit z promptu")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ), patch.object(
            dialog.commission_widget, "validate", return_value=(True, "")
        ):
            self.assertTrue(dialog._editor.request_close())
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
        dialog.close()

    def test_audit_dirty_prompt_discard_allows_close(self) -> None:
        dialog = self._dirty_audit_dialog("Zahodit")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        dialog.close()

    def test_audit_uses_editor_dialog_controller_for_close_paths(self) -> None:
        """Zavřít / X / Escape jdou přes EDC (eventFilter + close button)."""
        dialog = AuditDialog()
        self.assertIsNotNone(dialog._editor)
        self.assertTrue(dialog._editor.close_button is not None)
        dialog.close()

    def test_assertion_new_vs_edit_labels(self) -> None:
        new_dlg = AudityKnowledgeAssertionDialog()
        self.assertEqual(new_dlg._editor.close_button.text(), EDITOR_CANCEL_LABEL)
        new_dlg.close()

        edit_dlg = AudityKnowledgeAssertionDialog(
            assertion={
                "id": "t1",
                "text": "Text",
                "popis": "",
                "zavaznost": "stredni",
                "poradi": 10,
                "aktivni": True,
            }
        )
        self.assertEqual(edit_dlg._editor.close_button.text(), EDITOR_CLOSE_LABEL)
        edit_dlg.close()

    def test_assertion_dirty_prompt(self) -> None:
        dialog = AudityKnowledgeAssertionDialog(
            assertion={
                "id": "t2",
                "text": "Původní",
                "popis": "",
                "zavaznost": "stredni",
                "poradi": 10,
                "aktivni": True,
            }
        )
        dialog._text_edit.setPlainText("Upravené")
        self.assertTrue(dialog._editor.is_dirty())
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog._editor.request_close())
            prompt.assert_called_once()
        dialog.close()

    def test_program_create_new_labels(self) -> None:
        dialog = AuditProgramCreateDialog()
        self.assertEqual(dialog._editor.save_button.text(), EDITOR_SAVE_LABEL)
        self.assertEqual(dialog._editor.close_button.text(), EDITOR_CANCEL_LABEL)
        dialog.close()

    def test_supplement_workplaces_uses_pouzit_zavrit(self) -> None:
        workplaces = (
            MissingAuditableWorkplace(
                workplace_id=1,
                workplace_name="Sklad",
                audit_interval_months=12,
            ),
        )
        dialog = AuditProgramSupplementWorkplacesDialog(workplaces=workplaces)
        self.assertEqual(dialog.use_btn.text(), "Použít")
        self.assertEqual(dialog.close_btn.text(), "Zavřít")
        dialog.close()

    def test_knowledge_editor_keeps_stay_open_footer(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertEqual(dialog._apply_btn.text(), KNOWLEDGE_EDITOR_APPLY_LABEL)
        self.assertEqual(dialog._save_close_btn.text(), KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL)
        self.assertEqual(dialog._close_btn.text(), KNOWLEDGE_EDITOR_CLOSE_LABEL)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
