"""Fáze 97q – Index procesu: detail výpočtu."""

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
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_SPLNENO,
        COMPLIANCE_STATUS_LABELS,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        PROCESS_INDEX_DETAIL_PROMPT,
        LegalRequirementProcessIndexWidget,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.ukoly.modely.task import Task


class LegalRequirementProcessIndexPhase97qTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._parent = legal_requirement_service.create_requirement(
            title="Kořenový proces",
            process_code="P-060",
        )

    def _detail_texts(self, widget: LegalRequirementProcessIndexWidget) -> list[str]:
        return [label.text() for label in widget.detail_panel.findChildren(QLabel)]

    def test_prompt_when_no_scores(self) -> None:
        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        self.assertEqual(widget.table.selectedIndexes(), [])
        self.assertIn(PROCESS_INDEX_DETAIL_PROMPT, self._detail_texts(widget))

    def test_auto_selects_first_scored_area_and_shows_detail(self) -> None:
        legal_requirement_service.create_requirement(
            title="Splněný",
            process_code="P-060.1",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_SPLNENO,
        )
        legal_requirement_service.create_requirement(
            title="Částečný",
            process_code="P-060.2",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
        )

        widget = LegalRequirementProcessIndexWidget(self._parent.id)

        selected_rows = {index.row() for index in widget.table.selectedIndexes()}
        self.assertEqual(selected_rows, {2})
        texts = self._detail_texts(widget)
        self.assertIn("Právní požadavky", texts)
        self.assertIn("Skóre: 75,0 %", texts)
        self.assertIn("Přínos: 18,8", texts)
        self.assertIn(f"• {COMPLIANCE_STATUS_LABELS[COMPLIANCE_SPLNENO]}: 1", texts)
        self.assertIn(
            f"• {COMPLIANCE_STATUS_LABELS[COMPLIANCE_CASTECNE_SPLNENO]}: 1",
            texts,
        )
        self.assertTrue(any(text.startswith("• Splněno: 100 b.") for text in texts))
        self.assertTrue(any("Výpočet:" == text for text in texts))
        self.assertNotIn(PROCESS_INDEX_DETAIL_PROMPT, texts)

    def test_switching_row_updates_detail(self) -> None:
        legal_requirement_service.create_requirement(
            title="Splněný",
            process_code="P-060.1",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_SPLNENO,
        )

        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        self.assertIn("Právní požadavky", self._detail_texts(widget))

        widget.table.selectRow(0)
        texts = self._detail_texts(widget)
        self.assertIn("Audity", texts)
        self.assertTrue(
            any("Proces nemá přiřazena žádná auditní tvrzení." in text for text in texts)
            or any("podklady výpočtu" in text for text in texts)
            or any("Výpočet:" == text for text in texts)
        )


if __name__ == "__main__":
    unittest.main()
