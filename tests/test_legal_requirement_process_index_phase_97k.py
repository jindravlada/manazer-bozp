"""Fáze 97k – Index procesu: rozpad hodnocení."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_INDEX_AREA_WEIGHTS,
        PROCESS_INDEX_PLACEHOLDER,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )


class LegalRequirementProcessIndexPhase97kTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="Proces pro index",
            process_code="P-040",
        )

    def test_breakdown_has_four_areas_and_weights_sum_100(self) -> None:
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self._requirement.id,
        )

        self.assertEqual(len(breakdown.areas), 4)
        self.assertEqual(
            [item.area_label for item in breakdown.areas],
            ["Audity", "Prověrky", "Právní požadavky", "Úkoly"],
        )
        self.assertEqual(
            [item.weight_percent for item in breakdown.areas],
            [weight for _area_id, _label, weight in PROCESS_INDEX_AREA_WEIGHTS],
        )
        self.assertEqual(breakdown.total_weight_percent, 100)
        self.assertIsNone(breakdown.index_value)
        self.assertTrue(all(item.score is None for item in breakdown.areas))
        self.assertTrue(all(item.contribution is None for item in breakdown.areas))

    def test_dialog_has_index_tab_after_status(self) -> None:
        dialog = LegalRequirementDialog(requirement=self._requirement)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertIn("Index procesu", labels)
        self.assertIn("Stav procesu", labels)
        self.assertEqual(
            labels.index("Index procesu"),
            labels.index("Stav procesu") + 1,
        )
        self.assertIsNotNone(dialog.process_index_widget)

    def test_widget_shows_placeholder_score_and_footer(self) -> None:
        widget = LegalRequirementProcessIndexWidget(self._requirement.id)

        self.assertEqual(widget.table.rowCount(), 4)
        self.assertEqual(widget.table.item(0, 0).text(), "Audity")
        self.assertEqual(widget.table.item(0, 1).text(), "30")
        self.assertEqual(widget.table.item(0, 2).text(), PROCESS_INDEX_PLACEHOLDER)
        self.assertEqual(widget.table.item(0, 3).text(), PROCESS_INDEX_PLACEHOLDER)
        self.assertEqual(widget.total_weight_label.text(), "Součet vah: 100 %")
        self.assertIn("Index procesu:", widget.index_label.text())
        self.assertIn(PROCESS_INDEX_PLACEHOLDER, widget.index_label.text())

        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertTrue(any("Index procesu" == text for text in labels))


if __name__ == "__main__":
    unittest.main()
