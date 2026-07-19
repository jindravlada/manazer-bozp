"""PBP-1: založení výstupu Pravidla bezpečné práce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialogButtonBox

_TMP = Path(tempfile.mkdtemp(prefix="pbp-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidlaBezpecnePraceService,
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import HazardIdentificationsTab


class PravidlaBezpecnePraceServiceTestCase(unittest.TestCase):
    def test_generate_returns_empty_list(self) -> None:
        result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=1,
            operation_id=2,
            workplace_id=3,
            workplace_part_id=4,
        )
        self.assertEqual(result, [])
        self.assertIsInstance(pravidla_bezpecne_prace_service, PravidlaBezpecnePraceService)


class PravidlaBezpecnePraceDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for group in list(exposed_group_service.get_all(include_inactive=True)):
            if group.active:
                exposed_group_service.deactivate(group.id)
        for workplace in list(settings_service.get_workplaces(include_inactive=True)):
            settings_service.deactivate_workplace(workplace.id)

        self.group = exposed_group_service.create_group(name="PBP skupina")
        self.operation = settings_service.save_workplace(
            name="PBP provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="PBP část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def test_toolbar_has_pravidla_button(self) -> None:
        tab = HazardIdentificationsTab()
        self.assertEqual(tab.pravidla_btn.text(), "Pravidla bezpečné práce")

    def test_dialog_has_generate_and_close_buttons(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert save is not None
        assert cancel is not None
        self.assertEqual(save.text(), "Generovat")
        self.assertEqual(cancel.text(), "Zavřít")

    def test_dialog_requires_group_and_operation(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        with patch(
            "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.QMessageBox.warning"
        ) as warn:
            dialog._generate()
        warn.assert_called()
        self.assertIsNone(dialog.last_result)

    def test_generate_calls_service_with_hierarchy(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.endangered_group.set_group_id(self.group.id)
        index = dialog.operation.findData(self.operation.id)
        self.assertGreaterEqual(index, 0)
        dialog.operation.setCurrentIndex(index)
        workplace_index = dialog.workplace.findData(self.workplace.id)
        self.assertGreaterEqual(workplace_index, 0)
        dialog.workplace.setCurrentIndex(workplace_index)
        part_index = dialog.workplace_part.findData(self.part.id)
        self.assertGreaterEqual(part_index, 0)
        dialog.workplace_part.setCurrentIndex(part_index)

        with (
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.generate",
                return_value=[],
            ) as mock_generate_dialog,
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.QMessageBox.information"
            ),
        ):
            dialog._generate()
            mock_generate_dialog.assert_called_once_with(
                endangered_group_id=self.group.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
                workplace_part_id=self.part.id,
            )
        self.assertEqual(dialog.last_result, [])

    def test_workplace_cascade_clears_parts_when_operation_changes(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        op_index = dialog.operation.findData(self.operation.id)
        dialog.operation.setCurrentIndex(op_index)
        self.assertTrue(dialog.workplace.isEnabled())
        self.assertGreaterEqual(dialog.workplace.findData(self.workplace.id), 0)

        dialog.workplace.setCurrentIndex(dialog.workplace.findData(self.workplace.id))
        self.assertTrue(dialog.workplace_part.isEnabled())
        self.assertGreaterEqual(dialog.workplace_part.findData(self.part.id), 0)

        dialog.operation.setCurrentIndex(-1)
        self.assertFalse(dialog.workplace.isEnabled())
        self.assertFalse(dialog.workplace_part.isEnabled())


if __name__ == "__main__":
    unittest.main()
