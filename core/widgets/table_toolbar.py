from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QComboBox,QLabel
from .filter_bar import FilterBar

class TableToolbar(QWidget):
    """Globální panel nad tabulkami."""
    def __init__(self, table, show_active_filter=True, parent=None):
        super().__init__(parent)
        l=QHBoxLayout(self)
        l.setContentsMargins(0,0,0,0)

        self.btn_add=QPushButton("Přidat")
        self.btn_edit=QPushButton("Upravit")
        self.btn_toggle=QPushButton("Aktivovat / Deaktivovat")

        l.addWidget(self.btn_add)
        l.addWidget(self.btn_edit)
        l.addWidget(self.btn_toggle)

        l.addStretch()

        self.cmb_filter=None
        if show_active_filter:
            l.addWidget(QLabel("Zobrazit:"))
            self.cmb_filter=QComboBox()
            self.cmb_filter.addItems(["Aktivní","Všichni"])
            l.addWidget(self.cmb_filter)

        self.filter_bar=FilterBar(table)
