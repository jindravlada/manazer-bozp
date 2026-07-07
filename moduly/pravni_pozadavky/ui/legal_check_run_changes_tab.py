from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.ui.legal_change_table import LegalChangeTable


class LegalCheckRunChangesTab(QWidget):
    def __init__(self, run_id: int | None = None):
        super().__init__()
        self.run_id = run_id

        layout = QVBoxLayout(self)

        if run_id is None:
            layout.addWidget(QLabel("Změny budou dostupné až po uložení kontroly."))
            self.table = None
            return

        self.table = LegalChangeTable()
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        if self.table is None or self.run_id is None:
            return
        changes = legal_change_service.list_by_check_run(
            self.run_id,
            include_inactive=True,
        )
        self.table.load_changes(changes)
