from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel

class PageHeader(QWidget):
    def __init__(self,title:str,subtitle:str=''):
        super().__init__()
        l=QVBoxLayout(self)
        l.addWidget(QLabel(f'<b>{title}</b>'))
        if subtitle:
            l.addWidget(QLabel(subtitle))
