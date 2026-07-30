"""UX-INSPECTIONS-3: inteligentní prázdný stav panelu Kontrolní body."""

from __future__ import annotations

import os
import unittest
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea

from moduly.proverky.constants import (
    AREA_NOT_IMPLEMENTED_TEXT,
    CONTROL_POINTS_EMPTY_AREA_NONE,
    CONTROL_POINTS_EMPTY_CURRENT_PART,
    CONTROL_POINTS_EMPTY_SEE_DOCUMENTATION,
    CONTROL_POINTS_EMPTY_SEE_TERRAIN,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


def _section_with_points(*, documentation: int, terrain: int) -> dict:
    points: list[dict] = []
    for index in range(documentation):
        points.append(
            {
                "id": f"doc_{index + 1}",
                "nazev": f"Dokumentační bod {index + 1}",
                "popis": "",
                "poradi": (index + 1) * 10,
                "aktivni": True,
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
            }
        )
    for index in range(terrain):
        points.append(
            {
                "id": f"ter_{index + 1}",
                "nazev": f"Terénní bod {index + 1}",
                "popis": "",
                "poradi": (documentation + index + 1) * 10,
                "aktivni": True,
                "verification_type": VERIFICATION_TYPE_TERRAIN,
            }
        )
    return {
        "id": "test_sekce",
        "nazev": "Testovací sekce",
        "popis": "Popis sekce",
        "aktivni": True,
        "kontrolni_body": points,
        "typicke_zavady": [{"id": "z1", "nazev": "Závada", "aktivni": True}],
        "doporucene_postupy": [],
        "legislativa": [],
        "historie": [],
        "referencni_fotografie": [],
        "postup_kontroly": [],
    }


class UxInspections3SmartEmptyControlPointsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _show(
        self,
        section: dict,
        verification_type: str,
    ) -> BozpKnowledgeSectionWidget:
        widget = BozpKnowledgeSectionWidget()
        widget.set_verification_filter(verification_type)
        widget.set_section(
            deepcopy(section),
            area_id="test_oblast",
            area_label="Test",
            section_label="Testovací sekce",
        )
        return widget

    @staticmethod
    def _panel(widget: BozpKnowledgeSectionWidget) -> QScrollArea | None:
        return widget.findChild(QScrollArea, "ControlPointsPanel")

    @staticmethod
    def _titles(widget: BozpKnowledgeSectionWidget) -> list[str]:
        return [
            label.text()
            for label in widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]

    @staticmethod
    def _label_texts(widget: BozpKnowledgeSectionWidget) -> list[str]:
        return [label.text() for label in widget.findChildren(QLabel)]

    @staticmethod
    def _empty_info_texts(widget: BozpKnowledgeSectionWidget) -> list[str]:
        texts: list[str] = []
        panel = widget.findChild(QScrollArea, "ControlPointsPanel")
        if panel is None:
            return texts
        for frame in panel.findChildren(QFrame):
            if frame.property("controlPointsEmptyInfo"):
                texts.extend(label.text() for label in frame.findChildren(QLabel))
        return texts

    def test_current_part_with_points_shows_list(self) -> None:
        section = _section_with_points(documentation=2, terrain=1)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertIsNotNone(self._panel(widget))
        self.assertEqual(len(self._titles(widget)), 2)
        self.assertEqual(self._empty_info_texts(widget), [])
        self.assertIn("Kontrolní body", self._label_texts(widget))

    def test_points_only_in_documentation_shows_redirect_on_terrain(self) -> None:
        section = _section_with_points(documentation=3, terrain=0)
        widget = self._show(section, VERIFICATION_TYPE_TERRAIN)
        self.assertIsNotNone(self._panel(widget))
        self.assertEqual(self._titles(widget), [])
        self.assertEqual(
            self._empty_info_texts(widget),
            [CONTROL_POINTS_EMPTY_CURRENT_PART, CONTROL_POINTS_EMPTY_SEE_DOCUMENTATION],
        )

    def test_points_only_in_terrain_shows_redirect_on_documentation(self) -> None:
        section = _section_with_points(documentation=0, terrain=2)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertIsNotNone(self._panel(widget))
        self.assertEqual(self._titles(widget), [])
        self.assertEqual(
            self._empty_info_texts(widget),
            [CONTROL_POINTS_EMPTY_CURRENT_PART, CONTROL_POINTS_EMPTY_SEE_TERRAIN],
        )

    def test_area_without_any_points_shows_none_message(self) -> None:
        section = _section_with_points(documentation=0, terrain=0)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertIsNotNone(self._panel(widget))
        self.assertEqual(self._empty_info_texts(widget), [CONTROL_POINTS_EMPTY_AREA_NONE])
        self.assertNotIn(AREA_NOT_IMPLEMENTED_TEXT, self._empty_info_texts(widget))

    def test_unimplemented_area_keeps_original_message(self) -> None:
        from moduly.proverky.sluzby.proverky_knowledge_service import (
            KNOWLEDGE_NODE_AREA,
            KnowledgeTreeNode,
        )

        widget = BozpInspectionAreasWidget(verification_type=VERIFICATION_TYPE_DOCUMENTATION)
        unimplemented = KnowledgeTreeNode(
            node_type=KNOWLEDGE_NODE_AREA,
            node_id="neexistujici_oblast",
            label="Neexistující oblast",
            area_id="neexistujici_oblast",
            area_label="Neexistující oblast",
            children=(),
        )
        widget._on_area_selected(unimplemented)
        self.assertEqual(widget.content_stack.currentIndex(), widget._PAGE_PLACEHOLDER)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn(AREA_NOT_IMPLEMENTED_TEXT, labels)

    def test_switch_documentation_terrain_updates_empty_card(self) -> None:
        section = _section_with_points(documentation=0, terrain=2)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(
            self._empty_info_texts(widget),
            [CONTROL_POINTS_EMPTY_CURRENT_PART, CONTROL_POINTS_EMPTY_SEE_TERRAIN],
        )

        widget.set_verification_filter(VERIFICATION_TYPE_TERRAIN)
        self.assertEqual(len(self._titles(widget)), 2)
        self.assertEqual(self._empty_info_texts(widget), [])

        widget.set_verification_filter(VERIFICATION_TYPE_DOCUMENTATION)
        self.assertEqual(self._titles(widget), [])
        self.assertEqual(
            self._empty_info_texts(widget),
            [CONTROL_POINTS_EMPTY_CURRENT_PART, CONTROL_POINTS_EMPTY_SEE_TERRAIN],
        )


if __name__ == "__main__":
    unittest.main()
