"""MU-EDITOR-SAVE-1 – lišta editoru Vyšetřování mimořádné události."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

_TMP = Path(tempfile.mkdtemp(prefix="mu-editor-save-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.vysetrovani_mu.constants import (
        MU_STATUS_DOKONCENO,
        MU_STATUS_FILTER_DOKONCENO,
        MU_STATUS_FILTER_PROBIHA,
    )
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import (
        mu_investigation_service,
    )
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import (
        MuInvestigationDialog,
        _SAVE_CONFIRMATION_TEXT,
        _SAVE_CLOSE_LABEL,
        _UNSAVED_ABORT_LABEL,
    )
    from moduly.vysetrovani_mu.ui.vysetrovani_mu_page import VysetrovaniMuPage
    from core.widgets.editor_dialog_controller import (
        EDITOR_CLOSE_LABEL,
        EDITOR_SAVE_LABEL,
        EDITOR_UNSAVED_DISCARD_LABEL,
        confirm_unsaved_editor_close,
    )

CONFIRMATION_TITLE = "Vyšetřování mimořádné události"
_PROMPT = "moduly.vysetrovani_mu.ui.mu_investigation_dialog.confirm_unsaved_editor_close"
_INFO = "moduly.vysetrovani_mu.ui.mu_investigation_dialog._exec_message_box"


class MuEditorSave1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _create(self, title: str = "Původní událost", **kwargs):
        return mu_investigation_service.create_investigation(
            title=title,
            started_at=kwargs.pop("started_at", date(2026, 11, 1)),
            short_description=kwargs.pop("short_description", "původní popis"),
            **kwargs,
        )

    def _open(self, investigation=None) -> MuInvestigationDialog:
        dialog = MuInvestigationDialog(investigation=investigation)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: MuInvestigationDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(_INFO, side_effect=_exec):
            action()
        return shown

    def _footer_buttons(self, dialog: MuInvestigationDialog) -> list[QPushButton]:
        layout = dialog.layout()
        footer = layout.itemAt(layout.count() - 1).layout()
        buttons: list[QPushButton] = []
        for index in range(footer.count()):
            widget = footer.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                buttons.append(widget)
        return buttons

    def test_footer_places_save_buttons_on_the_right(self) -> None:
        dialog = self._open()
        try:
            layout = dialog.layout()
            footer = layout.itemAt(layout.count() - 1).layout()
            labels = [button.text() for button in self._footer_buttons(dialog)]
            self.assertEqual(
                labels,
                [
                    "Kontrola spisu",
                    EDITOR_SAVE_LABEL,
                    _SAVE_CLOSE_LABEL,
                    EDITOR_CLOSE_LABEL,
                ],
            )
            stretch_at = next(
                index
                for index in range(footer.count())
                if footer.itemAt(index).spacerItem() is not None
            )
            self.assertLess(footer.indexOf(dialog.check_spis_btn), stretch_at)
            self.assertLess(stretch_at, footer.indexOf(dialog._save_btn))
            self.assertLess(footer.indexOf(dialog._save_btn), footer.indexOf(dialog._save_close_btn))
            self.assertLess(
                footer.indexOf(dialog._save_close_btn),
                footer.indexOf(dialog._close_btn),
            )
        finally:
            self._close(dialog)

    def test_clean_editor_is_not_dirty(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        try:
            self.assertFalse(dialog._is_dirty())
            self.assertFalse(dialog.was_saved)
        finally:
            self._close(dialog)

    def test_save_confirms_keeps_editor_and_data(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        try:
            dialog.title_edit.setText("Uložený název")
            dialog.short_description_edit.setPlainText("uložený popis")
            dialog.oznameni_widget.oznameni_kdo.setText("Novák")
            shown = self._run(dialog._save_btn.click)
            self.assertEqual(len(shown), 1)
            box = shown[0]
            self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
            self.assertEqual(box.text(), _SAVE_CONFIRMATION_TEXT)
            self.assertEqual(box.icon(), QMessageBox.Icon.Information)
            ok_button = box.button(QMessageBox.StandardButton.Ok)
            assert ok_button is not None
            self.assertEqual(ok_button.text(), "OK")
            self.assertFalse(dialog._is_dirty())
            self.assertFalse(dialog._closing)
            self.assertTrue(dialog.isVisible())
            self.assertTrue(dialog.was_saved)
        finally:
            self._close(dialog)

        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Uložený název")
        self.assertEqual(stored.short_description, "uložený popis")
        self.assertEqual(stored.oznameni_kdo, "Novák")

        reopened = self._open(stored)
        try:
            self.assertEqual(reopened.title_edit.text(), "Uložený název")
            self.assertEqual(reopened.short_description_edit.toPlainText(), "uložený popis")
            self.assertEqual(reopened.oznameni_widget.oznameni_kdo.text(), "Novák")
            self.assertFalse(reopened._is_dirty())
        finally:
            self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        investigation = self._create(title="Beze změny")
        dialog = self._open(investigation)
        try:
            shown = self._run(dialog._save_btn.click)
            self.assertEqual(shown, [])
            self.assertFalse(dialog._closing)
            self.assertTrue(dialog.isVisible())
            again = self._run(dialog._save_keep_open)
            self.assertEqual(again, [])
        finally:
            self._close(dialog)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Beze změny")

    def test_new_save_confirms_once_and_does_not_duplicate(self) -> None:
        dialog = self._open()
        try:
            dialog.title_edit.setText("Nové vyšetřování")
            first = self._run(dialog._save_btn.click)
            self.assertEqual(len(first), 1)
            self.assertFalse(dialog._closing)
            self.assertTrue(dialog.isVisible())
            self.assertTrue(dialog.number_header.text().startswith("Číslo: MU-"))
            investigation_id = dialog.investigation.id
            second = self._run(dialog._save_btn.click)
            self.assertEqual(second, [])
            self.assertEqual(dialog.investigation.id, investigation_id)
        finally:
            self._close(dialog)

        matches = [
            item
            for item in mu_investigation_service.get_all()
            if item.title == "Nové vyšetřování"
        ]
        self.assertEqual(len(matches), 1)

    def test_failed_save_keeps_editor_and_draft(self) -> None:
        investigation = self._create(title="Platný záznam")
        dialog = self._open(investigation)
        try:
            dialog.title_edit.setText("Rozepsaný název")
            dialog.short_description_edit.setPlainText("rozepsaný popis")
            with (
                patch.object(
                    mu_investigation_service,
                    "update_investigation",
                    side_effect=RuntimeError("db"),
                ),
                patch(
                    "moduly.vysetrovani_mu.ui.mu_investigation_dialog.QMessageBox.warning"
                ) as warning,
            ):
                shown = self._run(dialog._save_btn.click)
                self.assertEqual(shown, [])
                warning.assert_called_once()
                self.assertIn("nepodařilo uložit", warning.call_args.args[2])
                self.assertFalse(dialog._closing)
                self.assertTrue(dialog.isVisible())
                self.assertTrue(dialog._is_dirty())
                self.assertEqual(dialog.title_edit.text(), "Rozepsaný název")

                dialog._save_and_close()
                self.assertFalse(dialog._closing)
                self.assertTrue(dialog.isVisible())
        finally:
            self._close(dialog)

        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Platný záznam")
        self.assertEqual(stored.short_description, "původní popis")

    def test_save_and_close_persists_without_confirmation(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        dialog.title_edit.setText("Zavřeno uložením")
        dialog.status_combo.setCurrentText(MU_STATUS_DOKONCENO)
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Zavřeno uložením")
        self.assertEqual(stored.status, MU_STATUS_DOKONCENO)
        dialog.deleteLater()

    def test_close_without_changes_skips_prompt(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        with patch(_PROMPT) as prompt:
            shown = self._run(dialog._close_btn.click)
        self.assertEqual(shown, [])
        prompt.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog.was_saved)
        dialog.deleteLater()

    def test_discard_does_not_save_draft(self) -> None:
        investigation = self._create(title="Ponechat")
        dialog = self._open(investigation)
        try:
            dialog.title_edit.setText("První zápis")
            self._run(dialog._save_btn.click)
            dialog.title_edit.setText("Rozpracované")
            dialog.short_description_edit.setPlainText("nemá se zapsat")
            with (
                patch(_PROMPT, return_value="discard") as prompt,
                patch.object(
                    mu_investigation_service,
                    "update_investigation",
                    wraps=mu_investigation_service.update_investigation,
                ) as update,
            ):
                dialog._close_btn.click()
            prompt.assert_called_once()
            self.assertEqual(prompt.call_args.kwargs.get("abort_label"), _UNSAVED_ABORT_LABEL)
            update.assert_not_called()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        finally:
            if dialog.isVisible():
                self._close(dialog)

        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "První zápis")
        self.assertEqual(stored.short_description, "původní popis")

    def test_back_keeps_editor_open(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        try:
            dialog.title_edit.setText("Ještě ne")
            with patch(_PROMPT, return_value="cancel"):
                dialog._close_btn.click()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._closing)
            self.assertEqual(dialog.title_edit.text(), "Ještě ne")
            self.assertTrue(dialog._is_dirty())
        finally:
            self._close(dialog)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Původní událost")

    def test_prompt_save_uses_shared_persist_and_skips_confirmation(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        dialog.title_edit.setText("Z dotazu")
        with (
            patch(_PROMPT, return_value="save"),
            patch.object(dialog, "_persist", wraps=dialog._persist) as persist,
        ):
            shown = self._run(dialog._close_btn.click)
        self.assertEqual(shown, [])
        persist.assert_called_once()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Z dotazu")
        dialog.deleteLater()

    def test_all_save_buttons_share_persist(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        try:
            with patch.object(dialog, "_persist", return_value=True) as persist:
                dialog.title_edit.setText("Tlačítko uložit")
                self._run(dialog._save_btn.click)
                dialog.title_edit.setText("Tlačítko zavřít")
                dialog._save_close_btn.click()
            self.assertEqual(persist.call_count, 2)
        finally:
            if dialog.isVisible():
                self._close(dialog)

    def test_unsaved_prompt_offers_save_discard_and_back(self) -> None:
        with patch(
            "core.widgets.editor_dialog_controller.QMessageBox"
        ) as mock_box_cls:
            instance = mock_box_cls.return_value
            buttons = [MagicMock(), MagicMock(), MagicMock()]
            instance.addButton.side_effect = buttons
            instance.clickedButton.return_value = buttons[2]
            decision = confirm_unsaved_editor_close(
                None,
                title=CONFIRMATION_TITLE,
                abort_label=_UNSAVED_ABORT_LABEL,
            )
        self.assertEqual(decision, "cancel")
        labels = [call.args[0] for call in instance.addButton.call_args_list]
        self.assertEqual(
            labels,
            [EDITOR_SAVE_LABEL, EDITOR_UNSAVED_DISCARD_LABEL, _UNSAVED_ABORT_LABEL],
        )
        buttons[2].setText.assert_any_call(_UNSAVED_ABORT_LABEL)

    def test_system_close_without_changes(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        event = QCloseEvent()
        with patch(_PROMPT) as prompt:
            dialog.closeEvent(event)
        prompt.assert_not_called()
        self.assertTrue(event.isAccepted())
        self.assertFalse(dialog.was_saved)
        dialog.deleteLater()

    def test_system_close_discard_does_not_save(self) -> None:
        investigation = self._create(title="Systémový křížek")
        dialog = self._open(investigation)
        dialog.title_edit.setText("Nemá se uložit")
        event = QCloseEvent()
        with patch(_PROMPT, return_value="discard"):
            dialog.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Systémový křížek")
        dialog.deleteLater()

    def test_system_close_back_ignores_event(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        try:
            dialog.title_edit.setText("Zpět z křížku")
            event = QCloseEvent()
            with patch(_PROMPT, return_value="cancel"):
                dialog.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.title_edit.text(), "Zpět z křížku")
        finally:
            self._close(dialog)

    def test_system_close_save_persists_and_accepts(self) -> None:
        investigation = self._create()
        dialog = self._open(investigation)
        dialog.short_description_edit.setPlainText("uloženo křížkem")
        event = QCloseEvent()
        with patch(_PROMPT, return_value="save"):
            shown = self._run(lambda: dialog.closeEvent(event))
        self.assertEqual(shown, [])
        self.assertTrue(event.isAccepted())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.short_description, "uloženo křížkem")
        dialog.deleteLater()

    def test_new_discard_does_not_create_record(self) -> None:
        before = {item.id for item in mu_investigation_service.get_all()}
        dialog = self._open()
        dialog.title_edit.setText("Nezakládat")
        with patch(_PROMPT, return_value="discard"):
            dialog._close_btn.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        after = {item.id for item in mu_investigation_service.get_all()}
        self.assertEqual(before, after)
        dialog.deleteLater()

    def test_page_saves_once_and_discard_leaves_list(self) -> None:
        investigation = self._create(title="Seznam")
        page = VysetrovaniMuPage()
        page.status_filter.setCurrentText(MU_STATUS_FILTER_PROBIHA)

        def save_and_close(dialog: MuInvestigationDialog) -> int:
            dialog.title_edit.setText("Ze stránky")
            dialog._save_and_close()
            return int(dialog.result())

        with (
            patch(
                "moduly.vysetrovani_mu.ui.vysetrovani_mu_page.exec_maximized",
                side_effect=save_and_close,
            ),
            patch.object(
                mu_investigation_service,
                "update_investigation",
                wraps=mu_investigation_service.update_investigation,
            ) as update,
        ):
            page.open_investigation(investigation.id)
        self.assertEqual(update.call_count, 1)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Ze stránky")

        def discard(dialog: MuInvestigationDialog) -> int:
            dialog.title_edit.setText("Ze stránky neukládat")
            with patch(_PROMPT, return_value="discard"):
                dialog._close_btn.click()
            return int(dialog.result())

        with patch(
            "moduly.vysetrovani_mu.ui.vysetrovani_mu_page.exec_maximized",
            side_effect=discard,
        ):
            page.open_investigation(investigation.id)
        stored = mu_investigation_service.get_by_id(investigation.id)
        assert stored is not None
        self.assertEqual(stored.title, "Ze stránky")

        def complete(dialog: MuInvestigationDialog) -> int:
            dialog.status_combo.setCurrentText(MU_STATUS_DOKONCENO)
            dialog._save_and_close()
            return int(dialog.result())

        with patch(
            "moduly.vysetrovani_mu.ui.vysetrovani_mu_page.exec_maximized",
            side_effect=complete,
        ):
            page.open_investigation(investigation.id)
        self.assertEqual(page.status_filter.currentText(), MU_STATUS_FILTER_DOKONCENO)

        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
