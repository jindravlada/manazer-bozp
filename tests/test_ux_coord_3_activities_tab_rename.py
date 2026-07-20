"""UX-COORD-3 – přejmenování záložky činností."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-3-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.koordinace_bozp.constants import (
        PROTOCOL_SECTION_ACTIVITIES,
        TAB_EMPLOYER_ACTIVITIES,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        PROTOCOL_ODT_CHAPTER_TITLES,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_employer_activities_tab import (
        CoordinationEmployerActivitiesTab,
    )
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )


class UxCoord3ActivitiesTabRenameTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_tab_constant_and_dialog_label(self) -> None:
        self.assertEqual(TAB_EMPLOYER_ACTIVITIES, "Činnosti na pracovišti")
        self.assertNotEqual(TAB_EMPLOYER_ACTIVITIES, "Činnosti zaměstnavatelů")

        dialog = BozpCoordinationDialog(None)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn("Činnosti na pracovišti", labels)
        self.assertNotIn("Činnosti zaměstnavatelů", labels)
        dialog.close()

    def test_unavailable_message_uses_new_name(self) -> None:
        tab = CoordinationEmployerActivitiesTab(None, coordination_id=None)
        self.assertIn("Činnosti na pracovišti", tab.unavailable_label.text())
        self.assertNotIn("Činnosti zaměstnavatelů", tab.unavailable_label.text())

    def test_preview_and_odt_chapter_titles(self) -> None:
        self.assertIn(PROTOCOL_SECTION_ACTIVITIES, PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Činnosti zaměstnavatelů", PROTOCOL_ODT_CHAPTER_TITLES)

        preview_file = Path(
            importlib.import_module(
                "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog"
            ).__file__
        )
        text = preview_file.read_text(encoding="utf-8")
        self.assertIn("document_blocks_from_dict", text)
        self.assertNotIn("Činnosti zaměstnavatelů", text)

        odt_file = Path(
            importlib.import_module(
                "moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer"
            ).__file__
        )
        odt_text = odt_file.read_text(encoding="utf-8")
        self.assertIn("PROTOCOL_SECTION_ACTIVITIES", odt_text)
        self.assertNotIn("Činnosti zaměstnavatelů", odt_text)


if __name__ == "__main__":
    unittest.main()
