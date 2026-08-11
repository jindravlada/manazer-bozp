"""AUDIT-TERRAIN-CHECKLIST-1: tisk terénního checklistu u auditů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

_TMP = Path(tempfile.mkdtemp(prefix="audit-terrain-checklist-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.shared.verification_type import VERIFICATION_TYPE_TERRAIN
    from moduly.audity.constants import (
        TAB_TEREN,
        TERRAIN_CHECKLIST_BUTTON_LABEL,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_terrain_checklist_service import (
        audit_terrain_checklist_service,
    )
    from moduly.audity.sluzby.audit_verification_service import (
        audit_verification_service,
    )
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget


_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"


def _assert_valid_odt_package(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        if "mimetype" not in names or "content.xml" not in names:
            raise AssertionError(f"Neplatný ODT balíček: {path}")
        ET.fromstring(archive.read("content.xml"))


class AuditTerrainChecklist1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def _ensure_terrain_assertion(self, audit_id: int) -> dict:
        criterion = audit_knowledge_service.get_criterion(
            _PROCESS_ID,
            _SECTION_ID,
            ensure=False,
        )
        self.assertIsNotNone(criterion)
        assertions = audit_knowledge_service.get_audit_questions(criterion)
        self.assertTrue(assertions)
        item = assertions[0]
        audit_verification_service.set_override(
            audit_id,
            area_id=_PROCESS_ID,
            section_id=_SECTION_ID,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        return item

    def test_checklist_button_only_on_terrain_tab(self) -> None:
        audit = audit_service.create_audit(title="Checklist UI")
        dialog = AuditDialog(audit=audit)
        self.assertIsNone(dialog.processes_widget.checklist_btn)
        self.assertIsNotNone(dialog.terrain_widget.checklist_btn)
        self.assertEqual(
            dialog.terrain_widget.checklist_btn.text(),
            TERRAIN_CHECKLIST_BUTTON_LABEL,
        )
        self.assertTrue(dialog.terrain_widget.checklist_btn.isEnabled())
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_TEREN, labels)
        dialog.close()

    def test_new_terrain_widget_has_disabled_checklist_until_audit_id(self) -> None:
        widget = AuditProcessesWidget(verification_type=VERIFICATION_TYPE_TERRAIN)
        self.assertIsNotNone(widget.checklist_btn)
        self.assertFalse(widget.checklist_btn.isEnabled())
        widget.set_audit_id(1)
        self.assertTrue(widget.checklist_btn.isEnabled())

    def test_terrain_checklist_odt_is_valid_package(self) -> None:
        audit = audit_service.create_audit(
            title="Checklist ODT",
            started_at=date(2026, 8, 11),
            workplace_name="Provoz audit checklist",
        )
        item = self._ensure_terrain_assertion(audit.id)
        path = audit_terrain_checklist_service.generate_for_audit(audit)
        self.assertTrue(path.exists())
        _assert_valid_odt_package(path)
        with zipfile.ZipFile(path, "r") as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Terénní checklist", content)
        self.assertIn("Číslo auditu", content)
        self.assertIn("Provoz audit checklist", content)
        self.assertIn("Poznámka:", content)
        label = str(item.get("nazev") or item.get("text") or "")
        self.assertIn(label, content)

    def test_terrain_checklist_question_is_bold_area_is_not(self) -> None:
        audit = audit_service.create_audit(title="Checklist bold")
        item = self._ensure_terrain_assertion(audit.id)
        terrain = audit_verification_service.list_assertions(
            audit.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(terrain)
        content = audit_terrain_checklist_service._checklist_content(audit.id)
        paragraphs = [p for p in content.paragraphs if not p.blank]
        self.assertGreaterEqual(len(paragraphs), 2)
        area_para = paragraphs[0]
        question_para = paragraphs[1]
        self.assertFalse(area_para.runs[0].bold)
        self.assertNotEqual(area_para.style, "AuditCriterion")
        self.assertTrue(question_para.runs[0].bold)
        expected = str(item.get("nazev") or item.get("text") or "")
        self.assertEqual(question_para.runs[0].text, expected)
        self.assertIn(" · ", area_para.runs[0].text)

    def test_template_odt_is_valid_package(self) -> None:
        template = audit_terrain_checklist_service.template_path()
        self.assertTrue(template.exists())
        _assert_valid_odt_package(template)


if __name__ == "__main__":
    unittest.main()
