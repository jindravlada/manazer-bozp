"""UX-COORD-1 – názvosloví a hlavní seznam koordinací."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QLabel

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.table_utils import configure_table_columns
    from moduly.koordinace_bozp.constants import (
        COL_MEETING_DATE,
        COL_NUMBER,
        COL_PBP,
        COL_PLACE,
        COL_STATUS,
        COL_SUBJECT,
        COL_VALIDITY,
        LABEL_ACTION_NAME,
        LABEL_MEETING_DATE,
        LABEL_MEETING_PLACE,
        SUBJECT_REQUIRED_MESSAGE,
        TABLE_HEADERS,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        BozpCoordinationError,
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import (
        BozpCoordinationDialog,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable


def _basics_label_texts(dialog: BozpCoordinationDialog) -> list[str]:
    basics = dialog.tabs.widget(0)
    return [
        (widget.text() or "").strip()
        for widget in basics.findChildren(QLabel)
        if (widget.text() or "").strip()
    ]


class UxCoord1NomenclatureTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_table_headers(self) -> None:
        self.assertEqual(TABLE_HEADERS[COL_NUMBER], "Číslo")
        self.assertEqual(TABLE_HEADERS[COL_MEETING_DATE], "Datum schůzky")
        self.assertEqual(TABLE_HEADERS[COL_PLACE], "Místo")
        self.assertEqual(TABLE_HEADERS[COL_SUBJECT], "Název akce")
        self.assertEqual(TABLE_HEADERS[COL_STATUS], "Stav")
        self.assertEqual(TABLE_HEADERS[COL_VALIDITY], "Platnost")
        self.assertEqual(TABLE_HEADERS[COL_PBP], "Příloha PBP")
        self.assertNotIn("Datum koordinační schůzky", TABLE_HEADERS)
        self.assertNotIn("Předmět koordinace", TABLE_HEADERS)

        table = BozpCoordinationTable()
        headers = [
            table.horizontalHeaderItem(i).text()
            for i in range(1, table.columnCount())
        ]
        self.assertEqual(headers, TABLE_HEADERS[1:])

    def test_subject_column_is_widest_stretch(self) -> None:
        table = BozpCoordinationTable()
        configure_table_columns(table, "bozp_coordinations")
        header = table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(COL_SUBJECT),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (
            COL_NUMBER,
            COL_MEETING_DATE,
            COL_PLACE,
            COL_STATUS,
            COL_VALIDITY,
            COL_PBP,
        ):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
            )
        self.assertGreater(
            table.columnWidth(COL_SUBJECT),
            table.columnWidth(COL_NUMBER),
        )

    def test_editor_field_labels(self) -> None:
        dialog = BozpCoordinationDialog(None)
        labels = _basics_label_texts(dialog)
        self.assertIn(f"{LABEL_MEETING_DATE}:", labels)
        self.assertIn(f"{LABEL_MEETING_PLACE}:", labels)
        self.assertIn(f"{LABEL_ACTION_NAME} *:", labels)
        self.assertNotIn("Datum koordinační schůzky:", labels)
        self.assertNotIn("Místo:", labels)
        self.assertNotIn("Předmět koordinace *:", labels)
        dialog.close()

    def test_editor_opens_maximized(self) -> None:
        dialog = BozpCoordinationDialog(None)
        self.assertTrue(
            bool(dialog.windowState() & Qt.WindowState.WindowMaximized)
        )
        dialog.showMaximized()
        self.assertTrue(
            dialog.isMaximized()
            or bool(dialog.windowState() & Qt.WindowState.WindowMaximized)
        )
        dialog.close()

        page_file = (
            Path(__file__).resolve().parents[1]
            / "moduly/koordinace_bozp/ui/koordinace_bozp_page.py"
        )
        text = page_file.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("dialog.showMaximized()"), 2)

    def test_validation_uses_new_label(self) -> None:
        with self.assertRaises(BozpCoordinationError) as ctx:
            bozp_coordination_service.create_coordination(subject="  ")
        self.assertEqual(str(ctx.exception), SUBJECT_REQUIRED_MESSAGE)
        self.assertIn("Název akce", str(ctx.exception))
        self.assertNotIn("Předmět koordinace", str(ctx.exception))

    def test_export_uses_new_action_name_label(self) -> None:
        target = _TMP / "ux-coord-1-export.odt"
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data={
                "basics": {
                    "coordination_number": "K-1",
                    "subject": "Akce ze dat",
                    "meeting_date": "2026-07-19",
                    "place": "Praha",
                },
                "employers": [],
                "participants_by_employer": [],
                "coordinator": None,
                "workplaces": [],
                "activities_by_employer": [],
                "measures_by_category": [],
                "contacts": [],
                "emergency_procedures": {},
                "risk_handovers": [],
                "pbp_snapshot": None,
                "attachments_by_group": [],
            },
            warnings=[],
            summary={"warnings_total": 0},
        )
        with zipfile.ZipFile(target) as zin:
            content = zin.read("content.xml").decode("utf-8")
        self.assertIn("Název akce: Akce ze dat", content)
        self.assertNotIn("Předmět:", content)
        self.assertNotIn("Předmět koordinace", content)

    def test_no_data_migration_needed(self) -> None:
        """Pole subject zůstává v DB – mění se jen uživatelské názvosloví."""
        from core.database.database_initializer import _table_columns

        columns = _table_columns("bozp_coordinations")
        self.assertIn("subject", columns)
        self.assertNotIn("action_name", columns)


if __name__ == "__main__":
    unittest.main()
