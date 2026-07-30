"""UX-INSPECTIONS-1: modalita dialogu doporučeného postupu kontroly."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QWidget,
)

from moduly.proverky.constants import KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE
from moduly.proverky.ui.proverky_control_procedure_dialog import (
    ParentDimOverlay,
    ProverkyControlProcedureDialog,
    _OVERLAY_ALPHA,
    _OVERLAY_OBJECT_NAME,
    clear_dim_overlays,
    find_dim_overlays,
)


class UxInspections1ControlProcedureModalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.host = QWidget()
        self.host.setObjectName("InspectionEditorHost")
        self.host.resize(900, 700)
        self.background_btn = QPushButton("Podklad", self.host)
        self.background_btn.move(20, 20)
        self.background_clicked = 0
        self.background_btn.clicked.connect(self._on_background_clicked)
        self.host.show()
        QApplication.processEvents()

    def tearDown(self) -> None:
        clear_dim_overlays(self.host)
        self.host.close()
        self.host.deleteLater()
        QApplication.processEvents()

    def _on_background_clicked(self) -> None:
        self.background_clicked += 1

    @staticmethod
    def _section() -> dict:
        return {
            "nazev": "Oblast skladování",
            "postup_kontroly_uvod": "Úvodní text postupu.",
            "postup_kontroly": [
                {"text": "Zkontrolujte přístupové cesty", "aktivni": True, "poradi": 1},
                {"text": "Ověřte značení", "aktivni": True, "poradi": 2},
            ],
        }

    def _make_dialog(self) -> ProverkyControlProcedureDialog:
        return ProverkyControlProcedureDialog(
            self._section(),
            section_label="Oblast skladování",
            parent=self.host,
        )

    def test_open_creates_single_overlay_with_gray_alpha(self) -> None:
        dialog = self._make_dialog()
        dialog._ensure_overlay()
        QApplication.processEvents()

        overlays = find_dim_overlays(self.host)
        self.assertEqual(len(overlays), 1)
        self.assertTrue(overlays[0].isVisible())
        self.assertEqual(overlays[0].objectName(), _OVERLAY_OBJECT_NAME)
        self.assertEqual(overlays[0].geometry(), self.host.rect())
        self.assertEqual(dialog.windowModality(), Qt.WindowModality.WindowModal)
        self.assertTrue(dialog.isModal())
        self.assertIsInstance(dialog.active_overlay(), ParentDimOverlay)

        alpha = QColor(0, 0, 0, _OVERLAY_ALPHA).alpha()
        self.assertGreaterEqual(alpha, int(255 * 0.35))
        self.assertLessEqual(alpha, int(255 * 0.50))

        dialog._cleanup_overlay()
        dialog.deleteLater()

    def test_background_does_not_receive_clicks_while_open(self) -> None:
        dialog = self._make_dialog()
        dialog._ensure_overlay()
        QApplication.processEvents()
        overlay = dialog.active_overlay()
        assert overlay is not None
        overlay.raise_()
        QApplication.processEvents()

        center = self.background_btn.geometry().center()
        top = self.host.childAt(center)
        self.assertIsNotNone(top)
        self.assertTrue(
            top is overlay or overlay.isAncestorOf(top),
            "Overlay musí překrývat podkladové ovládací prvky.",
        )

        before = self.background_clicked
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=center)
        self.assertEqual(self.background_clicked, before)

        dialog._cleanup_overlay()
        dialog.deleteLater()

    def test_close_button_removes_overlay(self) -> None:
        dialog = self._make_dialog()
        dialog.show()
        dialog._ensure_overlay()
        QApplication.processEvents()
        self.assertEqual(len(find_dim_overlays(self.host)), 1)

        close_btn = dialog.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Close,
        )
        assert close_btn is not None
        QTest.mouseClick(close_btn, Qt.MouseButton.LeftButton)
        QApplication.processEvents()

        self.assertEqual(find_dim_overlays(self.host), [])
        self.assertTrue(self.background_btn.isEnabled())
        dialog.deleteLater()

    def test_escape_removes_overlay(self) -> None:
        dialog = self._make_dialog()
        dialog.show()
        dialog._ensure_overlay()
        QApplication.processEvents()
        self.assertEqual(len(find_dim_overlays(self.host)), 1)

        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QApplication.processEvents()

        self.assertEqual(find_dim_overlays(self.host), [])
        dialog.deleteLater()

    def test_title_close_removes_overlay(self) -> None:
        dialog = self._make_dialog()
        dialog.show()
        dialog._ensure_overlay()
        QApplication.processEvents()
        self.assertEqual(len(find_dim_overlays(self.host)), 1)

        dialog.close()
        QApplication.processEvents()

        self.assertEqual(find_dim_overlays(self.host), [])
        dialog.deleteLater()

    def test_repeated_open_does_not_stack_overlays(self) -> None:
        for _ in range(3):
            dialog = self._make_dialog()
            with patch.object(
                QDialog,
                "exec",
                return_value=int(QDialog.DialogCode.Rejected),
            ):
                dialog.exec()
            QApplication.processEvents()
            self.assertEqual(find_dim_overlays(self.host), [])
            dialog.deleteLater()
            QApplication.processEvents()

        # Během otevření vždy jen jeden overlay
        dialog = self._make_dialog()
        dialog._ensure_overlay()
        dialog._ensure_overlay()
        self.assertEqual(len(find_dim_overlays(self.host)), 1)
        dialog._cleanup_overlay()
        dialog.deleteLater()

    def test_exec_creates_and_removes_overlay(self) -> None:
        dialog = self._make_dialog()
        during: list[int] = []

        def fake_super_exec() -> int:
            during.append(len(find_dim_overlays(self.host)))
            return int(QDialog.DialogCode.Rejected)

        with patch.object(QDialog, "exec", side_effect=fake_super_exec):
            result = dialog.exec()

        self.assertEqual(result, int(QDialog.DialogCode.Rejected))
        self.assertEqual(during, [1])
        self.assertEqual(find_dim_overlays(self.host), [])
        dialog.deleteLater()

    def test_editor_active_again_after_close(self) -> None:
        dialog = self._make_dialog()
        with patch.object(
            QDialog,
            "exec",
            return_value=int(QDialog.DialogCode.Rejected),
        ):
            dialog.exec()
        QApplication.processEvents()

        self.assertEqual(find_dim_overlays(self.host), [])
        before = self.background_clicked
        QTest.mouseClick(self.background_btn, Qt.MouseButton.LeftButton)
        self.assertEqual(self.background_clicked, before + 1)
        dialog.deleteLater()

    def test_procedure_content_unchanged(self) -> None:
        dialog = self._make_dialog()
        self.assertEqual(dialog.windowTitle(), KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE)
        labels = [
            label.text()
            for label in dialog.findChildren(QLabel)
            if label.text().strip()
        ]
        self.assertIn("Oblast skladování", labels)
        self.assertIn("Úvodní text postupu.", labels)
        self.assertIn("1. Zkontrolujte přístupové cesty", labels)
        self.assertIn("2. Ověřte značení", labels)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
