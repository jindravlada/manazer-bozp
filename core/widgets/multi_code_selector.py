from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.code_selector import CodeSelector


class MultiCodeSelector(QWidget):
    """
    Výběr více hodnot z číselníku s našeptávačem.
    Hodnoty se ukládají jako text oddělený středníkem.
    """

    def __init__(self, values: list[str] | None = None, parent=None):
        super().__init__(parent)

        self.values = values or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()

        self.selector = CodeSelector(self.values)
        self.selector.set_value("")
        self.btn_add = QPushButton("Přidat")
        self.btn_remove = QPushButton("Odebrat")

        top.addWidget(self.selector, 1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_remove)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(72)

        layout.addLayout(top)
        layout.addWidget(self.list_widget)

        self.btn_add.clicked.connect(self.add_current)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.selector.lineEdit().returnPressed.connect(self.add_current)

    def add_current(self):
        value = self.selector.value()
        if not value:
            return

        current_values = self.selected_values()
        if value in current_values:
            return

        self.list_widget.addItem(value)
        self.selector.set_value("")

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_values(self) -> list[str]:
        return [
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        ]

    def value(self) -> str:
        return "; ".join(self.selected_values())

    def set_value(self, value: str):
        self.list_widget.clear()

        if not value:
            return

        if isinstance(value, list):
            values = value
        else:
            values = [part.strip() for part in str(value).split(";") if part.strip()]

        for item in values:
            self.list_widget.addItem(item)

    def has_value(self) -> bool:
        return bool(self.selected_values())

    def set_values(self, values: list[str]):
        self.values = values or []
        self.selector.set_values(self.values)
        self.selector.set_value("")
