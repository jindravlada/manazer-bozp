"""INSPECTION-TERRAIN-1 – Dokumentace / Terén u prověrek BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="inspection-terrain-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.constants import (
        TAB_TEREN,
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_verification_service import (
        inspection_verification_service,
    )
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.sluzby.terrain_checklist_service import terrain_checklist_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.proverky_knowledge_list_item_dialog import (
        ProverkyKnowledgeListItemDialog,
    )


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        return archive.read("content.xml").decode("utf-8")


class InspectionTerrain1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _sample_control_point(self) -> tuple[str, str, dict]:
        for area in proverky_knowledge_service.get_areas():
            for section in proverky_knowledge_service.list_sections(
                area.id, include_inactive=False
            ):
                items = proverky_knowledge_service.get_active_items(
                    section.get("kontrolni_body")
                )
                if items:
                    return area.id, str(section.get("id") or ""), items[0]
        self.fail("V metodice není žádný kontrolní bod pro test.")

    def test_normalize_kontrolni_body_defaults_to_documentation(self) -> None:
        items = proverky_knowledge_service.normalize_kontrolni_body(
            [{"id": "bod_1", "nazev": "Bod 1"}]
        )
        self.assertEqual(items[0]["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)

    def test_normalize_kontrolni_body_keeps_terrain(self) -> None:
        items = proverky_knowledge_service.normalize_kontrolni_body(
            [
                {
                    "id": "bod_teren",
                    "nazev": "Bod terén",
                    "verification_type": VERIFICATION_TYPE_TERRAIN,
                }
            ]
        )
        self.assertEqual(items[0]["verification_type"], VERIFICATION_TYPE_TERRAIN)

    def test_knowledge_editor_dialog_has_verification_type(self) -> None:
        dialog = ProverkyKnowledgeListItemDialog(
            title="Test",
            include_zavaznost=True,
            include_verification_type=True,
            item={
                "id": "x",
                "nazev": "Bod",
                "verification_type": VERIFICATION_TYPE_TERRAIN,
            },
        )
        data = dialog.get_data()
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data["verification_type"], VERIFICATION_TYPE_TERRAIN)

    def test_override_moves_point_without_changing_methodology(self) -> None:
        area_id, section_id, item = self._sample_control_point()
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 7, 1),
            workplace_name="Hala test",
        )
        methodology = inspection_verification_service.methodology_verification_type(item)
        self.assertEqual(methodology, VERIFICATION_TYPE_DOCUMENTATION)

        effective = inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        self.assertEqual(effective, VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(
            inspection_verification_service.methodology_verification_type(item),
            VERIFICATION_TYPE_DOCUMENTATION,
        )

        terrain = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(
            any(ref.control_point_id == item["id"] for ref in terrain)
        )

        # Návrat na metodiku smaže výjimku.
        restored = inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            item=item,
        )
        self.assertEqual(restored, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(
            inspection_verification_service.overrides_map(inspection.id),
            {},
        )

    def test_dialog_has_terrain_tab(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        dialog = BozpInspectionDialog(inspection=inspection)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_TEREN, labels)
        self.assertEqual(
            labels.index("Kontrolované oblasti") + 1,
            labels.index(TAB_TEREN),
        )

    def test_terrain_checklist_export_contains_header_and_points(self) -> None:
        area_id, section_id, item = self._sample_control_point()
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 7, 10),
            workplace_name="Provoz checklist",
        )
        inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )

        path = terrain_checklist_service.generate_for_inspection(inspection)
        self.assertTrue(path.exists())
        content = _odt_content(path)
        self.assertIn("Terénní checklist", content)
        self.assertIn("Provoz checklist", content)
        self.assertIn(str(item["nazev"]), content)
        self.assertIn("Poznámka:", content)


if __name__ == "__main__":
    unittest.main()
