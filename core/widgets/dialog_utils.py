from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QScrollArea, QWidget


def configure_resizable_form_dialog(
    dialog: QDialog,
    *,
    width: int = 720,
    height: int = 640,
    min_width: int = 480,
    min_height: int = 400,
) -> None:
    dialog.resize(width, height)
    dialog.setMinimumSize(min_width, min_height)


def wrap_in_scroll_area(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


def apply_save_cancel_labels(buttons: QDialogButtonBox) -> None:
    save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
    if save_btn is not None:
        save_btn.setText("Uložit")
    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        ok_btn.setText("Uložit")
    cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel_btn is not None:
        cancel_btn.setText("Zrušit")


def apply_close_label(buttons: QDialogButtonBox) -> None:
    close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
    if close_btn is not None:
        close_btn.setText("Zavřít")


def exec_maximized(dialog: QDialog) -> int:
    dialog.showMaximized()
    return dialog.exec()
