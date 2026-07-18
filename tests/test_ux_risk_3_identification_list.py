"""UX-RISK-3 – úprava seznamu Identifikací rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        COL_IDENTIFICATION,
        COL_OPERATION,
        COL_STARTED_AT,
        COL_STATUS,
        COL_WORKPLACE,
        COL_WORKPLACE_PART,
        DIALOG_WINDOW_TITLE,
        TABLE_HEADERS,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage


class UxRisk3IdentificationListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        cls.operation = settings_service.save_workplace(
            name="Provoz UX-LIST",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        cls.workplace = settings_service.save_workplace(
            name="Pracoviště UX-LIST",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=cls.operation.id,
        )
        cls.part_alpha = settings_service.save_workplace(
            name="Část Alfa",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=cls.workplace.id,
        )
        cls.part_beta = settings_service.save_workplace(
            name="Část Beta",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=cls.workplace.id,
        )
        cls.person = settings_service.save_worker(first_name="Eva", last_name="Testerová")

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentification))
            session.commit()

    def _create(
        self,
        *,
        workplace_part_id: int | None,
        started_at: date,
        note: str = "",
    ):
        return hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=workplace_part_id,
            responsible_person_id=self.person.id,
            started_at=started_at,
            note=note,
        )

    def test_headers_include_workplace_part_and_identification(self) -> None:
        self.assertIn("Část pracoviště", TABLE_HEADERS)
        self.assertIn("Identifikace", TABLE_HEADERS)
        self.assertEqual(TABLE_HEADERS[COL_WORKPLACE_PART], "Část pracoviště")
        self.assertEqual(TABLE_HEADERS[COL_IDENTIFICATION], "Identifikace")

    def test_identification_column_hidden_workplace_part_visible(self) -> None:
        self._create(workplace_part_id=self.part_alpha.id, started_at=date(2026, 3, 1))
        page = RizeniRizikPage()
        table = page.identifications_tab.table

        self.assertTrue(table.isColumnHidden(COL_IDENTIFICATION))
        self.assertFalse(table.isColumnHidden(COL_WORKPLACE_PART))
        self.assertFalse(table.isColumnHidden(COL_OPERATION))
        self.assertFalse(table.isColumnHidden(COL_WORKPLACE))
        self.assertEqual(table.item(0, COL_WORKPLACE_PART).text(), "Část Alfa")
        # Číslo zůstává v datech tabulky (pro výběry / kompatibilitu), jen není zobrazené.
        self.assertTrue(table.item(0, COL_IDENTIFICATION).text())

    def test_sorted_by_started_at_desc(self) -> None:
        older = self._create(
            workplace_part_id=self.part_alpha.id,
            started_at=date(2026, 1, 10),
        )
        newer = self._create(
            workplace_part_id=self.part_beta.id,
            started_at=date(2026, 6, 15),
        )
        page = RizeniRizikPage()
        table = page.identifications_tab.table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, COL_IDENTIFICATION).text(), newer.identification_number)
        self.assertEqual(table.item(1, COL_IDENTIFICATION).text(), older.identification_number)
        self.assertEqual(table.item(0, COL_WORKPLACE_PART).text(), "Část Beta")
        self.assertEqual(table.item(0, COL_STATUS).text(), "Koncept")
        self.assertEqual(table.item(0, COL_STARTED_AT).text(), "15.06.2026")

    def test_search_matches_workplace_part_not_hidden_identification(self) -> None:
        first = self._create(
            workplace_part_id=self.part_alpha.id,
            started_at=date(2026, 2, 1),
        )
        self._create(
            workplace_part_id=self.part_beta.id,
            started_at=date(2026, 2, 2),
        )
        page = RizeniRizikPage()
        tab = page.identifications_tab
        table = tab.table

        tab.text_filter.search_edit.setText("Alfa")
        visible = [
            row
            for row in range(table.rowCount())
            if not table.isRowHidden(row)
        ]
        self.assertEqual(len(visible), 1)
        self.assertEqual(
            table.item(visible[0], COL_WORKPLACE_PART).text(),
            "Část Alfa",
        )

        # Skrytý sloupec Identifikace se do hledání nepočítá.
        tab.text_filter.search_edit.setText(first.identification_number)
        visible_by_number = [
            row
            for row in range(table.rowCount())
            if not table.isRowHidden(row)
        ]
        self.assertEqual(visible_by_number, [])

        tab.text_filter.search_edit.setText("Provoz UX-LIST")
        visible_by_operation = [
            row
            for row in range(table.rowCount())
            if not table.isRowHidden(row)
        ]
        self.assertEqual(len(visible_by_operation), 2)

    def test_editor_shows_identification_number(self) -> None:
        created = self._create(
            workplace_part_id=self.part_alpha.id,
            started_at=date(2026, 4, 1),
        )
        dialog = HazardIdentificationDialog(None, identification=created)
        try:
            self.assertEqual(
                dialog.basics_widget.identification_number_label.text(),
                created.identification_number,
            )
            self.assertEqual(
                dialog.windowTitle(),
                f"{DIALOG_WINDOW_TITLE} — {created.identification_number}",
            )
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
