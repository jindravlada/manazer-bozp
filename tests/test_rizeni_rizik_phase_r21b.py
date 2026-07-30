"""R21b – terminologie identifikace a úprava seznamu posouzení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

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
        HAZARD_IDENTIFICATION_VISIBLE_TABS,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        INVENTORY_INTRO_TEXT,
        RISK_ASSESSMENT_COL_ACTIVE,
        RISK_ASSESSMENT_COL_COMPLETED_AT,
        RISK_ASSESSMENT_COL_EVENT,
        RISK_ASSESSMENT_COL_EXPOSED_GROUP,
        RISK_ASSESSMENT_COL_INVENTORY_ITEM,
        RISK_ASSESSMENT_COL_SEVERITY,
        RISK_ASSESSMENT_COL_STATUS,
        RISK_ASSESSMENT_TABLE_HEADERS,
        RISK_ASSESSMENTS_INTRO_TEXT,
        RISK_SEVERITY_MODERATE,
        TAB_INVENTORY,
        TAB_RISK_ASSESSMENT,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import (
        HazardRiskAssessmentsWidget,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PhaseR21bTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        operation = settings_service.save_workplace(
            name="Provoz R21b",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R21b",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        cls.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=cls.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Dlouhý název zdroje rizika pro ověření elipsy v tabulce posouzení",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=cls.identification.id,
            inventory_item_id=item.id,
            name=(
                "Velmi dlouhý název nežádoucí události, který se má při úzkém "
                "sloupci zkrátit elipsou"
            ),
        )
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=cls.identification.id,
            hazard_event_id=event.id,
            exposed_group_id=ensure_exposed_group("Zaměstnanci").id,
            severity=RISK_SEVERITY_MODERATE,
        )

    def test_tab_labels(self) -> None:
        self.assertEqual(TAB_INVENTORY, "Zdroje rizik")
        self.assertEqual(TAB_RISK_ASSESSMENT, "Posouzení rizik")
        self.assertEqual(
            list(HAZARD_IDENTIFICATION_VISIBLE_TABS)[2:],
            [TAB_INVENTORY, TAB_RISK_ASSESSMENT],
        )
        dialog = HazardIdentificationDialog(identification=self.identification)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(labels, list(HAZARD_IDENTIFICATION_VISIBLE_TABS))

    def test_identification_texts_follow_master_model(self) -> None:
        self.assertIn("katalogových zdrojů rizik", INVENTORY_INTRO_TEXT)
        self.assertNotIn("Popište pracoviště", INVENTORY_INTRO_TEXT)
        self.assertIn("katalogových zdrojů", RISK_ASSESSMENTS_INTRO_TEXT)
        self.assertEqual(RISK_ASSESSMENT_TABLE_HEADERS[3], "Zdroj rizika")
        self.assertNotIn("Zdroj analýzy", RISK_ASSESSMENT_TABLE_HEADERS)

    def test_assessment_table_column_widths(self) -> None:
        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        table = widget.table
        header = table.horizontalHeader()

        self.assertEqual(table.columnWidth(RISK_ASSESSMENT_COL_INVENTORY_ITEM), 220)
        self.assertEqual(table.columnWidth(RISK_ASSESSMENT_COL_SEVERITY), 110)
        self.assertEqual(table.columnWidth(RISK_ASSESSMENT_COL_STATUS), 130)
        self.assertEqual(table.columnWidth(RISK_ASSESSMENT_COL_COMPLETED_AT), 120)
        self.assertEqual(table.columnWidth(RISK_ASSESSMENT_COL_ACTIVE), 70)
        self.assertEqual(
            header.sectionResizeMode(RISK_ASSESSMENT_COL_ACTIVE),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            header.sectionResizeMode(RISK_ASSESSMENT_COL_EXPOSED_GROUP),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(RISK_ASSESSMENT_COL_EVENT),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertFalse(table.wordWrap())

    def test_assessment_table_responsive_on_resize(self) -> None:
        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        table = widget.table
        header = table.horizontalHeader()
        from PySide6.QtWidgets import QApplication

        fixed_columns = {
            RISK_ASSESSMENT_COL_INVENTORY_ITEM: 220,
            RISK_ASSESSMENT_COL_SEVERITY: 110,
            RISK_ASSESSMENT_COL_STATUS: 130,
            RISK_ASSESSMENT_COL_COMPLETED_AT: 120,
            RISK_ASSESSMENT_COL_ACTIVE: 70,
        }

        widget.show()
        for width in (1400, 1100, 900):
            widget.resize(width, 600)
            table.resize(max(width - 40, 400), 280)
            QApplication.processEvents()
            for column, expected in fixed_columns.items():
                self.assertEqual(
                    header.sectionResizeMode(column),
                    QHeaderView.ResizeMode.Fixed,
                )
                self.assertEqual(table.columnWidth(column), expected)
            self.assertEqual(
                header.sectionResizeMode(RISK_ASSESSMENT_COL_EXPOSED_GROUP),
                QHeaderView.ResizeMode.Stretch,
            )
            self.assertEqual(
                header.sectionResizeMode(RISK_ASSESSMENT_COL_EVENT),
                QHeaderView.ResizeMode.Stretch,
            )
            # Ušetřená šířka se dělí rovnoměrně mezi textové sloupce.
            group_width = table.columnWidth(RISK_ASSESSMENT_COL_EXPOSED_GROUP)
            event_width = table.columnWidth(RISK_ASSESSMENT_COL_EVENT)
            self.assertAlmostEqual(group_width, event_width, delta=2)

        event_item = table.item(0, RISK_ASSESSMENT_COL_EVENT)
        source_item = table.item(0, RISK_ASSESSMENT_COL_INVENTORY_ITEM)
        assert event_item is not None
        assert source_item is not None
        self.assertTrue(event_item.text())
        self.assertTrue(source_item.text())
        self.assertTrue(event_item.toolTip())
        self.assertTrue(source_item.toolTip())


if __name__ == "__main__":
    unittest.main()
