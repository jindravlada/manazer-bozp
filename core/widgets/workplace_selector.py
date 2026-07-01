from PySide6.QtWidgets import QComboBox

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.sluzby.settings_service import settings_service


class WorkplaceSelector(QComboBox):
    def __init__(self, parent=None, include_empty: bool = True):
        super().__init__(parent)

        self.include_empty = include_empty
        self.reload()

    def reload(self):
        self.clear()

        if self.include_empty:
            self.addItem("", None)

        workplaces = settings_service.get_workplaces(include_inactive=False)
        workplaces = czech_sorted(workplaces, key=lambda workplace: workplace.name)

        for workplace in workplaces:
            self.addItem(workplace.name, workplace.id)

    def current_workplace_id(self):
        return self.currentData()

    def set_workplace_id(self, workplace_id, workplace_name: str = ""):
        if workplace_id is None:
            if self.include_empty:
                self.setCurrentIndex(0)
            return

        workplace_id = int(workplace_id)
        index = self.findData(workplace_id)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        name = str(workplace_name or "").strip()
        if not name:
            workplace = settings_service.get_workplace_by_id(workplace_id)
            name = workplace.name if workplace else f"Pracoviště #{workplace_id}"

        insert_at = 1 if self.include_empty else 0
        self.blockSignals(True)
        self.insertItem(insert_at, name, workplace_id)
        self.setCurrentIndex(insert_at)
        self.blockSignals(False)

    def set_workplace(self, workplace_id=None, workplace_name: str = "") -> None:
        if workplace_id is not None:
            self.set_workplace_id(workplace_id, workplace_name)
            return

        name = str(workplace_name or "").strip()
        if not name:
            if self.include_empty:
                self.setCurrentIndex(0)
            return

        index = self.findText(name)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        insert_at = 1 if self.include_empty else 0
        self.blockSignals(True)
        self.insertItem(insert_at, name, None)
        self.setCurrentIndex(insert_at)
        self.blockSignals(False)
