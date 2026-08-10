"""AUDIT-FIELD-OFFICE-3: rychlá změna typu ověření v metodice auditů."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox

_TMP = Path(tempfile.mkdtemp(prefix="audit-field-office-3-"))
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
from moduly.audity.sluzby.audit_knowledge_editor_service import (
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_assertion_dialog import (
    AudityKnowledgeAssertionDialog,
)
from moduly.audity.ui.audity_knowledge_assertions_widget import (
    _COL_VERIFICATION,
    AudityKnowledgeAssertionsWidget,
)

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_ASSERTION_ID = "vsechny_urazy_evidovany"


class AuditFieldOffice3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _section(self) -> dict:
        criterion = audit_knowledge_service.get_criterion(
            _PROCESS_ID,
            _SECTION_ID,
            ensure=False,
        )
        assert criterion is not None
        return criterion

    def _assertion_from_disk(self) -> dict:
        with self._path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for section in payload.get("sekce") or []:
            for item in section.get("auditni_tvrzeni") or []:
                if item.get("id") == _ASSERTION_ID:
                    return item
        self.fail(f"Assertion {_ASSERTION_ID} not found")

    def _load_widget(self) -> AudityKnowledgeAssertionsWidget:
        widget = AudityKnowledgeAssertionsWidget()
        widget.load_section(
            process_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            section=self._section(),
        )
        return widget

    def _combo_for_assertion(
        self, widget: AudityKnowledgeAssertionsWidget, assertion_id: str
    ) -> QComboBox:
        for row in range(widget._table.rowCount()):
            combo = widget._table.cellWidget(row, _COL_VERIFICATION)
            if isinstance(combo, QComboBox) and combo.property("assertion_id") == assertion_id:
                return combo
        self.fail(f"Combo for {assertion_id} not found")

    def _set_combo_type(self, combo: QComboBox, verification_type: str) -> None:
        index = combo.findData(verification_type)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)

    def test_inline_change_documentation_to_terrain(self) -> None:
        widget = self._load_widget()
        combo = self._combo_for_assertion(widget, _ASSERTION_ID)
        before = self._assertion_from_disk()
        before_text = before.get("text")
        before_popis = before.get("popis")
        before_severity = before.get("zavaznost")
        before_poradi = before.get("poradi")

        self._set_combo_type(combo, VERIFICATION_TYPE_TERRAIN)

        saved = self._assertion_from_disk()
        self.assertEqual(saved["verification_type"], VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(saved.get("text"), before_text)
        self.assertEqual(saved.get("popis"), before_popis)
        self.assertEqual(saved.get("zavaznost"), before_severity)
        self.assertEqual(saved.get("poradi"), before_poradi)

        reloaded = self._load_widget()
        reloaded_combo = self._combo_for_assertion(reloaded, _ASSERTION_ID)
        self.assertEqual(reloaded_combo.currentData(), VERIFICATION_TYPE_TERRAIN)

    def test_inline_change_terrain_to_documentation(self) -> None:
        audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            {
                "id": _ASSERTION_ID,
                "text": self._assertion_from_disk()["text"],
                "popis": self._assertion_from_disk().get("popis") or "",
                "zavaznost": self._assertion_from_disk().get("zavaznost") or "stredni",
                "verification_type": VERIFICATION_TYPE_TERRAIN,
                "poradi": self._assertion_from_disk().get("poradi") or 10,
                "aktivni": True,
            },
            assertion_id=_ASSERTION_ID,
        )

        widget = self._load_widget()
        combo = self._combo_for_assertion(widget, _ASSERTION_ID)
        self.assertEqual(combo.currentData(), VERIFICATION_TYPE_TERRAIN)

        self._set_combo_type(combo, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(
            self._assertion_from_disk()["verification_type"],
            VERIFICATION_TYPE_DOCUMENTATION,
        )

    def test_inline_change_visible_in_detail_dialog(self) -> None:
        widget = self._load_widget()
        combo = self._combo_for_assertion(widget, _ASSERTION_ID)
        self._set_combo_type(combo, VERIFICATION_TYPE_TERRAIN)

        assertion = next(
            item for item in widget._assertions if item.get("id") == _ASSERTION_ID
        )
        dialog = AudityKnowledgeAssertionDialog(assertion=assertion)
        self.assertEqual(dialog._current_verification_type(), VERIFICATION_TYPE_TERRAIN)

    def test_other_fields_unchanged_after_inline_toggle(self) -> None:
        before = self._assertion_from_disk()
        snapshot = {
            "text": before.get("text"),
            "popis": before.get("popis"),
            "zavaznost": before.get("zavaznost"),
            "poradi": before.get("poradi"),
            "aktivni": before.get("aktivni", True),
            "id": before.get("id"),
        }
        widget = self._load_widget()
        combo = self._combo_for_assertion(widget, _ASSERTION_ID)
        self._set_combo_type(combo, VERIFICATION_TYPE_TERRAIN)
        self._set_combo_type(
            self._combo_for_assertion(self._load_widget(), _ASSERTION_ID),
            VERIFICATION_TYPE_DOCUMENTATION,
        )
        after = self._assertion_from_disk()
        for key, value in snapshot.items():
            self.assertEqual(after.get(key, True if key == "aktivni" else None), value)
        self.assertEqual(after["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)


if __name__ == "__main__":
    unittest.main()
