from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.widgets.no_wheel_guards import NoWheelComboBox


class CodeSelector(NoWheelComboBox):
    """Univerzální výběr hodnoty z číselníku s našeptávačem."""

    def __init__(self, values: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setEditable(True)

        if values:
            self.set_values(values)

    def set_values(self, values: list[str]):
        self.clear()
        self.addItems(values)

        completer = QCompleter(values, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)

        self.setCompleter(completer)

    def value(self) -> str:
        return self.currentText().strip()

    def set_value(self, value: str):
        self.setEditText(value or "")
