from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.sluzby.audit_participant_service import audit_participant_service
from moduly.audity.ui.audit_participant_dialog import AuditParticipantDialog


class AuditParticipantsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit_id: int | None = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "Účastníky auditu lze přidat až po uložení auditu. "
            "Později půjde vybrat THP pracovníka i obecnou osobu."
        )
        self.info_label.setWordWrap(True)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Jméno", "Funkce", "Organizace"])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.info_label)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_participant)
        self.edit_btn.clicked.connect(self.edit_participant)
        self.delete_btn.clicked.connect(self.delete_participant)
        self.table.doubleClicked.connect(self.edit_participant)

        self._update_state()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.audit_id = audit_id
        self.refresh()
        self._update_state()

    def refresh(self) -> None:
        participants = []
        if self.audit_id is not None:
            participants = audit_participant_service.get_for_audit(self.audit_id)

        self.table.setRowCount(len(participants))
        for row, participant in enumerate(participants):
            values = [
                str(participant.id),
                participant.name or "—",
                participant.role or "—",
                participant.organization or "—",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _update_state(self) -> None:
        enabled = self.audit_id is not None
        self.info_label.setVisible(not enabled)
        self.add_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def _selected_participant_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def add_participant(self) -> None:
        if self.audit_id is None:
            return

        dialog = AuditParticipantDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.information(self, "Účastníci", "Vyplňte jméno účastníka.")
                return
            audit_participant_service.create_participant(self.audit_id, **data)
            self.refresh()

    def edit_participant(self) -> None:
        participant_id = self._selected_participant_id()
        if participant_id is None:
            QMessageBox.information(self, "Účastníci", "Vyberte účastníka.")
            return

        participant = audit_participant_service.get_by_id(participant_id)
        if participant is None:
            QMessageBox.warning(self, "Účastníci", "Účastník nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditParticipantDialog(self, participant=participant)
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                QMessageBox.information(self, "Účastníci", "Vyplňte jméno účastníka.")
                return
            audit_participant_service.update_participant(participant_id, **data)
            self.refresh()

    def delete_participant(self) -> None:
        participant_id = self._selected_participant_id()
        if participant_id is None:
            QMessageBox.information(self, "Účastníci", "Vyberte účastníka.")
            return

        answer = QMessageBox.question(
            self,
            "Smazat účastníka",
            "Opravdu smazat vybraného účastníka?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            audit_participant_service.delete_participant(participant_id)
            self.refresh()
