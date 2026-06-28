from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QTextEdit,
    QLabel,
)


class NotesWidget(QWidget):
    """
    Globální komponenta poznámek.
    Připraveno pro napojení na databázi.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._notes = []

        layout = QVBoxLayout(self)

        self.list = QListWidget()

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Napište poznámku...")

        buttons = QHBoxLayout()

        self.info = QLabel("Autor: -")

        self.btn_add = QPushButton("Přidat poznámku")
        self.btn_remove = QPushButton("Odebrat")

        buttons.addWidget(self.info)
        buttons.addStretch()
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_remove)

        layout.addWidget(self.list)
        layout.addWidget(self.editor)
        layout.addLayout(buttons)

        self.btn_add.clicked.connect(self.add_note)
        self.btn_remove.clicked.connect(self.remove_note)

    def add_note(self):
        text = self.editor.toPlainText().strip()
        if not text:
            return

        stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        record = {
            "datetime": stamp,
            "author": "-",
            "text": text,
        }

        self._notes.append(record)
        self.list.addItem(f"{stamp} | {record['author']} | {text[:60]}")
        self.editor.clear()

    def remove_note(self):
        row = self.list.currentRow()
        if row < 0:
            return

        self.list.takeItem(row)
        del self._notes[row]

    def notes(self):
        return list(self._notes)

    def clear(self):
        self._notes.clear()
        self.list.clear()
        self.editor.clear()
