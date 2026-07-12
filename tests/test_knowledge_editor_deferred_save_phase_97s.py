"""Fáze 97s – odložené ukládání změn v editorech metodik."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)
_HOME_PATCHER.start()

_PROCESS_ID = "urazy_mimo_udalosti"
_OTHER_PROCESS_ID = "planovani_bozp"
_SECTION_ID = "evidence_hlaseni_urazu"
_KNOWLEDGE_FILE = "urazy_mimo_udalosti.json"


def _bootstrap() -> None:
    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import core.database.session as session_module
    import moduly.audity.sluzby.audit_knowledge_editor_service as audity_editor_module
    import moduly.audity.sluzby.audit_knowledge_service as audity_knowledge_module
    import moduly.proverky.sluzby.proverky_knowledge_service as proverky_knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()
    importlib.reload(audity_knowledge_module)
    importlib.reload(audity_editor_module)
    importlib.reload(proverky_knowledge_module)


_bootstrap()

from core.services.editable_catalog_service import editable_catalog_service
from core.widgets.knowledge_editor_actions import (
    KNOWLEDGE_EDITOR_CANCEL_LABEL,
    KNOWLEDGE_EDITOR_DISCARD_LABEL,
    KNOWLEDGE_EDITOR_SAVE_LABEL,
    KNOWLEDGE_EDITOR_UNSAVED_MESSAGE,
    confirm_close_with_unsaved_changes,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
from moduly.proverky.constants import (
    KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
    KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog

_AREA_ID = KNOWLEDGE_EDITOR_DEFAULT_AREA_ID
_PROVERKY_SECTION_ID = KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID


class KnowledgeEditorConfirmLabelsPhase97sTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_confirm_dialog_button_labels(self) -> None:
        captured: dict[str, list[str]] = {"labels": []}

        class _FakeMessageBox:
            Icon = QMessageBox.Icon
            ButtonRole = QMessageBox.ButtonRole

            def __init__(self, parent=None):
                self._buttons: list[object] = []

            def setWindowTitle(self, *_args):
                return None

            def setText(self, *_args):
                return None

            def setIcon(self, *_args):
                return None

            def addButton(self, label, _role):
                button = object()
                self._buttons.append(button)
                captured["labels"].append(label)
                return button

            def setDefaultButton(self, *_args):
                return None

            def exec(self):
                return None

            def clickedButton(self):
                return self._buttons[-1]

        with patch(
            "core.widgets.knowledge_editor_actions.QMessageBox",
            _FakeMessageBox,
        ):
            result = confirm_close_with_unsaved_changes(None, title="Test")

        self.assertEqual(
            captured["labels"],
            [
                KNOWLEDGE_EDITOR_SAVE_LABEL,
                KNOWLEDGE_EDITOR_DISCARD_LABEL,
                KNOWLEDGE_EDITOR_CANCEL_LABEL,
            ],
        )
        self.assertEqual(result, "cancel")


class AudityDeferredSavePhase97sTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _bootstrap()
        audit_knowledge_editor_service.ensure_user_catalogs()
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

    def test_switch_process_keeps_draft_without_prompt(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Draft proces A")
        self.assertTrue(dialog._modified)
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_UNSAVED_MESSAGE)

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes"
        ) as mock_confirm:
            self.assertTrue(dialog.knowledge_tree.select_node(_OTHER_PROCESS_ID))
            mock_confirm.assert_not_called()

        self.assertIn(_PROCESS_ID, dialog._process_drafts)
        self.assertEqual(dialog._process_drafts[_PROCESS_ID]["nazev"], "Draft proces A")
        self.assertTrue(dialog._modified)

        with self._knowledge_path.open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        self.assertNotEqual(on_disk.get("nazev"), "Draft proces A")

        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        self.assertEqual(dialog.process_editor._nazev_edit.text(), "Draft proces A")
        self.assertTrue(dialog._current_dirty)

    def test_close_save_persists_drafts(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Uložit draft při zavření")
        self.assertTrue(dialog.knowledge_tree.select_node(_OTHER_PROCESS_ID))

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="save",
        ):
            dialog._request_close()

        with self._knowledge_path.open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        self.assertEqual(on_disk.get("nazev"), "Uložit draft při zavření")
        self.assertFalse(dialog._modified)
        self.assertFalse(dialog._process_drafts)

    def test_close_discard_drops_drafts(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        dialog.process_editor._nazev_edit.setText("Zahodit draft")
        self.assertTrue(dialog.knowledge_tree.select_node(_OTHER_PROCESS_ID))

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="discard",
        ):
            dialog._request_close()

        with self._knowledge_path.open(encoding="utf-8") as handle:
            on_disk = json.load(handle)
        self.assertEqual(on_disk.get("nazev"), self._original.get("nazev"))
        self.assertFalse(dialog._process_drafts)


class ProverkyDeferredSavePhase97sTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _bootstrap()
        proverky_knowledge_service.ensure_catalogs()
        area = proverky_knowledge_service.get_area_by_id(_AREA_ID)
        self.assertIsNotNone(area)
        self._path = proverky_knowledge_service.proverky_dir / area.soubor_znalosti
        bundled = editable_catalog_service.bundled_path(f"proverky/{area.soubor_znalosti}")
        shutil.copy2(bundled, self._path)
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)
        self._second_section_id = self._pick_second_section()

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _pick_second_section(self) -> str:
        sections = proverky_knowledge_service.list_sections(_AREA_ID, include_inactive=True)
        for section in sections:
            section_id = str(section.get("id") or "").strip()
            if section_id and section_id != _PROVERKY_SECTION_ID:
                return section_id
        self.fail("Potřebuji alespoň dvě sekce v oblasti pro test přepnutí.")

    def _nazev_on_disk(self, section_id: str) -> str:
        section = proverky_knowledge_service.get_section(_AREA_ID, section_id)
        self.assertIsNotNone(section)
        return str(section.get("nazev") or "")

    def test_switch_section_keeps_draft_without_prompt(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, _PROVERKY_SECTION_ID)
        )
        original = dialog._section_editor._nazev_edit.text()
        dialog._section_editor._nazev_edit.setText("Draft sekce A")
        self.assertTrue(dialog._modified)

        with patch(
            "moduly.proverky.ui.proverky_knowledge_editor_dialog.confirm_close_with_unsaved_changes"
        ) as mock_confirm:
            self.assertTrue(
                dialog.knowledge_tree.select_node(_AREA_ID, self._second_section_id)
            )
            mock_confirm.assert_not_called()

        key = (_AREA_ID, _PROVERKY_SECTION_ID)
        self.assertIn(key, dialog._drafts)
        self.assertEqual(dialog._drafts[key]["nazev"], "Draft sekce A")
        self.assertEqual(self._nazev_on_disk(_PROVERKY_SECTION_ID), original)
        self.assertTrue(dialog._modified)

        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, _PROVERKY_SECTION_ID)
        )
        self.assertEqual(dialog._section_editor._nazev_edit.text(), "Draft sekce A")
        self.assertTrue(dialog._section_editor.is_modified)

    def test_close_save_persists_drafts(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, _PROVERKY_SECTION_ID)
        )
        dialog._section_editor._nazev_edit.setText("Uložit draft sekce")
        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, self._second_section_id)
        )

        with patch(
            "moduly.proverky.ui.proverky_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="save",
        ):
            dialog._request_close()

        self.assertEqual(self._nazev_on_disk(_PROVERKY_SECTION_ID), "Uložit draft sekce")
        self.assertFalse(dialog._drafts)
        self.assertFalse(dialog._modified)

    def test_close_discard_drops_drafts(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, _PROVERKY_SECTION_ID)
        )
        original = self._nazev_on_disk(_PROVERKY_SECTION_ID)
        dialog._section_editor._nazev_edit.setText("Zahodit draft sekce")
        self.assertTrue(
            dialog.knowledge_tree.select_node(_AREA_ID, self._second_section_id)
        )

        with patch(
            "moduly.proverky.ui.proverky_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="discard",
        ):
            dialog._request_close()

        self.assertEqual(self._nazev_on_disk(_PROVERKY_SECTION_ID), original)
        self.assertFalse(dialog._drafts)


if __name__ == "__main__":
    unittest.main()
