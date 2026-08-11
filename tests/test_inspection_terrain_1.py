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
    from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
        ProverkyKnowledgeSectionEditDialog,
    )
    from moduly.proverky.ui.proverky_page import ProverkyPage
    from PySide6.QtWidgets import QComboBox, QListWidget


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

    def test_terrain_tab_uses_same_editor_as_documentation(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        dialog = BozpInspectionDialog(inspection=inspection)
        self.assertTrue(hasattr(dialog.areas_widget, "knowledge_tree"))
        self.assertTrue(hasattr(dialog.terrain_widget, "knowledge_tree"))
        self.assertTrue(hasattr(dialog.areas_widget, "knowledge_widget"))
        self.assertTrue(hasattr(dialog.terrain_widget, "knowledge_widget"))
        self.assertEqual(
            dialog.areas_widget.knowledge_widget.section_widget._verification_filter,
            VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertEqual(
            dialog.terrain_widget.knowledge_widget.section_widget._verification_filter,
            VERIFICATION_TYPE_TERRAIN,
        )
        self.assertIsNone(dialog.areas_widget.checklist_btn)
        self.assertIsNotNone(dialog.terrain_widget.checklist_btn)
        self.assertEqual(
            dialog.terrain_widget.checklist_btn.text(),
            TERRAIN_CHECKLIST_BUTTON_LABEL,
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

    def test_terrain_checklist_question_is_bold_area_is_not(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        terrain = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        self.assertTrue(terrain)
        content = terrain_checklist_service._checklist_content(inspection.id)
        paragraphs = [p for p in content.paragraphs if not p.blank]
        self.assertGreaterEqual(len(paragraphs), 2)
        area_para = paragraphs[0]
        question_para = paragraphs[1]
        self.assertFalse(area_para.runs[0].bold)
        self.assertNotEqual(area_para.style, "AuditCriterion")
        self.assertTrue(question_para.runs[0].bold)
        self.assertEqual(question_para.runs[0].text, terrain[0].control_point_label)
        self.assertIn(" · ", area_para.runs[0].text)

    def test_terrain_checklist_keeps_area_block_together(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 7, 10),
            workplace_name="Keep together",
        )
        content = terrain_checklist_service._checklist_content(inspection.id)
        blocks = [p for p in content.paragraphs if not p.blank]
        self.assertGreaterEqual(len(blocks), 4)
        self.assertTrue(blocks[0].keep_with_next)
        self.assertTrue(blocks[1].keep_with_next)
        self.assertTrue(blocks[2].keep_with_next)
        self.assertFalse(blocks[3].keep_with_next)

        path = terrain_checklist_service.generate_for_inspection(inspection)
        with zipfile.ZipFile(path, "r") as archive:
            xml = archive.read("content.xml").decode("utf-8")
        self.assertIn('style:name="ExportKeepWithNext"', xml)
        self.assertIn('fo:keep-with-next="always"', xml)
        self.assertIn('text:style-name="ExportKeepWithNext"', xml)

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

    def test_knowledge_section_editor_has_inline_verification_type(self) -> None:
        from PySide6.QtCore import Qt

        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        dialog = ProverkyKnowledgeSectionEditDialog(
            area_id=area_id,
            section_id=section_id,
        )
        list_widget = dialog._lists_by_field.get("kontrolni_body")
        self.assertIsInstance(list_widget, QListWidget)
        assert isinstance(list_widget, QListWidget)
        self.assertGreater(list_widget.count(), 0)

        target_row = None
        for row in range(list_widget.count()):
            raw = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(raw, dict) and raw.get("id") == item.get("id"):
                target_row = row
                break
        self.assertIsNotNone(target_row)
        assert target_row is not None

        row_item = list_widget.item(target_row)
        row_widget = list_widget.itemWidget(row_item)
        self.assertIsNotNone(row_widget)
        combos = row_widget.findChildren(QComboBox)
        self.assertGreaterEqual(len(combos), 2)
        verification_combo = combos[0]
        self.assertEqual(verification_combo.count(), 2)
        self.assertEqual(verification_combo.itemData(0), VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(verification_combo.itemData(1), VERIFICATION_TYPE_TERRAIN)

        terrain_index = verification_combo.findData(VERIFICATION_TYPE_TERRAIN)
        self.assertGreaterEqual(terrain_index, 0)
        verification_combo.setCurrentIndex(terrain_index)

        saved = proverky_knowledge_service.get_section(area_id, section_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        saved_item = next(
            (
                raw
                for raw in (saved.get("kontrolni_body") or [])
                if isinstance(raw, dict) and raw.get("id") == item.get("id")
            ),
            None,
        )
        self.assertIsNotNone(saved_item)
        assert saved_item is not None
        self.assertEqual(saved_item.get("verification_type"), VERIFICATION_TYPE_TERRAIN)

        # vrať metodiku zpět, ať ostatní testy nejsou ovlivněné
        verification_combo.setCurrentIndex(
            verification_combo.findData(VERIFICATION_TYPE_DOCUMENTATION)
        )

    def test_seed_marks_prakticka_kontrola_as_terrain(self) -> None:
        found = False
        for area in proverky_knowledge_service.get_areas():
            knowledge = proverky_knowledge_service.load_area_knowledge(area)
            if not knowledge:
                continue
            for section in knowledge.get("sekce") or []:
                if not isinstance(section, dict):
                    continue
                for raw in section.get("kontrolni_body") or []:
                    if not isinstance(raw, dict):
                        continue
                    if raw.get("id") != "prakticka_kontrola":
                        continue
                    found = True
                    self.assertEqual(
                        proverky_knowledge_service.get_verification_type(raw),
                        VERIFICATION_TYPE_TERRAIN,
                        msg=f"{area.id}/{section.get('id')}/prakticka_kontrola",
                    )
        self.assertTrue(found, "V metodice chybí prakticka_kontrola")

    def test_adhoc_override_does_not_change_methodology(self) -> None:
        area_id, section_id, item = self._sample_control_point(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        point_id = str(item.get("id") or "")
        methodology_before = inspection_verification_service.methodology_verification_type(item)

        inspection = bozp_inspection_service.create_inspection()
        inspection_verification_service.set_override(
            inspection_id=inspection.id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=point_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
            item=item,
        )

        section_after = proverky_knowledge_service.get_section(area_id, section_id)
        self.assertIsNotNone(section_after)
        assert section_after is not None
        item_after = next(
            (
                raw
                for raw in (section_after.get("kontrolni_body") or [])
                if isinstance(raw, dict) and raw.get("id") == point_id
            ),
            None,
        )
        self.assertIsNotNone(item_after)
        self.assertEqual(
            inspection_verification_service.methodology_verification_type(item_after),
            methodology_before,
        )
        self.assertEqual(
            inspection_verification_service.effective_verification_type(
                inspection.id,
                area_id=area_id,
                section_id=section_id,
                control_point_id=point_id,
                item=item_after,
            ),
            VERIFICATION_TYPE_TERRAIN,
        )

    def test_terrain_widget_has_checklist_button(self) -> None:
        widget = BozpInspectionTerrainWidget()
        inspection = bozp_inspection_service.create_inspection()
        widget.set_inspection_id(inspection.id)
        self.assertIsNotNone(widget.checklist_btn)
        self.assertEqual(widget.checklist_btn.text(), TERRAIN_CHECKLIST_BUTTON_LABEL)
        self.assertTrue(hasattr(widget, "knowledge_tree"))


if __name__ == "__main__":
    unittest.main()
