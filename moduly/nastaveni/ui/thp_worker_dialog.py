from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLabel,
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
from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.multi_responsibility_role_selector import (
    MultiResponsibilityRoleSelector,
)
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.nastaveni.sluzby.settings_service import (
    SettingsWorkerError,
    settings_service,
)

POSITION_HINT = (
    "Pracovní funkce zaměstnance. "
    "Tento údaj se používá také při automatickém vyplňování dokumentů, "
    "například v Koordinaci BOZP."
)
ROLES_HINT = (
    "Funkce a role zaměstnance podle číselníku. "
    "Používají se například při přípravě a evidenci zkoušek. "
    "Nemění údaj v poli Funkce."
)


def _hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("MutedText")
    label.setWordWrap(True)
    set_widget_tooltip(label, text)
    return label


class ThpWorkerDialog(QDialog):
    def __init__(self, parent=None, worker=None):
        super().__init__(parent)
        self.worker_id = worker.id if worker is not None else None
        self.saved_worker_id: int | None = self.worker_id
        is_new = worker is None

        self.setWindowTitle("Nový zaměstnanec" if is_new else "Upravit zaměstnance")
        configure_resizable_form_dialog(
            self,
            width=560,
            height=720,
            min_width=440,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.position = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.performs_controls_checkbox = QCheckBox("Provádí kontroly")
        self.personal_number = QLineEdit()
        self.workplace = WorkplaceSelector(
            include_empty=True,
            allow_custom_value=False,
        )
        self.roles = MultiResponsibilityRoleSelector(self)
        self.is_thp_checkbox = QCheckBox("Vedoucí zaměstnanec / THP")
        self.may_examine = QCheckBox("Zkoušející / člen(ka) komise")
        self.active_checkbox = QCheckBox("Aktivní")

        self.position_hint = _hint_label(POSITION_HINT)
        self.roles_hint = _hint_label(ROLES_HINT)
        set_widget_tooltip(self.position, POSITION_HINT)
        set_widget_tooltip(self.roles, ROLES_HINT)

        if is_new:
            self.active_checkbox.setChecked(True)
            self.is_thp_checkbox.setChecked(False)
            self.performs_controls_checkbox.setChecked(False)
            self.may_examine.setChecked(False)

        form.addRow("Titul před jménem:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za jménem:", self.title_after)
        form.addRow("Funkce:", self.position)
        form.addRow("", self.position_hint)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("", self.performs_controls_checkbox)
        form.addRow("Osobní číslo:", self.personal_number)
        form.addRow("Provoz (pracoviště):", self.workplace)
        form.addRow("Funkce / role:", self.roles)
        form.addRow("", self.roles_hint)
        form.addRow("", self.is_thp_checkbox)
        form.addRow("", self.may_examine)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=is_new)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if worker is not None:
            self.title_before.setText(worker.title_before or "")
            self.first_name.setText(worker.first_name or "")
            self.last_name.setText(worker.last_name or "")
            self.title_after.setText(worker.title_after or "")
            self.position.setText(worker.position or "")
            self.phone.setText(worker.phone or "")
            self.email.setText(worker.email or "")
            self.performs_controls_checkbox.setChecked(bool(worker.performs_controls))
            self.personal_number.setText(worker.personal_number or "")
            self._set_workplace(worker.workplace_id)
            self.roles.set_role_ids(
                settings_service.list_worker_role_ids(worker.id)
            )
            self.is_thp_checkbox.setChecked(bool(worker.is_thp))
            self.may_examine.setChecked(bool(worker.may_examine))
            self.active_checkbox.setChecked(bool(worker.active))

    def accept(self) -> None:
        if self.workplace.currentText().strip() and self._workplace_id() is None:
            QMessageBox.warning(
                self,
                "Zaměstnanci",
                "Zvolený provoz nebo pracoviště neexistuje.",
            )
            return
        data = self.get_data()
        try:
            payload = dict(data)
            if self.worker_id is not None:
                payload["id"] = self.worker_id
            saved = settings_service.save_worker(**payload)
        except SettingsWorkerError as error:
            QMessageBox.warning(self, "Zaměstnanci", str(error))
            return
        self.saved_worker_id = saved.id
        super().accept()

    def get_data(self) -> dict:
        return {
            "title_before": self.title_before.text().strip(),
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "title_after": self.title_after.text().strip(),
            "position": self.position.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "performs_controls": self.performs_controls_checkbox.isChecked(),
            "personal_number": self.personal_number.text().strip(),
            "workplace_id": self._workplace_id(),
            "responsibility_role_ids": self.roles.selected_role_ids(),
            "is_thp": self.is_thp_checkbox.isChecked(),
            "may_examine": self.may_examine.isChecked(),
            "active": self.active_checkbox.isChecked(),
        }

    def _workplace_id(self) -> int | None:
        index = self.workplace.currentIndex()
        text = self.workplace.currentText().strip()
        if index < 0 or self.workplace.itemText(index).strip() != text:
            return None
        data = self.workplace.itemData(index)
        if not isinstance(data, int):
            return None
        return int(data)

    def _set_workplace(self, workplace_id: int | None) -> None:
        if workplace_id is None:
            return
        workplace = settings_service.get_workplace_by_id(workplace_id)
        label = ""
        if workplace is not None and not workplace.active:
            label = f"{workplace.name} (neaktivní)"
        self.workplace.set_workplace_id(workplace_id, label)
