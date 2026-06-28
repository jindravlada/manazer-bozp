from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QSizePolicy


class SearchComboBox(QComboBox):
    """
    Jednotný rozbalovací výběr s našeptávačem.

    - šipka pro rozbalení celého seznamu
    - možnost psát vlastní text
    - našeptávání podle části textu bez ohledu na velikost písmen
    """

    def __init__(self, values: list[str] | None = None, parent=None, allow_custom_value: bool = True):
        super().__init__(parent)

        self.allow_custom_value = allow_custom_value

        self.setEditable(True)
        self.setDuplicatesEnabled(False)
        self.setInsertPolicy(QComboBox.NoInsert if allow_custom_value else QComboBox.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(22)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if values:
            self.set_items(values)

    def set_items(self, values: list[str], include_empty: bool = False):
        current = self.currentText().strip()

        self.clear()

        if include_empty:
            self.addItem("")

        clean_values = []
        seen = set()
        for value in values or []:
            value = str(value).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            clean_values.append(value)

        self.addItems(clean_values)

        completer_values = ([""] if include_empty else []) + clean_values
        completer = QCompleter(completer_values, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current:
            self.setCurrentText(current)

    def value(self) -> str:
        return self.currentText().strip()

    def set_value(self, value: str):
        self.setCurrentText(value or "")
