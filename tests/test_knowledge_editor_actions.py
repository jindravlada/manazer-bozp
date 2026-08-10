import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QSizePolicy

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)

_STORAGE_BOOTSTRAPPED = False

_PROCESS_ID = "urazy_mimo_udalosti"
_KNOWLEDGE_FILE = "urazy_mimo_udalosti.json"


def _bootstrap_audity_storage() -> None:
    global _STORAGE_BOOTSTRAPPED
    if not _STORAGE_BOOTSTRAPPED:
        _HOME_PATCHER.start()
        _STORAGE_BOOTSTRAPPED = True

    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import moduly.audity.sluzby.audit_knowledge_editor_service as editor_module
    import moduly.audity.sluzby.audit_knowledge_service as knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(knowledge_module)
    importlib.reload(editor_module)


def _import_audity_services() -> None:
    global editable_catalog_service
    global audit_knowledge_editor_service
    global AudityKnowledgeEditorDialog
    global KNOWLEDGE_EDITOR_SAVED_MESSAGE

    from core.services.editable_catalog_service import editable_catalog_service
    from core.widgets.knowledge_editor_actions import (
        KNOWLEDGE_EDITOR_SAVED_MESSAGE,
        KNOWLEDGE_EDITOR_UNSAVED_MESSAGE,
    )
    from moduly.audity.sluzby.audit_knowledge_editor_service import (
        audit_knowledge_editor_service,
    )
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog

    globals()["KNOWLEDGE_EDITOR_UNSAVED_MESSAGE"] = KNOWLEDGE_EDITOR_UNSAVED_MESSAGE


_bootstrap_audity_storage()
_import_audity_services()


class AudityKnowledgeEditorActionsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _bootstrap_audity_storage()
        _import_audity_services()
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _bootstrap_audity_storage()
        _import_audity_services()
        audit_knowledge_editor_service.ensure_user_catalogs()
        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

        self._knowledge_path = audit_knowledge_service.audity_dir / _KNOWLEDGE_FILE
        bundled = editable_catalog_service.bundled_path(f"audity/{_KNOWLEDGE_FILE}")
        shutil.copy2(bundled, self._knowledge_path)
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_footer_button_labels(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertEqual(dialog._apply_btn.text(), "Použít")
        self.assertEqual(dialog._save_close_btn.text(), "Uložit a zavřít")
        self.assertEqual(dialog._close_btn.text(), "Zavřít")

    def test_footer_layout_stable_on_open(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertEqual(dialog._status_label.text(), "")
        self.assertFalse(dialog._status_label.isHidden())
        for button in (dialog._apply_btn, dialog._save_close_btn, dialog._close_btn):
            self.assertEqual(
                button.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Fixed,
            )
            self.assertFalse(button.icon().isNull())

    def test_footer_status_cycle(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        dialog.process_editor._nazev_edit.setText("Editor test — cyklus stavu")
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_UNSAVED_MESSAGE)
        self.assertTrue(dialog._modified)

        dialog._apply_changes()
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        self.assertFalse(dialog._modified)

        dialog.process_editor._nazev_edit.setText("Editor test — další změna")
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_UNSAVED_MESSAGE)

        apply_width = dialog._apply_btn.width()
        dialog._apply_changes()
        self.assertEqual(dialog._apply_btn.width(), apply_width)

    def test_apply_saves_and_keeps_dialog_open(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        dialog.process_editor._nazev_edit.setText("Editor test — Použít")
        dialog._apply_changes()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        self.assertFalse(dialog._modified)

    def test_save_and_close_accepts_dialog(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        dialog.process_editor._nazev_edit.setText("Editor test — Uložit a zavřít")
        dialog._save_and_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog._modified)

    def test_close_without_changes_rejects_immediately(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))

        with patch.object(QMessageBox, "question") as mock_question:
            dialog._request_close()

        mock_question.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_close_with_changes_prompts_and_cancel_keeps_open(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Editor test — neuložené")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="cancel",
        ):
            dialog._request_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(dialog._modified)

    def test_close_with_changes_yes_saves_and_closes(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Editor test — Ano uložit")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="save",
        ):
            dialog._request_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog._modified)

    def test_close_with_changes_no_discards_and_closes(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Editor test — Ne zavřít")

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="discard",
        ):
            dialog._request_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog._modified)

    @patch("moduly.audity.ui.audity_knowledge_editor_dialog.QMessageBox.warning")
    @patch(
        "moduly.audity.ui.audity_knowledge_editor_dialog.audit_knowledge_editor_service.save_process_metadata",
        return_value=["Editor test — simulovaná chyba uložení."],
    )
    def test_apply_shows_error_on_failure(self, _mock_save, mock_warning) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Editor test — chyba uložení")

        dialog._apply_changes()

        mock_warning.assert_called_once()
        self.assertEqual(dialog._status_label.text(), "")
        self.assertTrue(dialog._has_unsaved_changes())


class ProverkyKnowledgeEditorActionsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _bootstrap_audity_storage()
        cls._app = QApplication.instance() or QApplication([])

        import core.services.storage_service as storage_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()

        import core.services.editable_catalog_service as editable_catalog_module
        import moduly.proverky.sluzby.proverky_knowledge_service as proverky_knowledge_module

        importlib.reload(editable_catalog_module)
        importlib.reload(proverky_knowledge_module)
        proverky_knowledge_module.proverky_knowledge_service.ensure_catalogs()

        from moduly.proverky.constants import (
            KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
            KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
        )
        from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
            ProverkyKnowledgeSectionEditDialog,
        )

        cls._dialog_cls = ProverkyKnowledgeSectionEditDialog
        cls._area_id = KNOWLEDGE_EDITOR_DEFAULT_AREA_ID
        cls._section_id = KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID

    def _create_dialog(self):
        return self._dialog_cls(
            area_id=self._area_id,
            section_id=self._section_id,
        )

    def test_footer_button_labels(self) -> None:
        dialog = self._create_dialog()
        self.assertEqual(dialog._apply_btn.text(), "Použít")
        self.assertEqual(dialog._save_close_btn.text(), "Uložit a zavřít")
        self.assertEqual(dialog._close_btn.text(), "Zavřít")

    def test_footer_layout_stable_on_open(self) -> None:
        dialog = self._create_dialog()
        self.assertEqual(dialog._status_label.text(), "")
        self.assertFalse(dialog._status_label.isHidden())
        for button in (dialog._apply_btn, dialog._save_close_btn, dialog._close_btn):
            self.assertEqual(
                button.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Fixed,
            )
            self.assertFalse(button.icon().isNull())

    def test_modified_flag_and_status_on_edit(self) -> None:
        dialog = self._create_dialog()
        self.assertFalse(dialog._modified)
        self.assertEqual(dialog._status_label.text(), "")
        dialog._nazev_edit.setText("Editor test — modified flag")
        self.assertTrue(dialog._modified)
        self.assertEqual(dialog._status_label.text(), "● Neuložené změny")

    def test_apply_saves_and_keeps_dialog_open(self) -> None:
        dialog = self._create_dialog()
        dialog._nazev_edit.setText("Editor test — Prověrky Použít")
        dialog._apply_changes()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        self.assertFalse(dialog._modified)

    def test_save_and_close_accepts_dialog(self) -> None:
        dialog = self._create_dialog()
        dialog._nazev_edit.setText("Editor test — Prověrky Uložit a zavřít")
        dialog._save_and_close()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_footer_status_after_save_and_reedit(self) -> None:
        dialog = self._create_dialog()
        dialog._nazev_edit.setText("Editor test — Prověrky stav")
        dialog._apply_changes()
        self.assertEqual(dialog._status_label.text(), "✓ Uloženo.")
        dialog._popis_edit.setPlainText("Další úprava")
        self.assertEqual(dialog._status_label.text(), "● Neuložené změny")


if __name__ == "__main__":
    unittest.main()
