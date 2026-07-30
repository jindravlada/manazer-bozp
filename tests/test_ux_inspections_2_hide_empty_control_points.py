"""UX-INSPECTIONS-2: skrytí prázdné sekce Kontrolní body."""

from __future__ import annotations

import os
import unittest
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from moduly.proverky.constants import (
    AREA_PART_NO_CONTROL_QUESTIONS_TEXT,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
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


class UxInspections2HideEmptyControlPointsTestCase(unittest.TestCase):
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
    def _has_control_points_panel(widget: BozpKnowledgeSectionWidget) -> bool:
        return widget.findChild(QScrollArea, "ControlPointsPanel") is not None

    @staticmethod
    def _control_point_titles(widget: BozpKnowledgeSectionWidget) -> list[str]:
        return [
            label.text()
            for label in widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]

    def test_section_with_control_points_shows_panel(self) -> None:
        section = _section_with_points(documentation=2, terrain=0)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertTrue(self._has_control_points_panel(widget))
        self.assertEqual(len(self._control_point_titles(widget)), 2)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Kontrolní body", labels)
        self.assertNotIn(AREA_PART_NO_CONTROL_QUESTIONS_TEXT, labels)

    def test_section_without_control_points_omits_panel(self) -> None:
        section = _section_with_points(documentation=0, terrain=3)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertFalse(self._has_control_points_panel(widget))
        self.assertEqual(self._control_point_titles(widget), [])
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertNotIn("Kontrolní body", labels)
        self.assertNotIn(AREA_PART_NO_CONTROL_QUESTIONS_TEXT, labels)
        # Ostatní bloky zůstávají (typické závady).
        self.assertTrue(any("Závada" in text for text in labels))

    def test_switch_documentation_terrain_shows_or_hides_panel(self) -> None:
        section = _section_with_points(documentation=0, terrain=2)
        widget = self._show(section, VERIFICATION_TYPE_DOCUMENTATION)
        self.assertFalse(self._has_control_points_panel(widget))

        widget.set_verification_filter(VERIFICATION_TYPE_TERRAIN)
        self.assertTrue(self._has_control_points_panel(widget))
        self.assertEqual(len(self._control_point_titles(widget)), 2)

        widget.set_verification_filter(VERIFICATION_TYPE_DOCUMENTATION)
        self.assertFalse(self._has_control_points_panel(widget))
        self.assertEqual(self._control_point_titles(widget), [])
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertNotIn(AREA_PART_NO_CONTROL_QUESTIONS_TEXT, labels)


if __name__ == "__main__":
    unittest.main()
