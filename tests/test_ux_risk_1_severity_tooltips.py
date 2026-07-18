"""UX-RISK-1 – tooltipy závažnosti z jednoho společného číselníku."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.risk_severity import (
        RISK_SEVERITY_DESCRIPTIONS,
        RISK_SEVERITY_LABELS,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
        format_risk_severity_description,
        format_risk_severity_tooltip,
    )
    from core.widgets.severity_tooltips import populate_severity_combo
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_DESCRIPTIONS as MODULE_DESCRIPTIONS,
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
    from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import (
        HazardRiskAssessmentDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import (
        HazardRiskAssessmentsWidget,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class UxRisk1SeverityTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        operation = settings_service.save_workplace(
            name="Provoz UX-RISK-1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště UX-RISK-1",
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
            name="Jeřáb",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=cls.identification.id,
            inventory_item_id=item.id,
            name="Pád břemene",
        )
        cls.assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=cls.identification.id,
            hazard_event_id=event.id,
            exposed_group_id=ensure_exposed_group("Zaměstnanci").id,
            severity=RISK_SEVERITY_MINOR,
        )

    def test_shared_codebook_texts_unchanged(self) -> None:
        self.assertEqual(
            RISK_SEVERITY_DESCRIPTIONS[RISK_SEVERITY_MINOR],
            "Lehké zranění nebo zdravotní obtíže bez pracovní neschopnosti.",
        )
        self.assertIs(MODULE_DESCRIPTIONS, RISK_SEVERITY_DESCRIPTIONS)

    def test_tooltip_format_matches_editor_description(self) -> None:
        tooltip = format_risk_severity_tooltip(RISK_SEVERITY_MINOR)
        self.assertEqual(
            tooltip,
            "Lehký\n\nLehké zranění nebo zdravotní obtíže bez pracovní neschopnosti.",
        )
        self.assertEqual(
            format_risk_severity_description(RISK_SEVERITY_MINOR),
            RISK_SEVERITY_DESCRIPTIONS[RISK_SEVERITY_MINOR],
        )
        self.assertEqual(RISK_SEVERITY_LABELS[RISK_SEVERITY_MINOR], "Lehký")

    def test_table_cell_has_severity_tooltip(self) -> None:
        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(self.identification.id, read_only=False)
        from moduly.rizeni_rizik.constants import RISK_ASSESSMENT_COL_SEVERITY

        item = widget.table.item(0, RISK_ASSESSMENT_COL_SEVERITY)
        assert item is not None
        self.assertEqual(item.text(), "Lehký")
        self.assertIn("Lehké zranění", item.toolTip())
        self.assertIn("Lehký", item.toolTip())

    def test_combo_items_have_tooltips(self) -> None:
        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        populate_severity_combo(combo, current=RISK_SEVERITY_MODERATE)
        minor_index = combo.findData(RISK_SEVERITY_MINOR)
        self.assertGreaterEqual(minor_index, 0)
        tooltip = combo.itemData(minor_index, Qt.ItemDataRole.ToolTipRole)
        self.assertEqual(
            tooltip,
            "Lehký\n\nLehké zranění nebo zdravotní obtíže bez pracovní neschopnosti.",
        )
        self.assertIn("Závažný", combo.toolTip())

    def test_assessment_dialog_description_from_shared_source(self) -> None:
        dialog = HazardRiskAssessmentDialog(
            hazard_identification_id=self.identification.id,
            assessment=self.assessment,
        )
        self.assertEqual(
            dialog.severity_description.text(),
            RISK_SEVERITY_DESCRIPTIONS[RISK_SEVERITY_MINOR],
        )
        minor_index = dialog.severity.findData(RISK_SEVERITY_MINOR)
        tooltip = dialog.severity.itemData(minor_index, Qt.ItemDataRole.ToolTipRole)
        self.assertIn("Lehké zranění", tooltip)


if __name__ == "__main__":
    unittest.main()
