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

    def set_workplace_id(self, workplace_id):
        index = self.findData(workplace_id)
        if index >= 0:
            self.setCurrentIndex(index)
        elif self.include_empty:
            self.setCurrentIndex(0)
