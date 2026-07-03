from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QStyle,
    QWidget,
)


def _app_style() -> QStyle:
    return QApplication.style()


def _standard_icon(pixmap: QStyle.StandardPixmap) -> QIcon:
    return _app_style().standardIcon(pixmap)


def configure_save_cancel_buttons(buttons: QDialogButtonBox) -> None:
    save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
    if save_btn is not None:
        save_btn.setText("Uložit")
        save_btn.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))

    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        ok_btn.setText("Uložit")
        ok_btn.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))

    cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel_btn is not None:
        cancel_btn.setText("Zrušit")
        cancel_btn.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCancelButton))


def configure_close_button(buttons: QDialogButtonBox) -> None:
    close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
    if close_btn is not None:
        close_btn.setText("Zavřít")
        close_btn.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCloseButton))


def configure_close_push_button(button: QPushButton) -> None:
    button.setText("Zavřít")
    button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCloseButton))


def configure_navigate_button(button: QPushButton) -> None:
    button.setText("Přejít")
    icon = _standard_icon(QStyle.StandardPixmap.SP_ArrowForward)
    if icon.isNull():
        icon = _standard_icon(QStyle.StandardPixmap.SP_ArrowRight)
    button.setIcon(icon)


def create_save_cancel_box(parent: QWidget | None = None) -> QDialogButtonBox:
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save,
        parent=parent,
    )
    configure_save_cancel_buttons(buttons)
    return buttons


def create_close_box(parent: QWidget | None = None) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=parent)
    configure_close_button(buttons)
    return buttons


def add_work_dialog_footer(
    parent_layout,
    *,
    work_widgets: list[QWidget] | None = None,
    buttons: QDialogButtonBox | None = None,
) -> QDialogButtonBox:
    if buttons is None:
        buttons = create_save_cancel_box()

    row = QHBoxLayout()
    for widget in work_widgets or []:
        row.addWidget(widget)
    row.addStretch()
    row.addWidget(buttons)
    parent_layout.addLayout(row)
    return buttons


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


def prepare_work_dialog_maximized(dialog: QDialog) -> None:
    """Prepare a large work dialog for maximized display across window managers."""
    if dialog.minimumWidth() <= 0 or dialog.minimumHeight() <= 0:
        dialog.setMinimumSize(480, 400)

    screen = QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        if available.isValid():
            dialog.resize(available.size())
            dialog.move(available.topLeft())

    dialog.setWindowState(dialog.windowState() | Qt.WindowState.WindowMaximized)
    dialog.showMaximized()
    QApplication.processEvents()


def exec_maximized(dialog: QDialog) -> int:
    prepare_work_dialog_maximized(dialog)
    return dialog.exec()


# Zpětná kompatibilita
apply_save_cancel_labels = configure_save_cancel_buttons
apply_close_label = configure_close_button
