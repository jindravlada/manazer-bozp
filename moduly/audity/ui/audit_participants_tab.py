from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from moduly.audity.ui.audit_participants_widget import AuditParticipantsWidget


class AuditParticipantsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        team_tab = QWidget()
        team_layout = QVBoxLayout(team_tab)
        team_info = QLabel(
            "Auditní tým tvoří THP pracovníci z nastavení aplikace.\n"
            "Výběr z THP pracovníků bude doplněn v další fázi."
        )
        team_info.setWordWrap(True)
        team_layout.addWidget(team_info)
        team_layout.addStretch()

        self.participants_widget = AuditParticipantsWidget()

        self.tabs.addTab(team_tab, "Auditní tým")
        self.tabs.addTab(self.participants_widget, "Účastníci auditu")

        layout.addWidget(self.tabs)

    def set_audit_id(self, audit_id: int | None) -> None:
        self.participants_widget.set_audit_id(audit_id)
