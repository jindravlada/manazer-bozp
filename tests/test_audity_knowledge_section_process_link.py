import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)


def _bootstrap() -> None:
    import core.services.editable_catalog_service as editable_catalog_module
    import core.services.storage_service as storage_module
    import core.database.session as session_module
    import moduly.audity.sluzby.audit_knowledge_editor_service as editor_module
    import moduly.audity.sluzby.audit_knowledge_service as knowledge_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(editable_catalog_module)
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()
    importlib.reload(knowledge_module)
    importlib.reload(editor_module)


_bootstrap()

from core.services.editable_catalog_service import editable_catalog_service
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_section_editor_widget import (
    AudityKnowledgeSectionEditorWidget,
)
from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_SECOND_SECTION_ID = "vysetrovani_urazu"


class AudityKnowledgeSectionProcessLinkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        _bootstrap()
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._process = legal_requirement_service.create_requirement(
            title="Řízení pracovních úrazů",
            process_code="P-012",
            requirement_summary="Testovací proces",
        )

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _section_from_file(self, section_id: str = _SECTION_ID) -> dict:
        with self._path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return next(
            item for item in payload.get("sekce") or [] if item.get("id") == section_id
        )

    def _save_metadata(self, section_id: str, **changes) -> list[str]:
        section = self._section_from_file(section_id)
        metadata = {
            "nazev": changes.get("nazev", section.get("nazev")),
            "popis": changes.get("popis", section.get("popis")),
            "cil_overeni": changes.get("cil_overeni", section.get("cil_overeni")),
            "poradi": changes.get("poradi", section.get("poradi")),
            "aktivni": changes.get("aktivni", section.get("aktivni", True)),
        }
        if "legal_requirement_id" in changes:
            metadata["legal_requirement_id"] = changes["legal_requirement_id"]
        return audit_knowledge_editor_service.save_section_metadata(
            _PROCESS_ID,
            section_id,
            metadata,
        )

    def test_section_can_be_saved_without_control_process(self) -> None:
        errors = self._save_metadata(_SECTION_ID, legal_requirement_id=None)
        self.assertEqual(errors, [])

        section = self._section_from_file(_SECTION_ID)
        self.assertNotIn("legal_requirement_id", section)

    def test_section_can_be_saved_with_control_process(self) -> None:
        errors = self._save_metadata(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertEqual(errors, [])

        section = self._section_from_file(_SECTION_ID)
        self.assertEqual(section["legal_requirement_id"], self._process.id)

    def test_section_editor_loads_selected_control_process(self) -> None:
        errors = self._save_metadata(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertEqual(errors, [])

        widget = AudityKnowledgeSectionEditorWidget()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=self._section_from_file(_SECTION_ID),
        )

        self.assertEqual(
            widget.section_metadata()["legal_requirement_id"],
            self._process.id,
        )
        expected_label = legal_requirement_merged_target_label(self._process)
        current_label = widget._control_process_combo.currentText()
        self.assertEqual(current_label, expected_label)

    def test_multiple_sections_can_share_one_control_process(self) -> None:
        errors_one = self._save_metadata(
            _SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        errors_two = self._save_metadata(
            _SECOND_SECTION_ID,
            legal_requirement_id=self._process.id,
        )
        self.assertEqual(errors_one, [])
        self.assertEqual(errors_two, [])

        first = self._section_from_file(_SECTION_ID)
        second = self._section_from_file(_SECOND_SECTION_ID)
        self.assertEqual(first["legal_requirement_id"], self._process.id)
        self.assertEqual(second["legal_requirement_id"], self._process.id)


if __name__ == "__main__":
    unittest.main()
