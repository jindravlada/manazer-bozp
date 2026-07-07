from PySide6.QtWidgets import QComboBox

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service


class ResponsibilityRoleSelector(QComboBox):
    def __init__(self, parent=None, include_empty: bool = True):
        super().__init__(parent)

        self.include_empty = include_empty
        self.reload()

    def reload(self):
        self.clear()

        if self.include_empty:
            self.addItem("", None)

        roles = responsibility_role_service.get_all(include_inactive=False)
        roles = czech_sorted(roles, key=lambda role: role.name)

        for role in roles:
            self.addItem(role.name, role.id)

    def current_role_id(self):
        return self.currentData()

    def set_role_id(self, role_id, role_name: str = ""):
        if role_id is None:
            if self.include_empty:
                self.setCurrentIndex(0)
            return

        role_id = int(role_id)
        index = self.findData(role_id)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        name = str(role_name or "").strip()
        if not name:
            role = responsibility_role_service.get_by_id(role_id)
            name = role.name if role else f"Role #{role_id}"

        insert_at = 1 if self.include_empty else 0
        self.blockSignals(True)
        self.insertItem(insert_at, name, role_id)
        self.setCurrentIndex(insert_at)
        self.blockSignals(False)
