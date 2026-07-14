from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.sluzby.hazard_identification_service import hazard_identification_service
from moduly.rizeni_rizik.ui.hazard_identification_table import HazardIdentificationTable


class RizeniRizikPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová identifikace")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()

        self.table = HazardIdentificationTable()
        configure_table_columns(self.table, "hazard_identifications")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat identifikaci...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        identifications = hazard_identification_service.get_all(include_inactive=True)
        self.table.load_identifications(identifications)
        configure_table_columns(self.table, "hazard_identifications")
        self.text_filter.update_count()
