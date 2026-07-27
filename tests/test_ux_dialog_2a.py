"""UX-DIALOG-2a – bezpečné odpojování signálů editoru."""

from __future__ import annotations

import os
import warnings
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.editor_dialog_controller import (
    EditorDialogController,
    create_editor_button_box,
)


def _disconnect_warnings(recorded: list) -> list[str]:
    messages = []
    for item in recorded:
        text = str(item.message)
        if "Failed to disconnect" in text:
            messages.append(text)
    return messages


class _ModalEditor(QDialog):
    """Modalní editor bez on_save – Uložit = accept()."""

    def __init__(self, *, is_new: bool = True):
        super().__init__()
        self.setWindowTitle("Modal editor")
        layout = QVBoxLayout(self)
        self.edit = QLineEdit()
        layout.addWidget(self.edit)
        self.buttons = create_editor_button_box(self, is_new=is_new)
        layout.addWidget(self.buttons)
        self.controller = EditorDialogController(
            self,
            self.buttons,
            is_new=is_new,
            title="Modal editor",
        )
        self.controller.set_snapshot_provider(lambda: self.edit.text())
        if not is_new:
            self.edit.setText("původní")
            self.controller.capture_baseline()
        self.controller.install_auto_dirty_tracking(self.edit)


class _StayOpenEditor(QDialog):
    def __init__(self, *, is_new: bool = True):
        super().__init__()
        self.setWindowTitle("Stay-open editor")
        self._saved = False
        self._value = ""
        layout = QVBoxLayout(self)
        self.edit = QLineEdit()
        layout.addWidget(self.edit)
        self.buttons = create_editor_button_box(self, is_new=is_new)
        layout.addWidget(self.buttons)
        self.controller = EditorDialogController(
            self,
            self.buttons,
            is_new=is_new,
            title="Stay-open editor",
            on_save=self._save,
            is_dirty=lambda: self.edit.text() != self._value,
        )
        if not is_new:
            self._value = "původní"
            self.edit.setText("původní")
            self.controller.capture_baseline()
        self.controller.install_auto_dirty_tracking(self.edit)

    def _save(self) -> bool:
        self._value = self.edit.text()
        self._saved = True
        return True


class UxDialog2aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_cleanup_disconnects_tracked_slots(self) -> None:
        dialog = _StayOpenEditor(is_new=True)
        controller = dialog.controller
        self.assertGreaterEqual(len(controller._connections), 2)

        calls = {"save": 0, "close": 0}
        original_save = controller._handle_save_clicked
        original_close = controller._handle_close_clicked

        def save_probe() -> None:
            calls["save"] += 1
            original_save()

        def close_probe() -> None:
            calls["close"] += 1
            original_close()

        # Nahraď evidované sloty sondami se stejným signálem.
        controller.cleanup()
        controller._cleaned = False
        controller._connect(controller.save_button.clicked, save_probe)
        controller._connect(controller.close_button.clicked, close_probe)

        controller.save_button.click()
        controller.close_button.click()
        self.assertEqual(calls["save"], 1)
        self.assertEqual(calls["close"], 1)

        controller.cleanup()
        controller.save_button.click()
        controller.close_button.click()
        self.assertEqual(calls["save"], 1)
        self.assertEqual(calls["close"], 1)
        self.assertEqual(controller._connections, [])

    def test_double_cleanup_is_safe(self) -> None:
        dialog = _StayOpenEditor(is_new=True)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            dialog.controller.cleanup()
            dialog.controller.cleanup()
            dialog.controller.cleanup()
        self.assertEqual(_disconnect_warnings(recorded), [])

    def test_cleanup_keeps_foreign_slots(self) -> None:
        dialog = _StayOpenEditor(is_new=True)
        foreign_calls = {"n": 0}

        def foreign_slot(*_args) -> None:
            foreign_calls["n"] += 1

        dialog.controller.save_button.clicked.connect(foreign_slot)
        dialog.controller.cleanup()
        dialog.controller.save_button.click()
        self.assertEqual(foreign_calls["n"], 1)

    def test_close_via_accepted_path(self) -> None:
        dialog = _ModalEditor(is_new=True)
        dialog.edit.setText("nový")
        dialog.controller.mark_dirty()
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            dialog.controller.save_button.click()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertTrue(dialog.controller._cleaned)
        self.assertEqual(_disconnect_warnings(recorded), [])

    def test_close_via_rejected_path(self) -> None:
        dialog = _ModalEditor(is_new=False)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            dialog.controller.close_button.click()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
            self.assertTrue(dialog.controller._cleaned)
        self.assertEqual(_disconnect_warnings(recorded), [])

    def test_escape_close_without_disconnect_warnings(self) -> None:
        dialog = _ModalEditor(is_new=False)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            dialog.reject()
        self.assertEqual(_disconnect_warnings(recorded), [])
        self.assertTrue(dialog.controller._cleaned)

    def test_reopen_does_not_multiply_connections(self) -> None:
        first = _StayOpenEditor(is_new=True)
        first_count = len(first.controller._connections)
        first.controller.cleanup()
        first.close()

        second = _StayOpenEditor(is_new=True)
        self.assertEqual(len(second.controller._connections), first_count)

        # Dvojí install_auto_dirty_tracking by dříve násobilo spojení –
        # ověříme, že jedno vytvoření dialogu drží stabilní počet.
        third = _StayOpenEditor(is_new=False)
        self.assertEqual(len(third.controller._connections), first_count)

    def test_init_does_not_bare_disconnect_accepted_rejected(self) -> None:
        foreign_accepted = {"n": 0}
        foreign_rejected = {"n": 0}

        dialog = QDialog()
        layout = QVBoxLayout(dialog)
        buttons = create_editor_button_box(dialog, is_new=True)
        layout.addWidget(buttons)

        def on_accepted() -> None:
            foreign_accepted["n"] += 1

        def on_rejected() -> None:
            foreign_rejected["n"] += 1

        buttons.accepted.connect(on_accepted)
        buttons.rejected.connect(on_rejected)

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            controller = EditorDialogController(
                dialog,
                buttons,
                is_new=True,
                title="Foreign signals",
            )
        self.assertEqual(_disconnect_warnings(recorded), [])

        buttons.accepted.emit()
        buttons.rejected.emit()
        self.assertEqual(foreign_accepted["n"], 1)
        self.assertEqual(foreign_rejected["n"], 1)
        controller.cleanup()
        buttons.accepted.emit()
        buttons.rejected.emit()
        self.assertEqual(foreign_accepted["n"], 2)
        self.assertEqual(foreign_rejected["n"], 2)

    def test_save_existing_record_then_close_clean(self) -> None:
        dialog = _StayOpenEditor(is_new=False)
        dialog.edit.setText("změna")
        dialog.controller.mark_dirty()
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            self.assertTrue(dialog.controller._run_save())
            self.assertTrue(dialog._saved)
            dialog.controller.close_button.click()
        self.assertEqual(_disconnect_warnings(recorded), [])

    def test_new_record_save_stay_open_then_close(self) -> None:
        dialog = _StayOpenEditor(is_new=True)
        dialog.edit.setText("nový")
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            dialog.controller.save_button.click()
            self.assertTrue(dialog._saved)
            self.assertFalse(dialog.controller.is_new)
            self.assertFalse(dialog.controller._cleaned)
            dialog.controller.close_button.click()
            self.assertTrue(dialog.controller._cleaned)
        self.assertEqual(_disconnect_warnings(recorded), [])


if __name__ == "__main__":
    unittest.main()
