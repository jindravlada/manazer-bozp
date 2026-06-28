from PySide6.QtWidgets import QDialog

class SetreniDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Šetření úrazu")
