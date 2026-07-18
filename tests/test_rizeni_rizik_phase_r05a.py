"""Fáze R05a – přejmenování inventury na analýzu pracoviště."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        EVENT_TABLE_HEADERS,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        INVENTORY_INTRO_TEXT,
        INVENTORY_ITEM_DIALOG_TITLE,
        ITEM_EVENT_TABLE_HEADERS,
        TAB_EVENTS,
        TAB_INVENTORY,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget


class WorkplaceAnalysisTerminologyPhaseR05aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

    def test_tab_label_is_workplace_sources(self) -> None:
        self.assertEqual(TAB_INVENTORY, "Zdroje rizik na pracovišti")

    def test_intro_text_updated(self) -> None:
        self.assertIn("katalogových zdrojů rizik", INVENTORY_INTRO_TEXT)
        self.assertIn("vyskytují", INVENTORY_INTRO_TEXT)
        self.assertNotIn("Inventura", INVENTORY_INTRO_TEXT)
        self.assertNotIn("Popište pracoviště", INVENTORY_INTRO_TEXT)

    def test_event_table_headers(self) -> None:
        self.assertIn("Zdroj rizika", EVENT_TABLE_HEADERS)
        self.assertNotIn("Zdrojová položka inventury", EVENT_TABLE_HEADERS)
        self.assertNotIn("Zdrojová položka analýzy", EVENT_TABLE_HEADERS)
        self.assertNotIn("Zdroj analýzy", EVENT_TABLE_HEADERS)

    def test_inventory_widget_shows_new_intro(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        label = widget.layout().itemAt(0).widget()
        self.assertEqual(label.text(), INVENTORY_INTRO_TEXT)

    def test_dialog_tab_uses_workplace_analysis_label(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog

        dialog = HazardIdentificationDialog(identification=self.identification)
        self.assertEqual(dialog.tabs.tabText(2), TAB_INVENTORY)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertNotIn(TAB_EVENTS, labels)

    def test_inventory_events_table_headers(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        self.assertEqual(
            [
                widget.events_table.horizontalHeaderItem(column).text()
                for column in range(widget.events_table.columnCount())
            ],
            ITEM_EVENT_TABLE_HEADERS,
        )
        self.assertNotIn("Zdroj analýzy", ITEM_EVENT_TABLE_HEADERS)
        self.assertNotIn("Zdroj rizika", ITEM_EVENT_TABLE_HEADERS)
        self.assertIn("Zdroj rizika", EVENT_TABLE_HEADERS)

    def test_inventory_item_service_still_works(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.assertEqual(item.name, "Lokomotiva")
        self.assertEqual(INVENTORY_ITEM_DIALOG_TITLE, "Zdroj rizika na pracovišti")


if __name__ == "__main__":
    unittest.main()
