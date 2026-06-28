from PySide6.QtWidgets import QWidget,QHBoxLayout,QLineEdit,QComboBox

class TaskFilterWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        l=QHBoxLayout(self)
        self.search=QLineEdit()
        self.search.setPlaceholderText("Hledat...")
        self.status=QComboBox()
        self.status.addItems(["Vše","Nový","Rozpracovaný","Splněný"])
        l.addWidget(self.search)
        l.addWidget(self.status)
