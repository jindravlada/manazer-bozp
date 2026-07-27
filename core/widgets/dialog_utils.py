from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QWidget,
)

from core.widgets.editor_dialog_controller import (
    configure_editor_buttons,
    create_editor_button_box,
)


def _app_style() -> QStyle:
    return QApplication.style()


def _standard_icon(pixmap: QStyle.StandardPixmap) -> QIcon:
    return _app_style().standardIcon(pixmap)


def configure_save_cancel_buttons(
    buttons: QDialogButtonBox,
    *,
    is_new: bool = True,
) -> None:
    """UX-DIALOG-2: Uložit + Zrušit (nový) / Zavřít (existující)."""
    configure_editor_buttons(buttons, is_new=is_new)


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


def create_save_cancel_box(
    parent: QWidget | None = None,
    *,
    is_new: bool = True,
) -> QDialogButtonBox:
    return create_editor_button_box(parent, is_new=is_new)


def create_close_box(parent: QWidget | None = None) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=parent)
    configure_close_button(buttons)
    return buttons


def add_work_dialog_footer(
    parent_layout,
    *,
    work_widgets: list[QWidget] | None = None,
    buttons: QDialogButtonBox | None = None,
    is_new: bool = True,
) -> QDialogButtonBox:
    if buttons is None:
        buttons = create_save_cancel_box(is_new=is_new)

    row = QHBoxLayout()
    for widget in work_widgets or []:
        row.addWidget(widget)
    row.addStretch()
    row.addWidget(buttons)
    parent_layout.addLayout(row)
    return buttons


def add_save_cancel_footer(
    parent_layout,
    dialog: QDialog,
    *,
    is_new: bool = True,
) -> QDialogButtonBox:
    buttons = create_save_cancel_box(dialog, is_new=is_new)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    parent_layout.addWidget(buttons)
    return buttons


def configure_resizable_form_dialog(
    dialog: QDialog,
    *,
    width: int = 720,
    height: int = 640,
    min_width: int = 480,
    min_height: int = 400,
) -> None:
    dialog.setMinimumSize(min_width, min_height)

    screen = QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        if available.isValid():
            max_width = max(min_width, available.width())
            max_height = max(min_height, available.height())
            dialog.setMaximumSize(max_width, max_height)
            width = min(width, max_width)
            height = min(height, max_height)

    dialog.resize(width, height)


def wrap_in_scroll_area(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    scroll.setWidget(content)
    return scroll


def configure_form_tab_navigation(root: QWidget) -> None:
    """Tab / Shift+Tab přesouvají fokus mezi poli; v QTextEdit nevkládají odsazení."""
    from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea, QTextEdit

    for widget in root.findChildren(QTextEdit):
        widget.setTabChangesFocus(True)
    for widget in root.findChildren(QPlainTextEdit):
        widget.setTabChangesFocus(True)
    for widget in root.findChildren(QLabel):
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    for widget in root.findChildren(QScrollArea):
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)


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
