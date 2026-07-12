"""Fáze 97c – editor metodiky prověrek + vazba na řídicí proces."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplitter

_TMP = Path(tempfile.mkdtemp())


def _bootstrap() -> None:
    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import core.database.session as session_module
    import moduly.proverky.sluzby.proverky_knowledge_service as knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()
    importlib.reload(knowledge_module)


with patch.object(Path, "home", return_value=_TMP):
    _bootstrap()

from core.services.editable_catalog_service import editable_catalog_service
from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.proverky.constants import (
    KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
    KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
    KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY,
    KNOWLEDGE_EDITOR_SELECT_SECTION_HINT,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog
from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
    ProverkyKnowledgeSectionEditDialog,
)

_AREA_ID = KNOWLEDGE_EDITOR_DEFAULT_AREA_ID
_SECTION_ID = KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID
_SECOND_SECTION_ID = "lekarnicka"  # may equal default; will pick another if needed


class ProverkyKnowledgeEditorPhase97cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        with patch.object(Path, "home", return_value=_TMP):
            _bootstrap()

        proverky_knowledge_service.ensure_catalogs()
        area = proverky_knowledge_service.get_area_by_id(_AREA_ID)
        self.assertIsNotNone(area)
        self._path = proverky_knowledge_service.proverky_dir / area.soubor_znalosti
        bundled = editable_catalog_service.bundled_path(f"proverky/{area.soubor_znalosti}")
        shutil.copy2(bundled, self._path)
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._process = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            requirement_summary="Testovací proces",
        )
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
            if section_id and section_id != _SECTION_ID:
                return section_id
        return _SECTION_ID

    def _section_from_file(self, section_id: str = _SECTION_ID) -> dict:
        with self._path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        def walk(items):
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                if item.get("id") == section_id:
                    return item
                found = walk(item.get("sekce") or [])
                if found is not None:
                    return found
            return None

        found = walk(payload.get("sekce") or [])
        self.assertIsNotNone(found)
        return found

    def _save_section(self, section_id: str, **changes) -> tuple[bool, list[str]]:
        section = proverky_knowledge_service.get_section(_AREA_ID, section_id)
        self.assertIsNotNone(section)
        payload = dict(section)
        payload.update(changes)
        return proverky_knowledge_service.save_section(_AREA_ID, section_id, payload)

    def test_editor_has_tree_and_edit_panel(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()
        splitters = dialog.findChildren(QSplitter)
        self.assertTrue(splitters)
        self.assertIsNotNone(dialog.knowledge_tree)
        self.assertIsNotNone(dialog._editor_host)

    def test_editor_opens_without_automatic_selection(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog()

        self.assertIsNone(dialog.knowledge_tree.currentItem())
        self.assertEqual(dialog.knowledge_tree.selectedItems(), [])
        self.assertIsNone(dialog._section_editor)
        self.assertTrue(dialog._empty_state_label.isVisibleTo(dialog))
        self.assertIn(
            KNOWLEDGE_EDITOR_SELECT_SECTION_HINT,
            dialog._empty_state_label.text(),
        )
        self.assertFalse(dialog._editor_host.isVisibleTo(dialog))

    def test_tree_selection_loads_section(self) -> None:
        dialog = ProverkyKnowledgeEditorDialog(
            area_id=_AREA_ID,
            section_id=_SECTION_ID,
        )
        self.assertIsNotNone(dialog._section_editor)
        self.assertEqual(dialog._section_editor.area_id, _AREA_ID)
        self.assertEqual(dialog._section_editor.section_id, _SECTION_ID)
        self.assertIn(_SECTION_ID, dialog._section_editor._id_label.text())

    def test_section_can_be_saved_without_control_process(self) -> None:
        ok, errors = self._save_section(_SECTION_ID, legal_requirement_id=None)
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        section = self._section_from_file(_SECTION_ID)
        self.assertNotIn("legal_requirement_id", section)

    def test_section_can_be_saved_with_control_process(self) -> None:
        ok, errors = self._save_section(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        section = self._section_from_file(_SECTION_ID)
        self.assertEqual(section["legal_requirement_id"], self._process.id)

    def test_section_editor_loads_selected_control_process(self) -> None:
        ok, errors = self._save_section(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])

        editor = ProverkyKnowledgeSectionEditDialog(
            area_id=_AREA_ID,
            section_id=_SECTION_ID,
        )
        self.assertEqual(
            editor._control_process_combo.currentText(),
            legal_requirement_merged_target_label(self._process),
        )
        self.assertNotEqual(
            editor._control_process_combo.currentText(),
            KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY,
        )

    def test_multiple_sections_can_share_one_control_process(self) -> None:
        ok_one, errors_one = self._save_section(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        ok_two, errors_two = self._save_section(
            self._second_section_id,
            legal_requirement_id=self._process.id,
        )
        self.assertTrue(ok_one)
        self.assertEqual(errors_one, [])
        self.assertTrue(ok_two)
        self.assertEqual(errors_two, [])
        self.assertEqual(
            self._section_from_file(_SECTION_ID)["legal_requirement_id"],
            self._process.id,
        )
        self.assertEqual(
            self._section_from_file(self._second_section_id)["legal_requirement_id"],
            self._process.id,
        )

    def test_older_json_without_legal_requirement_id_loads(self) -> None:
        section = self._section_from_file(_SECTION_ID)
        self.assertNotIn("legal_requirement_id", section)
        loaded = proverky_knowledge_service.get_section(_AREA_ID, _SECTION_ID)
        self.assertIsNotNone(loaded)
        self.assertNotIn("legal_requirement_id", loaded)
        editor = ProverkyKnowledgeSectionEditDialog(
            area_id=_AREA_ID,
            section_id=_SECTION_ID,
        )
        self.assertEqual(
            editor._control_process_combo.currentText(),
            KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY,
        )

    def test_same_name_section_is_not_auto_matched_to_process(self) -> None:
        legal_requirement_service.create_requirement(
            title="Lékárnička",
            process_code="P-099",
        )
        loaded = proverky_knowledge_service.get_section(_AREA_ID, _SECTION_ID)
        self.assertIsNotNone(loaded)
        self.assertNotIn("legal_requirement_id", loaded)
        editor = ProverkyKnowledgeSectionEditDialog(
            area_id=_AREA_ID,
            section_id=_SECTION_ID,
        )
        self.assertEqual(
            editor._control_process_combo.currentData(Qt.ItemDataRole.UserRole),
            None,
        )

    def test_inactive_saved_process_is_kept_on_edit(self) -> None:
        ok, errors = self._save_section(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        legal_requirement_service.archive_requirement(self._process.id)

        editor = ProverkyKnowledgeSectionEditDialog(
            area_id=_AREA_ID,
            section_id=_SECTION_ID,
        )
        self.assertEqual(
            editor._control_process_combo.currentData(Qt.ItemDataRole.UserRole),
            self._process.id,
        )
        # Opětovné uložení se stejnou vazbou musí projít.
        editor._nazev_edit.setText(editor._nazev_edit.text())
        self.assertTrue(editor.persist_changes())
        self.assertEqual(
            self._section_from_file(_SECTION_ID)["legal_requirement_id"],
            self._process.id,
        )


if __name__ == "__main__":
    unittest.main()
