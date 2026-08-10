"""Dialog pro doplnění nových auditovaných pracovišť do programu."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_close_push_button
from moduly.audity.constants import AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_DIALOG_TITLE
from moduly.audity.sluzby.audit_program_service import MissingAuditableWorkplace


class AuditProgramSupplementWorkplacesDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        workplaces: tuple[MissingAuditableWorkplace, ...],
    ):
        super().__init__(parent)

        self.setWindowTitle(AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_DIALOG_TITLE)
        self.resize(520, 360)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Vyberte auditovaná pracoviště z nastavení, která mají být doplněna "
            "do programu. Pro nová pracoviště se vygenerují návštěvy a rozdělí "
            "řídicí procesy."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._list = QListWidget()
        for workplace in workplaces:
            item = QListWidgetItem(
                f"{workplace.workplace_name} "
                f"(interval {workplace.audit_interval_months} měs.)"
            )
            item.setData(Qt.ItemDataRole.UserRole, workplace.workplace_id)
            item.setCheckState(Qt.CheckState.Checked)
            self._list.addItem(item)
        layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox(self)
        self.use_btn = QPushButton("Použít")
        self.use_btn.setDefault(True)
        apply_icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogApplyButton
        )
        if apply_icon.isNull():
            apply_icon = QApplication.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogOkButton
            )
        self.use_btn.setIcon(apply_icon)

        self.close_btn = QPushButton("Zavřít")
        configure_close_push_button(self.close_btn)

        buttons.addButton(self.use_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.use_btn.clicked.connect(self._accept_if_valid)
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if self.selected_workplace_ids():
            self.accept()

    def selected_workplace_ids(self) -> tuple[int, ...]:
        selected: list[int] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            workplace_id = item.data(Qt.ItemDataRole.UserRole)
            if workplace_id is not None:
                selected.append(int(workplace_id))
        return tuple(selected)
