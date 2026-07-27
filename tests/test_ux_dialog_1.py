"""UX-DIALOG-1 – sjednocení vzhledu dialogových oken (QMessageBox)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from core.dialogs.message_box import (
    MESSAGE_BOX_MIN_WIDTH,
    configure_application_for_dialogs,
    install_unified_message_boxes,
    polish_message_box,
    preferred_message_box_width,
    show_information,
    show_question,
    strip_application_title_suffix,
    uninstall_unified_message_boxes,
)
from core.version import APP_NAME, app_display_name


class UxDialog1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        configure_application_for_dialogs(cls._app)
        install_unified_message_boxes(cls._app)

    @classmethod
    def tearDownClass(cls) -> None:
        uninstall_unified_message_boxes()

    def test_strip_application_title_suffix(self) -> None:
        self.assertEqual(
            strip_application_title_suffix("Nelze uložit pracovní úraz — Manažer BOZP"),
            "Nelze uložit pracovní úraz",
        )
        self.assertEqual(
            strip_application_title_suffix(
                f"Identifikace nebezpečí — {app_display_name()}"
            ),
            "Identifikace nebezpečí",
        )
        self.assertEqual(
            strip_application_title_suffix("ARES"),
            "ARES",
        )

    def test_application_display_name_cleared(self) -> None:
        self.assertEqual(self._app.applicationDisplayName(), "")
        self.assertEqual(self._app.applicationName(), "manazer-bozp")
        self.assertNotEqual(self._app.applicationName(), APP_NAME)

    def test_polish_sets_czech_buttons_and_min_width(self) -> None:
        box = QMessageBox()
        box.setWindowTitle("Nelze uložit pracovní úraz — Manažer BOZP")
        box.setText("Datum pracovního úrazu nemůže být v budoucnosti.")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        polish_message_box(box)

        self.assertEqual(box.windowTitle(), "Nelze uložit pracovní úraz")
        ok_btn = box.button(QMessageBox.StandardButton.Ok)
        self.assertIsNotNone(ok_btn)
        assert ok_btn is not None
        self.assertEqual(ok_btn.text(), "OK")
        self.assertGreaterEqual(box.minimumWidth(), MESSAGE_BOX_MIN_WIDTH)
        self.assertGreaterEqual(
            preferred_message_box_width(box),
            MESSAGE_BOX_MIN_WIDTH,
        )

    def test_question_buttons_ano_ne(self) -> None:
        box = QMessageBox()
        box.setWindowTitle("Potvrzení")
        box.setText("Opravdu smazat záznam?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        polish_message_box(box)
        yes_btn = box.button(QMessageBox.StandardButton.Yes)
        no_btn = box.button(QMessageBox.StandardButton.No)
        self.assertEqual(yes_btn.text(), "Ano")
        self.assertEqual(no_btn.text(), "Ne")

    def test_cancel_button_is_storno(self) -> None:
        box = QMessageBox()
        box.setWindowTitle("Dotaz")
        box.setText("Pokračovat?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        polish_message_box(box)
        cancel_btn = box.button(QMessageBox.StandardButton.Cancel)
        self.assertEqual(cancel_btn.text(), "Storno")

    def test_custom_unsaved_buttons_are_preserved(self) -> None:
        box = QMessageBox()
        box.setWindowTitle("Neuložené změny")
        box.setText("Uložit změny?")
        save_btn = box.addButton("Uložit", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("Neukládat", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Zrušit", QMessageBox.ButtonRole.RejectRole)
        polish_message_box(box)
        self.assertEqual(save_btn.text(), "Uložit")
        self.assertEqual(discard_btn.text(), "Neukládat")
        self.assertEqual(cancel_btn.text(), "Zrušit")

    def test_short_message_keeps_width_for_title(self) -> None:
        """Regrese: „Zdroj rizika“ se nesmí useknout na „Zdr“ u krátkého textu."""
        box = QMessageBox()
        box.setWindowTitle("Zdroj rizika")
        box.setText("Změny byly uloženy.")
        box.setIcon(QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        polish_message_box(box)

        self.assertEqual(box.windowTitle(), "Zdroj rizika")
        self.assertGreaterEqual(box.minimumWidth(), MESSAGE_BOX_MIN_WIDTH)
        self.assertGreaterEqual(box.width(), MESSAGE_BOX_MIN_WIDTH)
        # sizeHint Qt u krátkého textu je ~200 px – nesmí vyhrát.
        self.assertGreater(box.width(), box.sizeHint().width())
        title_width = box.fontMetrics().horizontalAdvance(box.windowTitle())
        self.assertLess(
            title_width + 80,
            box.minimumWidth(),
            msg="Titulek musí mít v dialogu rezervu na ovládací prvky okna",
        )

    def test_long_text_widens_dialog(self) -> None:
        short = QMessageBox()
        short.setWindowTitle("Info")
        short.setText("OK.")
        short_width = preferred_message_box_width(short)

        long = QMessageBox()
        long.setWindowTitle("Info")
        long.setText(
            "Toto je delší informační věta, která by se v úzkém dialogu "
            "zbytečně lomila na mnoho krátkých řádků."
        )
        long_width = preferred_message_box_width(long)
        self.assertGreater(long_width, short_width)

    def test_installed_static_api_matches_helpers(self) -> None:
        self.assertEqual(getattr(QMessageBox.information, "__name__", ""), "show_information")
        self.assertEqual(getattr(QMessageBox.warning, "__name__", ""), "show_warning")
        self.assertEqual(getattr(QMessageBox.critical, "__name__", ""), "show_critical")
        self.assertEqual(getattr(QMessageBox.question, "__name__", ""), "show_question")

    def test_title_fits_without_app_suffix_in_window_title(self) -> None:
        box = QMessageBox()
        box.setWindowTitle(f"Identifikace nebezpečí — {APP_NAME}")
        box.setText("Základní údaje byly uloženy.")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        polish_message_box(box)
        self.assertNotIn(APP_NAME, box.windowTitle())
        self.assertNotIn("—", box.windowTitle())
        # Titulek musí vejít do minimální šířky dialogu.
        metrics = box.fontMetrics()
        self.assertLessEqual(
            metrics.horizontalAdvance(box.windowTitle()) + 140,
            max(box.minimumWidth(), preferred_message_box_width(box)),
        )

    def test_question_helper_returns_standard_button(self) -> None:
        with patch.object(QMessageBox, "exec", return_value=int(QMessageBox.StandardButton.No)):
            result = show_question(None, "Dotaz", "Pokračovat?")
        self.assertEqual(result, QMessageBox.StandardButton.No)


if __name__ == "__main__":
    unittest.main()
