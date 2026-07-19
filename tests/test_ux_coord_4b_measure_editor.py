"""UX-COORD-4b: zjednodušení editoru organizačních opatření."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-4b-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        MEASURE_CATEGORY_COMMUNICATION,
        MEASURE_EDITOR_HELP_TEXT,
        MEASURE_TABLE_HEADERS,
        MSR_COL_ACTIVE,
        MSR_COL_CATEGORY,
        MSR_COL_DESCRIPTION,
        MSR_COL_TITLE,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        protocol_measure_display_text,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_measure_dialog import (
        CoordinationMeasureDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_measure_table import (
        CoordinationMeasureTable,
    )
    from moduly.koordinace_bozp.ui.coordination_measures_tab import (
        CoordinationMeasuresTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord4bMeasureEditorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def _create_coordination(self, **kwargs):
        return bozp_coordination_service.create_coordination(
            subject="Testovací akce",
            meeting_date=date(2026, 7, 17),
            place="Praha",
            **kwargs,
        )

    def test_dialog_field_labels_and_help(self) -> None:
        dialog = CoordinationMeasureDialog()
        labels = {
            widget.text()
            for widget in dialog.findChildren(QLabel)
            if widget.text().strip()
        }
        self.assertIn("Kategorie *:", labels)
        self.assertIn("Krátký název *:", labels)
        self.assertIn("Text opatření:", labels)
        self.assertIn(MEASURE_EDITOR_HELP_TEXT, labels)
        self.assertTrue(dialog.description.isEnabled())
        self.assertGreaterEqual(dialog.description.minimumHeight(), 80)

    def test_save_short_title_and_measure_text(self) -> None:
        coordination = self._create_coordination()
        item = coordination_measure_service.add(
            coordination.id,
            category=MEASURE_CATEGORY_COMMUNICATION,
            title="Zákaz vstupu",
            description="Do prostoru stavby je zakázán vstup nepovolaným osobám.",
        )
        loaded = coordination_measure_service.get_by_id(item.id)
        assert loaded is not None
        self.assertEqual(loaded.title, "Zákaz vstupu")
        self.assertEqual(
            loaded.description,
            "Do prostoru stavby je zakázán vstup nepovolaným osobám.",
        )

        updated = coordination_measure_service.update(
            item.id,
            category=MEASURE_CATEGORY_COMMUNICATION,
            title="Krátký název",
            description="Úplný text opatření do protokolu.",
        )
        assert updated is not None
        self.assertEqual(updated.title, "Krátký název")
        self.assertEqual(updated.description, "Úplný text opatření do protokolu.")

    def test_fallback_uses_short_title_when_text_empty(self) -> None:
        self.assertEqual(
            protocol_measure_display_text(
                {
                    "title": "Krátký název opatření",
                    "description": "",
                }
            ),
            "Krátký název opatření",
        )
        self.assertEqual(
            protocol_measure_display_text(
                {
                    "title": "Krátký název",
                    "description": "   ",
                }
            ),
            "Krátký název",
        )
        self.assertEqual(
            protocol_measure_display_text(
                {
                    "title": "Krátký",
                    "description": "Úplný text opatření do protokolu",
                }
            ),
            "Úplný text opatření do protokolu",
        )

    def test_table_uses_new_column_headers(self) -> None:
        table = CoordinationMeasureTable()
        self.assertEqual(
            table.horizontalHeaderItem(MSR_COL_CATEGORY).text(),
            "Kategorie",
        )
        self.assertEqual(
            table.horizontalHeaderItem(MSR_COL_TITLE).text(),
            "Krátký název",
        )
        self.assertEqual(
            table.horizontalHeaderItem(MSR_COL_DESCRIPTION).text(),
            "Text opatření",
        )
        self.assertEqual(
            table.horizontalHeaderItem(MSR_COL_ACTIVE).text(),
            "Aktivní",
        )
        self.assertEqual(
            MEASURE_TABLE_HEADERS,
            ["ID", "Kategorie", "Krátký název", "Text opatření", "Aktivní"],
        )
        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)

        coordination = self._create_coordination()
        measure = coordination_measure_service.add(
            coordination.id,
            category=MEASURE_CATEGORY_COMMUNICATION,
            title="Krátký",
            description="Dlouhý text opatření určený do protokolu",
        )
        table.load_measures([measure])
        self.assertEqual(table.item(0, MSR_COL_TITLE).text(), "Krátký")
        self.assertEqual(
            table.item(0, MSR_COL_DESCRIPTION).text(),
            "Dlouhý text opatření určený do protokolu",
        )
        self.assertIn(
            "Dlouhý text opatření určený do protokolu",
            table.item(0, MSR_COL_DESCRIPTION).toolTip(),
        )

    def test_measures_tab_stretches_text_column(self) -> None:
        tab = CoordinationMeasuresTab()
        header = tab.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(MSR_COL_DESCRIPTION),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(MSR_COL_TITLE),
            QHeaderView.ResizeMode.Interactive,
        )

    def test_new_coordination_starts_without_measures(self) -> None:
        coordination = self._create_coordination()
        items = coordination_measure_service.list_for_coordination(coordination.id)
        self.assertEqual(items, [])
        dialog = BozpCoordinationDialog(None)
        self.assertFalse(hasattr(dialog, "insert_default_measures"))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
