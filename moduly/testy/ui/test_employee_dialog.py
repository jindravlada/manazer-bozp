"""Editor zaměstnance pro přezkušování."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.multi_responsibility_role_selector import (
    MultiResponsibilityRoleSelector,
)
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.constants import (
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    MODULE_NAME,
)
from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.sluzby.test_employee_service import (
    TestEmployeeError,
    test_employee_service,
)


class TestEmployeeDialog(QDialog):
    def __init__(
        self,
        parent=None,
        employee: TestEmployee | None = None,
        role_ids: list[int] | None = None,
    ):
        super().__init__(parent)
        self.employee_id = employee.id if employee is not None else None
        self.saved_employee_id: int | None = self.employee_id
        is_new = employee is None

        self.setWindowTitle(DIALOG_TITLE_NEW if is_new else DIALOG_TITLE_EDIT)
        configure_resizable_form_dialog(
            self,
            width=560,
            height=620,
            min_width=440,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.personal_number = QLineEdit()
        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.workplace = WorkplaceSelector(
            include_empty=True,
            allow_custom_value=False,
        )
        self.roles = MultiResponsibilityRoleSelector(self)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)
        self.may_examine = QCheckBox("Zkoušející / člen(ka) komise")

        form.addRow("Osobní číslo:", self.personal_number)
        form.addRow("Titul před jménem:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za jménem:", self.title_after)
        form.addRow("Provoz (pracoviště):", self.workplace)
        form.addRow("Funkce / role:", self.roles)
        form.addRow("", self.active_checkbox)
        form.addRow("", self.may_examine)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self._snapshot)
        self._editor.install_auto_dirty_tracking()
        self.roles.list_widget.model().rowsInserted.connect(self._editor.mark_dirty)
        self.roles.list_widget.model().rowsRemoved.connect(self._editor.mark_dirty)

        if employee is not None:
            self.personal_number.setText(employee.personal_number)
            self.title_before.setText(employee.title_before or "")
            self.first_name.setText(employee.first_name)
            self.last_name.setText(employee.last_name)
            self.title_after.setText(employee.title_after or "")
            self._set_workplace(employee.workplace_id)
            self.roles.set_role_ids(role_ids or [])
            self.active_checkbox.setChecked(employee.active)
            self.may_examine.setChecked(bool(employee.may_examine))

        self._editor.capture_baseline()

    def accept(self) -> None:
        data = self.get_data()
        try:
            if self.employee_id is None:
                created = test_employee_service.create_employee(**data)
                self.saved_employee_id = created.id
            else:
                updated = test_employee_service.update_employee_details(
                    self.employee_id,
                    **data,
                )
                self.saved_employee_id = updated.id
        except TestEmployeeError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "personal_number": self.personal_number.text(),
            "title_before": self.title_before.text(),
            "first_name": self.first_name.text(),
            "last_name": self.last_name.text(),
            "title_after": self.title_after.text(),
            "workplace_id": self._workplace_id(),
            "responsibility_role_ids": self.roles.selected_role_ids(),
            "may_examine": self.may_examine.isChecked(),
            "active": self.active_checkbox.isChecked(),
        }

    def _snapshot(self) -> tuple:
        return (
            self.personal_number.text(),
            self.title_before.text(),
            self.first_name.text(),
            self.last_name.text(),
            self.title_after.text(),
            self._workplace_id(),
            tuple(self.roles.selected_role_ids()),
            self.may_examine.isChecked(),
            self.active_checkbox.isChecked(),
        )

    def _workplace_id(self) -> int | None:
        """ID vybrané položky číselníku, ne první shoda podle názvu."""
        index = self.workplace.currentIndex()
        text = self.workplace.currentText().strip()
        if index < 0 or self.workplace.itemText(index).strip() != text:
            return None
        data = self.workplace.itemData(index)
        if not isinstance(data, int):
            return None
        return int(data)

    def _set_workplace(self, workplace_id: int) -> None:
        workplace = settings_service.get_workplace_by_id(workplace_id)
        label = ""
        if workplace is not None and not workplace.active:
            label = f"{workplace.name} (neaktivní)"
        self.workplace.set_workplace_id(workplace_id, label)
