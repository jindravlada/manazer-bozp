from PySide6.QtWidgets import QMessageBox

class DialogManager:
    @staticmethod
    def info(parent,title,text):
        QMessageBox.information(parent,title,text)

    @staticmethod
    def warning(parent,title,text):
        QMessageBox.warning(parent,title,text)

    @staticmethod
    def error(parent,title,text):
        QMessageBox.critical(parent,title,text)

    @staticmethod
    def confirm(parent,title,text)->bool:
        return QMessageBox.question(
            parent,title,text,
            QMessageBox.Yes|QMessageBox.No,
            QMessageBox.No
        )==QMessageBox.Yes
