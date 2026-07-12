"""Fáze 97r – Index procesu: zpřehlednění detailu výpočtu."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel
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
        COMPLIANCE_NENI_RELEVANTNI,
        COMPLIANCE_SPLNENO,
        COMPLIANCE_STATUS_LABELS,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.ukoly.modely.task import Task


class LegalRequirementProcessIndexPhase97rTestCase(unittest.TestCase):
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
            process_code="P-070",
        )
        legal_requirement_service.create_requirement(
            title="Splněný",
            process_code="P-070.1",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_SPLNENO,
        )
        legal_requirement_service.create_requirement(
            title="Nerelevantní",
            process_code="P-070.2",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_NENI_RELEVANTNI,
        )

    def test_detail_groups_order_and_content(self) -> None:
        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        groups = widget.detail_panel.findChildren(QGroupBox)
        titles = [group.title() for group in groups]
        self.assertEqual(
            titles,
            [
                "Výsledek",
                "Zdroj dat",
                "Počty podle stavů",
                "Bodové hodnocení",
                "Výpočet",
            ],
        )

        result_labels = [label.text() for label in groups[0].findChildren(QLabel)]
        self.assertEqual(
            result_labels,
            [
                "Skóre: 100,0 %",
                "Přínos: 25,0",
                "Metodická váha: 25 %",
            ],
        )

        points_labels = [label.text() for label in groups[3].findChildren(QLabel)]
        self.assertTrue(any("Splněno: 100 b." in text for text in points_labels))
        self.assertFalse(
            any(
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_NENI_RELEVANTNI] in text
                and "b." in text
                for text in points_labels
            )
        )

        status_labels = [label.text() for label in groups[2].findChildren(QLabel)]
        self.assertTrue(
            any(
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_NENI_RELEVANTNI] in text
                for text in status_labels
            )
        )


if __name__ == "__main__":
    unittest.main()
