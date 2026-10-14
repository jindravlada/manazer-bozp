"""NEBEZPECI-ULOZENI-1 – potvrzení uložení identifikace nebezpečí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="nebezpeci-ulozeni-1-"))
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
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )

CONFIRMATION_TITLE = "Řízení rizik"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class NebezpeciUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.operation = settings_service.save_workplace(
            name="Provoz identifikace",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna identifikace",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.rizeni_rizik.ui.save_confirmation._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def _select_operation(self, dialog: HazardIdentificationDialog) -> None:
        dialog.basics_widget._select_combo_value(
            dialog.basics_widget.operation,
            self.operation.id,
        )

    def _close(self, dialog: HazardIdentificationDialog) -> None:
        dialog._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = HazardIdentificationDialog()
        dialog.show()
        self._select_operation(dialog)
        dialog.basics_widget.note.setPlainText("uložená poznámka")
        order: list[str] = []
        original = hazard_identification_service.create_identification

        def _create(**kwargs):
            order.append("write")
            return original(**kwargs)

        def _action() -> None:
            with patch.object(
                hazard_identification_service,
                "create_identification",
                side_effect=_create,
            ):
                dialog.save_button.click()

        shown = self._run(_action)
        self.assertEqual(order, ["write"])
        self._assert_confirmation(shown)
        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertFalse(dialog.isHidden())
        identification_id = dialog.identification.id
        self._close(dialog)

        reopened = HazardIdentificationDialog(
            identification=hazard_identification_service.get_by_id(identification_id)
        )
        reopened.show()
        self.assertEqual(reopened.basics_widget.note.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.basics_widget.operation.currentData(), self.operation.id)
        self.assertFalse(reopened.save_button.isEnabled())
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            note="Beze změny",
        )
        dialog = HazardIdentificationDialog(
            identification=hazard_identification_service.get_by_id(created.id)
        )
        dialog.show()
        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.save_button.isEnabled())
        shown = self._run(dialog.save_button.click)
        self.assertEqual(shown, [])
        direct = self._run(dialog._save_from_button)
        self.assertEqual(direct, [])
        stored = hazard_identification_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "Beze změny")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = HazardIdentificationDialog()
        dialog.show()
        dialog.basics_widget.note.setPlainText("rozepsaná poznámka")
        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("Provoz je povinný.", warn.call_args.args[2])
        self.assertEqual(dialog.basics_widget.note.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog.is_dirty())
        self.assertIsNone(dialog.identification)
        self._close(dialog)

    def test_indirect_saves_do_not_confirm(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            note="Původní",
        )
        dialog = HazardIdentificationDialog(
            identification=hazard_identification_service.get_by_id(created.id)
        )
        dialog.show()
        dialog.basics_widget.note.setPlainText("přímý zápis")
        shown = self._run(lambda: self.assertTrue(dialog._save_all()))
        self.assertEqual(shown, [])
        stored = hazard_identification_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "přímý zápis")

        dialog.basics_widget.note.setPlainText("jen záložka")
        shown = self._run(lambda: dialog.tabs.setCurrentIndex(dialog.photos_tab_index))
        self.assertEqual(shown, [])
        stored = hazard_identification_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "přímý zápis")
        self.assertEqual(dialog.basics_widget.note.toPlainText(), "jen záložka")

        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(dialog.close)
        self.assertEqual(shown, [])
        stored = hazard_identification_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "jen záložka")

        opened: list[int] = []
        dialog = HazardIdentificationDialog(
            identification=hazard_identification_service.get_by_id(created.id),
            on_open_library_template=opened.append,
        )
        dialog.show()
        dialog.basics_widget.note.setPlainText("před katalogem")
        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: dialog._handle_open_library_template(7))
        self.assertEqual(shown, [])
        self.assertEqual(opened, [7])
        stored = hazard_identification_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "před katalogem")
        self.assertEqual(stored.workplace_id, None)
