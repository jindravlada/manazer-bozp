"""INSPECTIONS-QUESTIONS-2: diagnostika ztráty kontrolních otázek.

Reálná uživatelská metodika (manazer-bozp/chemicke_latky.json) má u sekce
„Bezpečnostní listy“:

- 5 aktivních kontrolních bodů typu ``teren``,
- ale ``sekce.aktivni = False``.

Tento test zachycuje přesné počty v každém kroku toku a dokládá, že první
místo ztráty 5 → 0 je filtrování neaktivních sekcí při sestavení stromu
prověrky (``get_active_sections`` / ``get_knowledge_tree``), nikoli dělení
Dokumentace/Terén ani vykreslení widgetu.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="inspections-questions-2-"))
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
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_verification_service import (
        inspection_verification_service,
    )
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


_CHEMIE = "chemie"
_BL = "bezpecnostni_listy"
logger = logging.getLogger("inspections_questions_2.diagnostics")


def _diagnose(section: dict) -> dict:
    """Vrátí diagnostické počty pro jeden průchod toku (pro log i asserty)."""
    raw = list(section.get("kontrolni_body") or [])
    active = proverky_knowledge_service.get_active_items(raw)
    docs, terrain, unknown = inspection_verification_service.partition_active_control_points(raw)
    areas = proverky_knowledge_service.get_areas()
    active_sections = proverky_knowledge_service.list_sections(_CHEMIE, include_inactive=False)
    all_sections = proverky_knowledge_service.list_sections(_CHEMIE, include_inactive=True)
    tree = proverky_knowledge_service.get_knowledge_tree(include_inactive=False)
    chem = next(root for root in tree if root.area_id == _CHEMIE)
    report = {
        "areas": len(areas),
        "active_sections": len(active_sections),
        "all_sections": len(all_sections),
        "section_aktivni": bool(section.get("aktivni", True)),
        "raw_control_points": len(raw),
        "active_control_points": len(active),
        "point_details": [
            {
                "id": item.get("id"),
                "aktivni": item.get("aktivni", True),
                "verification_type": item.get("verification_type"),
                "poradi": item.get("poradi"),
            }
            for item in raw
            if isinstance(item, dict)
        ],
        "partition_documentation": len(docs),
        "partition_terrain": len(terrain),
        "partition_unknown": len(unknown),
        "inspection_tree_children": len(chem.children),
        "bl_in_inspection_tree": any(child.node_id == _BL for child in chem.children),
    }
    logger.info("INSPECTIONS-QUESTIONS-2 diagnostics: %s", report)
    return report


class InspectionsQuestions2DiagnosticsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        proverky_knowledge_service.ensure_catalogs()
        self._install_repro_methodology()

    def _install_repro_methodology(self) -> None:
        """Reprodukce stavu z reálné uživatelské metodiky."""
        path = proverky_knowledge_service.proverky_dir / "chemicke_latky.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in data.get("sekce") or []:
            if not isinstance(section, dict):
                continue
            # Všechny sekce neaktivní – jako v uživatelských datech.
            section["aktivni"] = False
            if section.get("id") != _BL:
                continue
            section["kontrolni_body"] = [
                {
                    "id": "dostupnost",
                    "nazev": "Bezpečnostní listy jsou dostupné",
                    "popis": "",
                    "poradi": 10,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                    "verification_type": "teren",
                },
                {
                    "id": "aktualnost",
                    "nazev": "Bezpečnostní listy jsou aktuální",
                    "popis": "",
                    "poradi": 20,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                    "verification_type": "teren",
                },
                {
                    "id": "cesky_jazyk",
                    "nazev": "Bezpečnostní listy jsou v českém jazyce",
                    "popis": "",
                    "poradi": 30,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                    "verification_type": "teren",
                },
                {
                    "id": "pristup_zamestnancu",
                    "nazev": "Zaměstnanci mají přístup k bezpečnostním listům",
                    "popis": "",
                    "poradi": 40,
                    "aktivni": True,
                    "zavaznost": "vysoka",
                    "verification_type": "teren",
                },
                {
                    "id": "prakticka_kontrola",
                    "nazev": "Vedoucí zná umístění bezpečnostních listů",
                    "popis": "",
                    "poradi": 50,
                    "aktivni": True,
                    "zavaznost": "stredni",
                    "verification_type": "teren",
                },
            ]
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_drop_happens_at_inactive_section_filter_not_at_type_split(self) -> None:
        section = proverky_knowledge_service.get_section(_CHEMIE, _BL)
        self.assertIsNotNone(section)
        assert section is not None

        report = _diagnose(section)

        # 1–2: oblast existuje, ale aktivní sekce chybí.
        self.assertGreaterEqual(report["areas"], 1)
        self.assertEqual(report["section_aktivni"], False)
        self.assertEqual(report["active_sections"], 0)
        self.assertGreaterEqual(report["all_sections"], 1)

        # 3–5: metodika stále drží 5 aktivních bodů typu Terén.
        self.assertEqual(report["raw_control_points"], 5)
        self.assertEqual(report["active_control_points"], 5)
        self.assertTrue(
            all(row["aktivni"] and row["verification_type"] == "teren" for row in report["point_details"])
        )

        # 6: dělení Dokumentace/Terén body NEZTRÁCÍ – všech 5 je Terén.
        self.assertEqual(report["partition_documentation"], 0)
        self.assertEqual(report["partition_terrain"], 5)
        self.assertEqual(report["partition_unknown"], 0)

        # *** PRVNÍ MÍSTO ZTRÁTY 5 → 0 ***
        # get_active_sections / inspection tree vyřadí neaktivní sekci.
        self.assertEqual(report["inspection_tree_children"], 0)
        self.assertFalse(report["bl_in_inspection_tree"])

        inspection = bozp_inspection_service.create_inspection()
        listed = inspection_verification_service.list_control_points(
            inspection.id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        bl_listed = [row for row in listed if row.section_id == _BL]
        self.assertEqual(
            len(bl_listed),
            0,
            "Collector vychází z aktivního stromu – body se sem vůbec nedostanou.",
        )

        # 7–8: pokud sekci do widgetu vnútíme přímo, 5 řádků se vykreslí.
        widget = BozpKnowledgeSectionWidget()
        widget.set_verification_filter(VERIFICATION_TYPE_TERRAIN)
        widget.set_section(
            section,
            area_id=_CHEMIE,
            area_label="Chemické látky a směsi",
            section_label="Bezpečnostní listy",
        )
        titles = [
            label.text()
            for label in widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]
        self.assertEqual(len(titles), 5)

        # Editor prověrky sekci nenajde → 0 otázek / oblastní oblast.
        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.show()
        QApplication.processEvents()
        selected = dialog.terrain_widget.knowledge_tree.select_node(_CHEMIE, _BL)
        self.assertFalse(selected)
        tree_titles = [
            label.text()
            for label in dialog.terrain_widget.knowledge_widget.findChildren(QLabel)
            if label.objectName() == "ControlPointTitle"
        ]
        self.assertEqual(tree_titles, [])

        chem_node = next(
            root
            for root in proverky_knowledge_service.get_knowledge_tree()
            if root.area_id == _CHEMIE
        )
        dialog.terrain_widget._on_area_selected(chem_node)
        self.assertEqual(
            dialog.terrain_widget.content_stack.currentIndex(),
            dialog.terrain_widget._PAGE_PLACEHOLDER,
        )
        placeholder_texts = [
            label.text()
            for label in dialog.terrain_widget.findChildren(QLabel)
            if label.text() == AREA_NOT_IMPLEMENTED_TEXT
        ]
        self.assertTrue(placeholder_texts)
        dialog.close()

    def test_methodology_editor_tree_still_sees_inactive_section(self) -> None:
        """Editor metodiky používá include_inactive=True – proto otázky „vidí“."""
        tree = proverky_knowledge_service.get_knowledge_tree(include_inactive=True)
        chem = next(root for root in tree if root.area_id == _CHEMIE)
        bl = next(child for child in chem.children if child.node_id == _BL)
        self.assertIsNotNone(bl.section)
        assert bl.section is not None
        self.assertFalse(bl.section.get("aktivni", True))
        active = proverky_knowledge_service.get_active_items(bl.section.get("kontrolni_body"))
        self.assertEqual(len(active), 5)
        docs, terrain, _unknown = inspection_verification_service.partition_active_control_points(
            bl.section.get("kontrolni_body"),
        )
        self.assertEqual(len(terrain), 5)
        self.assertEqual(len(docs), 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
