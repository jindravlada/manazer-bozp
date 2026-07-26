"""INSPECTION-TERRAIN-1 / 1a / 1b – Dokumentace / Terén u prověrek BOZP."""

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

_TMP = Path(tempfile.mkdtemp(prefix="inspection-terrain-1b-"))
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
        TERRAIN_CHECKLIST_BUTTON_LABEL,
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
    from moduly.proverky.ui.bozp_inspection_terrain_widget import BozpInspectionTerrainWidget
    from moduly.proverky.ui.proverky_knowledge_list_item_dialog import (
        ProverkyKnowledgeListItemDialog,
    )
    from moduly.proverky.ui.proverky_page import ProverkyPage


def _assert_valid_odt_package(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        assert infos, "prázdný ODT archiv"
        first = infos[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/vnd.oasis.opendocument.text"

        required = {
            "mimetype",
            "content.xml",
            "styles.xml",
            "META-INF/manifest.xml",
        }
        names = set(archive.namelist())
        missing = required - names
        assert not missing, f"chybí soubory: {sorted(missing)}"

        for name in ("content.xml", "styles.xml", "meta.xml", "settings.xml", "META-INF/manifest.xml"):
            if name in names:
                ET.fromstring(archive.read(name))


class InspectionTerrain1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        proverky_knowledge_service.ensure_catalogs()

    def _sample_control_point(
        self,
        *,
        verification_type: str | None = None,
    ) -> tuple[str, str, dict]:
        wanted = (
            inspection_verification_service.normalize_verification_type(verification_type)
            if verification_type is not None
            else None
        )
        for area in proverky_knowledge_service.get_areas():
            for section in proverky_knowledge_service.list_sections(
                area.id, include_inactive=False
            ):
                items = proverky_knowledge_service.get_active_items(
                    section.get("kontrolni_body")
                )
                for item in items:
                    if wanted is not None:
                        if (
                            inspection_verification_service.methodology_verification_type(
                                item
                            )
                            != wanted
                        ):
                            continue
                    return area.id, str(section.get("id") or ""), item
        self.fail("V metodice není žádný kontrolní bod pro test.")

    def test_documentation_point_listed_under_documentation(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        inspection = bozp_inspection_service.create_inspection()
        docs = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertTrue(
            any(
                ref.control_point_id == item["id"]
                and ref.section_id == section_id
                and ref.area_id == area_id
                for ref in docs
            )
        )
        terrain = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertFalse(
            any(
                ref.control_point_id == item["id"]
                and ref.section_id == section_id
                and ref.area_id == area_id
                for ref in terrain
            )
        )

    def test_terrain_point_listed_under_terrain(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_TERRAIN
        )
        inspection = bozp_inspection_service.create_inspection()
        terrain = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(
            any(
                ref.control_point_id == item["id"]
                and ref.section_id == section_id
                and ref.area_id == area_id
                for ref in terrain
            )
        )

    def test_adhoc_move_documentation_to_terrain(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        inspection = bozp_inspection_service.create_inspection()
        inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )
        terrain = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(
            any(
                ref.control_point_id == item["id"] and ref.section_id == section_id
                for ref in terrain
            )
        )
        self.assertEqual(
            inspection_verification_service.methodology_verification_type(item),
            VERIFICATION_TYPE_DOCUMENTATION,
        )

    def test_adhoc_move_terrain_to_documentation(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_TERRAIN
        )
        inspection = bozp_inspection_service.create_inspection()
        inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            item=item,
        )
        docs = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertTrue(
            any(
                ref.control_point_id == item["id"] and ref.section_id == section_id
                for ref in docs
            )
        )

    def test_override_persists_after_reopen(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        inspection = bozp_inspection_service.create_inspection()
        inspection_verification_service.set_override(
            inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=str(item["id"]),
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )

        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        self.assertIsNotNone(reloaded)
        terrain = inspection_verification_service.list_control_points(
            reloaded.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(
            any(
                ref.control_point_id == item["id"] and ref.section_id == section_id
                for ref in terrain
            )
        )
        overrides = inspection_verification_service.overrides_map(reloaded.id)
        self.assertEqual(
            overrides[(area_id, section_id, str(item["id"]))],
            VERIFICATION_TYPE_TERRAIN,
        )

    def test_checklist_button_is_on_terrain_tab(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        dialog = BozpInspectionDialog(inspection=inspection)
        self.assertEqual(
            dialog.terrain_widget.checklist_btn.text(),
            TERRAIN_CHECKLIST_BUTTON_LABEL,
        )
        self.assertTrue(dialog.terrain_widget.checklist_btn.isEnabled())
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_TEREN, labels)

    def test_main_list_has_no_terrain_checklist_export(self) -> None:
        page = ProverkyPage()
        self.assertFalse(hasattr(page, "terrain_checklist_btn"))

    def test_terrain_checklist_odt_is_valid_package(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 7, 10),
            workplace_name="Provoz checklist",
        )
        path = terrain_checklist_service.generate_for_inspection(inspection)
        self.assertTrue(path.exists())
        _assert_valid_odt_package(path)
        with zipfile.ZipFile(path, "r") as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Terénní checklist", content)
        self.assertIn("Provoz checklist", content)
        self.assertIn("Poznámka:", content)

    def test_template_odt_is_valid_package(self) -> None:
        template = terrain_checklist_service.template_path()
        self.assertTrue(template.exists())
        _assert_valid_odt_package(template)

    def test_normalize_kontrolni_body_defaults_to_documentation(self) -> None:
        items = proverky_knowledge_service.normalize_kontrolni_body(
            [{"id": "bod_1", "nazev": "Bod 1"}]
        )
        self.assertEqual(items[0]["verification_type"], VERIFICATION_TYPE_DOCUMENTATION)

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

    def test_terrain_widget_has_same_evaluation_controls_api(self) -> None:
        widget = BozpInspectionTerrainWidget()
        inspection = bozp_inspection_service.create_inspection()
        widget.set_inspection_id(inspection.id)
        self.assertTrue(hasattr(widget, "checklist_btn"))
        self.assertEqual(widget.checklist_btn.text(), TERRAIN_CHECKLIST_BUTTON_LABEL)


if __name__ == "__main__":
    unittest.main()
