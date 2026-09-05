"""UX-RISK-5 – Uložit a Uložit a zavřít v editoru zdroje rizika."""

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

    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_SAVE_AND_CLOSE,
        HAZARD_LIBRARY_SCOPE_MANUAL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )


class UxRisk5HazardSourceEditorSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.template = hazard_library_template_service.create_template(
            name=f"UX-RISK-5 existující {id(self)}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

    def _footer_buttons(self, dialog: HazardLibraryTemplateDialog):
        footer = dialog.layout().itemAt(dialog.layout().count() - 1).layout()
        return [
            footer.itemAt(index).widget()
            for index in range(footer.count())
            if footer.itemAt(index).widget() is not None
        ]

    def test_footer_order_cancel_save_save_and_close(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        self.assertEqual(dialog.cancel_button.text(), "Zrušit")
        self.assertEqual(dialog.save_button.text(), "Uložit")
        self.assertEqual(dialog.save_close_button.text(), HAZARD_LIBRARY_SAVE_AND_CLOSE)
        self.assertEqual(
            self._footer_buttons(dialog),
            [dialog.cancel_button, dialog.save_button, dialog.save_close_button],
        )

        existing = HazardLibraryTemplateDialog(template=self.template)
        self.assertEqual(existing.cancel_button.text(), "Zavřít")
        self.assertEqual(
            self._footer_buttons(existing),
            [existing.cancel_button, existing.save_button, existing.save_close_button],
        )

    def test_save_persists_and_keeps_editor_open(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        dialog.name.setText("Nový zdroj UX-RISK-5 uložit")
        self.assertTrue(dialog.save_button.isEnabled())

        dialog.save_button.click()

        self.assertIsNotNone(dialog.template)
        self.assertIsNotNone(dialog.template.id)
        self.assertFalse(dialog._closing)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.is_dirty())
        self.assertEqual(dialog.cancel_button.text(), "Zavřít")
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertFalse(dialog.save_close_button.isEnabled())

        reloaded = hazard_library_template_service.get_by_id(dialog.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Nový zdroj UX-RISK-5 uložit")

    def test_save_does_not_show_blocking_information_dialog(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        dialog.name.setText("Nový zdroj UX-RISK-5 bez dialogu")

        with patch.object(QMessageBox, "information") as info:
            self.assertTrue(dialog._save_all())
            info.assert_not_called()

    def test_save_and_close_persists_and_closes_new_source(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        dialog.name.setText("Nový zdroj UX-RISK-5 zavřít")

        with patch.object(dialog, "_save_all", wraps=dialog._save_all) as save:
            dialog._save_and_close()
            save.assert_called_once()

        self.assertTrue(dialog._closing)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        assert dialog.saved_template is not None
        reloaded = hazard_library_template_service.get_by_id(dialog.saved_template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Nový zdroj UX-RISK-5 zavřít")

    def test_save_and_close_validation_error_keeps_editor_open(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        dialog.name.setText("")

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
            dialog.save_close_button.click()

        self.assertFalse(dialog._closing)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNone(dialog.template)
        remaining = hazard_library_template_service.repository.get_all(include_inactive=True)
        self.assertEqual([item.id for item in remaining], [self.template.id])

    def test_save_and_close_existing_source_persists_and_closes(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog.name.setText("Přejmenovaný UX-RISK-5")

        dialog.save_close_button.click()

        self.assertTrue(dialog._closing)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Přejmenovaný UX-RISK-5")

    def test_save_and_close_does_not_prompt_unsaved_changes(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog.name.setText("Bez dalšího dotazu UX-RISK-5")

        with (
            patch.object(dialog, "_prompt_unsaved_close") as prompt,
            patch.object(QMessageBox, "question") as question,
            patch.object(QMessageBox, "information") as info,
        ):
            dialog._save_and_close()
            prompt.assert_not_called()
            question.assert_not_called()
            info.assert_not_called()

        self.assertTrue(dialog._closing)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.is_dirty())


if __name__ == "__main__":
    unittest.main()
