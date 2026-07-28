"""RISK-IDENT-3: identifikace může být vedena pouze na úrovni provozu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ident-3-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QFormLayout, QLabel

    from core.database.session import get_session
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        HazardIdentificationError,
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
        HazardIdentificationWorkingCopy,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
        HazardIdentificationBasicsWidget,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from sqlalchemy import delete


class RiskIdent3OperationOnlyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz RISK-IDENT-3",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Pracoviště RISK-IDENT-3",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="Část RISK-IDENT-3",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def test_create_operation_only(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=None,
            workplace_part_id=None,
        )
        self.assertEqual(created.operation_id, self.operation.id)
        self.assertIsNone(created.workplace_id)
        self.assertIsNone(created.workplace_part_id)
        self.assertEqual(created.workplace_name, "")
        self.assertEqual(created.workplace_part_name, "")

    def test_create_operation_and_workplace(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(created.workplace_id, self.workplace.id)
        self.assertIsNone(created.workplace_part_id)

    def test_create_full_hierarchy(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )
        self.assertEqual(created.workplace_part_id, self.part.id)

    def test_create_without_operation_fails(self) -> None:
        with self.assertRaises(HazardIdentificationError) as ctx:
            hazard_identification_service.create_identification(
                operation_id=None,
                workplace_id=self.workplace.id,
            )
        self.assertIn("Provoz", str(ctx.exception))

    def test_part_without_workplace_fails(self) -> None:
        with self.assertRaises(HazardIdentificationError) as ctx:
            hazard_identification_service.create_identification(
                operation_id=self.operation.id,
                workplace_id=None,
                workplace_part_id=self.part.id,
            )
        self.assertIn("Část pracoviště", str(ctx.exception))

    def test_workplace_without_matching_operation_fails(self) -> None:
        other_operation = settings_service.save_workplace(
            name="Jiný provoz RISK-IDENT-3",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        other_workplace = settings_service.save_workplace(
            name="Cizí pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=other_operation.id,
        )
        with self.assertRaises(HazardIdentificationError):
            hazard_identification_service.create_identification(
                operation_id=self.operation.id,
                workplace_id=other_workplace.id,
            )

    def test_basics_widget_workplace_optional_and_part_disabled(self) -> None:
        widget = HazardIdentificationBasicsWidget()
        labels = []
        form = widget.findChild(QFormLayout)
        assert form is not None
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label_item is None:
                continue
            label_widget = label_item.widget()
            if isinstance(label_widget, QLabel):
                labels.append(label_widget.text())
        self.assertIn("Provoz *:", labels)
        self.assertIn("Pracoviště:", labels)
        self.assertNotIn("Pracoviště *:", labels)

        # Bez provozu je pracoviště i část zakázaná.
        self.assertFalse(widget.workplace.isEnabled())
        self.assertFalse(widget.workplace_part.isEnabled())

        widget._select_combo_value(widget.operation, self.operation.id)
        widget._reload_workplaces(self.operation.id)
        self.assertTrue(widget.workplace.isEnabled())
        self.assertIsNone(widget.workplace.currentData())
        self.assertFalse(widget.workplace_part.isEnabled())
        self.assertIsNone(widget.workplace_part.currentData())

        widget._select_combo_value(widget.workplace, self.workplace.id)
        widget._reload_workplace_parts(self.workplace.id)
        self.assertTrue(widget.workplace_part.isEnabled())

    def test_dialog_saves_operation_only(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        dialog = HazardIdentificationDialog()
        dialog.basics_widget._select_combo_value(
            dialog.basics_widget.operation,
            self.operation.id,
        )
        dialog.basics_widget._reload_workplaces(self.operation.id)
        self.assertIsNone(dialog.basics_widget.workplace.currentData())
        self.assertFalse(dialog.basics_widget.workplace_part.isEnabled())

        with patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
                self.assertTrue(dialog._save_all())
        saved = dialog.identification
        assert saved is not None
        self.assertEqual(saved.operation_id, self.operation.id)
        self.assertIsNone(saved.workplace_id)
        self.assertIsNone(saved.workplace_part_id)
        dialog.reject()

    def test_working_copy_and_ai_export_tolerate_missing_workplace(self) -> None:
        from core.ai_oponentni.types import AiPeerReviewExportOptions
        from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
        from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
            hazard_inventory_item_service,
        )

        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
        )
        working = HazardIdentificationWorkingCopy.load(created.id)
        self.assertEqual(working.identification_id, created.id)

        hazard_inventory_item_service.create_item(
            hazard_identification_id=created.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zařízení IDENT-3",
        )
        content = hazard_identification_peer_review_provider.build_export_content(
            created.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("Provoz:", content.data_text)
        self.assertIn("Pracoviště: —", content.data_text)


if __name__ == "__main__":
    unittest.main()
