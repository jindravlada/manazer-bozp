from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.multi_exposed_group_selector import MultiExposedGroupSelector
from moduly.nastaveni.ui.exposed_groups_management_dialog import (
    ExposedGroupsManagementDialog,
)


class ProfessionDialog(QDialog):
    """Přidání / úprava profese s výběrem ohrožených skupin."""

    def __init__(self, parent=None, profession=None, group_ids: list[int] | None = None):
        super().__init__(parent)

        self.setWindowTitle("Profese")
        configure_resizable_form_dialog(self, width=560, height=480, min_width=440, min_height=360)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 9999)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)
        self.groups = MultiExposedGroupSelector(self)

        groups_row = QWidget()
        groups_layout = QVBoxLayout(groups_row)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_toolbar = QHBoxLayout()
        manage_btn = QPushButton("Správa ohrožených skupin…")
        manage_btn.clicked.connect(self._manage_groups)
        groups_toolbar.addWidget(manage_btn)
        groups_toolbar.addStretch()
        groups_layout.addLayout(groups_toolbar)
        groups_layout.addWidget(self.groups)
        hint = QLabel(
            "Vyberte jednu nebo více ohrožených skupin, které profese zahrnuje."
        )
        hint.setWordWrap(True)
        groups_layout.addWidget(hint)

        form.addRow("Název:", self.name)
        form.addRow("Poznámka:", self.note)
        form.addRow("Pořadí:", self.sort_order)
        form.addRow("", self.active_checkbox)
        form.addRow("Ohrožené skupiny:", groups_row)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if profession is not None:
            self.name.setText(profession.name)
            self.note.setPlainText(profession.note or "")
            self.sort_order.setValue(profession.sort_order)
            self.active_checkbox.setChecked(profession.active)
        if group_ids:
            self.groups.set_group_ids(group_ids)

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "note": self.note.toPlainText().strip(),
            "sort_order": self.sort_order.value(),
            "active": self.active_checkbox.isChecked(),
            "exposed_group_ids": self.groups.selected_group_ids(),
        }

    def _manage_groups(self) -> None:
        current = self.groups.selected_group_ids()
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self.groups.reload(preserve_ids=current)
