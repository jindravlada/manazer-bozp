"""INSPECTIONS-QUESTIONS-1: zobrazení otázek Dokumentace / Terén."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="inspections-questions-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QLabel

    from moduly.proverky.constants import (
        AREA_NOT_IMPLEMENTED_TEXT,
        AREA_PART_NO_CONTROL_QUESTIONS_TEXT,
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_verification_service import (
        inspection_verification_service,
    )
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_inspection_terrain_widget import BozpInspectionTerrainWidget
    from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


_CHEMIE_AREA_ID = "chemie"
_BL_SECTION_ID = "bezpecnostni_listy"


class InspectionsQuestions1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        proverky_knowledge_service.ensure_catalogs()

    def _chemie_area(self):
        area = proverky_knowledge_service.get_area_by_id(_CHEMIE_AREA_ID)
        self.assertIsNotNone(area)
        assert area is not None
        self.assertEqual(area.nazev, "Chemické látky a směsi")
        return area

    def _bl_section(self) -> dict:
        section = proverky_knowledge_service.get_section(_CHEMIE_AREA_ID, _BL_SECTION_ID)
        self.assertIsNotNone(section)
        assert section is not None
        self.assertEqual(section.get("nazev"), "Bezpečnostní listy")
        return section

    def _set_all_points_type(self, section: dict, verification_type: str) -> dict:
        items = []
        for raw in section.get("kontrolni_body") or []:
            if not isinstance(raw, dict):
                continue
            updated = dict(raw)
            updated["verification_type"] = verification_type
            updated["aktivni"] = True
            items.append(updated)
        payload = dict(section)
        payload["kontrolni_body"] = items
        ok, errors = proverky_knowledge_service.save_section(
            _CHEMIE_AREA_ID,
            _BL_SECTION_ID,
            payload,
        )
        self.assertTrue(ok, errors)
        return proverky_knowledge_service.get_section(_CHEMIE_AREA_ID, _BL_SECTION_ID)

    def test_chemie_area_and_bl_section_load(self) -> None:
        self._chemie_area()
        section = self._bl_section()
        items = proverky_knowledge_service.get_active_items(section.get("kontrolni_body"))
        self.assertGreaterEqual(len(items), 5)

    def test_five_terrain_points_visible_only_in_terrain_tab(self) -> None:
        section = self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        items = proverky_knowledge_service.get_active_items(section.get("kontrolni_body"))
        self.assertEqual(len(items), 6)

        docs, terrain, unknown = inspection_verification_service.partition_active_control_points(
            section.get("kontrolni_body"),
        )
        self.assertEqual(len(docs), 0)
        self.assertEqual(len(terrain), 6)
        self.assertEqual(len(unknown), 0)

        inspection = bozp_inspection_service.create_inspection()
        listed = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        bl_terrain = [
            ref
            for ref in listed
            if ref.area_id == _CHEMIE_AREA_ID and ref.section_id == _BL_SECTION_ID
        ]
        self.assertEqual(len(bl_terrain), 6)

        listed_docs = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertFalse(
            any(
                ref.area_id == _CHEMIE_AREA_ID and ref.section_id == _BL_SECTION_ID
                for ref in listed_docs
            )
        )

    def test_documentation_points_only_in_documentation(self) -> None:
        section = self._set_all_points_type(
            self._bl_section(),
            VERIFICATION_TYPE_DOCUMENTATION,
        )
        docs, terrain, _ = inspection_verification_service.partition_active_control_points(
            section.get("kontrolni_body"),
        )
        self.assertEqual(len(docs), 6)
        self.assertEqual(len(terrain), 0)

    def test_canonical_and_legacy_aliases(self) -> None:
        normalize = inspection_verification_service.normalize_verification_type
        self.assertEqual(normalize("dokumentace"), VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(normalize("documentation"), VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(normalize("document"), VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(normalize("docs"), VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(normalize("teren"), VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(normalize("field"), VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(normalize("terrain"), VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(normalize("Terén"), VERIFICATION_TYPE_TERRAIN)

    def test_active_inactive_section_and_points(self) -> None:
        section = self._bl_section()
        items = list(section.get("kontrolni_body") or [])
        self.assertGreaterEqual(len(items), 2)
        items[0] = dict(items[0], aktivni=False, verification_type=VERIFICATION_TYPE_TERRAIN)
        for index in range(1, len(items)):
            items[index] = dict(
                items[index],
                aktivni=True,
                verification_type=VERIFICATION_TYPE_TERRAIN,
            )
        payload = dict(section, kontrolni_body=items, aktivni=True)
        ok, errors = proverky_knowledge_service.save_section(
            _CHEMIE_AREA_ID,
            _BL_SECTION_ID,
            payload,
        )
        self.assertTrue(ok, errors)
        reloaded = self._bl_section()
        active = proverky_knowledge_service.get_active_items(reloaded.get("kontrolni_body"))
        self.assertEqual(len(active), len(items) - 1)
        self.assertTrue(all(item.get("aktivni", True) for item in active))

        inactive_section = dict(reloaded, aktivni=False)
        ok, errors = proverky_knowledge_service.save_section(
            _CHEMIE_AREA_ID,
            _BL_SECTION_ID,
            inactive_section,
        )
        self.assertTrue(ok, errors)
        active_sections = {
            str(row.get("id"))
            for row in proverky_knowledge_service.list_sections(
                _CHEMIE_AREA_ID,
                include_inactive=False,
            )
        }
        self.assertNotIn(_BL_SECTION_ID, active_sections)

        # Obnov aktivitu pro následující testy ve stejné DB.
        restored = proverky_knowledge_service.get_section(_CHEMIE_AREA_ID, _BL_SECTION_ID)
        assert restored is not None
        ok, errors = proverky_knowledge_service.save_section(
            _CHEMIE_AREA_ID,
            _BL_SECTION_ID,
            dict(restored, aktivni=True),
        )
        self.assertTrue(ok, errors)

    def test_empty_part_message_not_area_unimplemented(self) -> None:
        section = self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        widget = BozpKnowledgeSectionWidget()
        widget.set_verification_filter(VERIFICATION_TYPE_DOCUMENTATION)
        widget.set_section(
            section,
            area_id=_CHEMIE_AREA_ID,
            area_label="Chemické látky a směsi",
            section_label="Bezpečnostní listy",
        )
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn(AREA_PART_NO_CONTROL_QUESTIONS_TEXT, labels)
        self.assertNotIn(AREA_NOT_IMPLEMENTED_TEXT, labels)

    def test_area_with_questions_not_marked_unimplemented(self) -> None:
        self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        widget = BozpInspectionAreasWidget(verification_type=VERIFICATION_TYPE_DOCUMENTATION)
        widget.reload_areas()
        tree = proverky_knowledge_service.get_knowledge_tree()
        chem = next(root for root in tree if root.area_id == _CHEMIE_AREA_ID)
        self.assertTrue(chem.children)
        widget._on_area_selected(chem)
        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_HINT)

    def test_ui_shows_terrain_points_after_type_change_and_refresh(self) -> None:
        section = self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        docs_widget = BozpInspectionAreasWidget(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        terrain_widget = BozpInspectionTerrainWidget()
        # Simulace zastaralého snímku na druhé záložce (původní bug).
        stale = dict(section)
        stale["kontrolni_body"] = [
            dict(item, verification_type=VERIFICATION_TYPE_DOCUMENTATION)
            for item in (section.get("kontrolni_body") or [])
            if isinstance(item, dict)
        ]
        terrain_widget.knowledge_widget.show_section(
            stale,
            area_id=_CHEMIE_AREA_ID,
            area_label="Chemické látky a směsi",
            section_label="Bezpečnostní listy",
        )
        terrain_widget._current_area_id = _CHEMIE_AREA_ID
        terrain_widget._current_section_id = _BL_SECTION_ID
        terrain_widget.content_stack.setCurrentIndex(terrain_widget._PAGE_KNOWLEDGE)

        # Po refreshi z metodiky musí terénní body naskočit bez duplicit.
        terrain_widget.reload_knowledge()
        terrain_widget.knowledge_tree.select_node(_CHEMIE_AREA_ID, _BL_SECTION_ID)

        titles = [
            label.text()
            for label in terrain_widget.knowledge_widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]
        self.assertEqual(len(titles), 6)
        self.assertEqual(len(set(titles)), 6)

        docs_widget.knowledge_tree.select_node(_CHEMIE_AREA_ID, _BL_SECTION_ID)
        docs_widget._on_section_selected(
            next(
                node
                for root in proverky_knowledge_service.get_knowledge_tree()
                if root.area_id == _CHEMIE_AREA_ID
                for node in root.children
                if node.node_id == _BL_SECTION_ID
            )
        )
        doc_titles = [
            label.text()
            for label in docs_widget.knowledge_widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]
        self.assertEqual(doc_titles, [])

    def test_dialog_knowledge_changed_refreshes_both_tabs(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.show()
        QApplication.processEvents()
        self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        dialog._on_knowledge_changed()
        QApplication.processEvents()

        selected = dialog.terrain_widget.knowledge_tree.select_node(
            _CHEMIE_AREA_ID,
            _BL_SECTION_ID,
        )
        self.assertTrue(selected)
        QApplication.processEvents()

        titles = [
            label.text()
            for label in dialog.terrain_widget.knowledge_widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]
        self.assertEqual(len(titles), 6)
        self.assertEqual(len(set(titles)), 6)
        dialog.close()

    def test_order_preserved(self) -> None:
        section = self._set_all_points_type(self._bl_section(), VERIFICATION_TYPE_TERRAIN)
        before = [
            str(item.get("id"))
            for item in proverky_knowledge_service.get_active_items(section.get("kontrolni_body"))
        ]
        filtered = inspection_verification_service.filter_active_control_points(
            section.get("kontrolni_body"),
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        after = [str(item.get("id")) for item in filtered]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
