import traceback
from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.table_utils import configure_table_columns
from moduly.audity.constants import (
    AUDIT_STATUS_BY_FILTER,
    AUDIT_STATUS_DOKONCENO,
    AUDIT_STATUS_FILTER_DOKONCENE,
    AUDIT_STATUS_FILTER_PLANOVANE,
    AUDIT_STATUS_FILTER_PROBIHAJICI,
    AUDIT_STATUS_FILTER_VSE,
    AUDIT_DETAILED_REPORT_BUTTON_LABEL,
    AUDIT_DETAILED_REPORT_DIALOG_TITLE,
    AUDIT_PROGRAM_BUTTON_LABEL,
    AUDIT_PROTOCOL_BUTTON_LABEL,
    AUDIT_PROTOCOL_DIALOG_TITLE,
    DEFAULT_AUDIT_STATUS_FILTER,
    KNOWLEDGE_EDITOR_BUTTON_LABEL,
    MODULE_NAME,
    YEAR_FILTER_VSE,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
from moduly.audity.ui.audit_dialog import AuditDialog
from moduly.audity.ui.audit_program_manager_banner_widget import (
    AuditProgramManagerBannerWidget,
)
from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
from moduly.audity.ui.audit_table import AuditTable
from moduly.audity.ui.rocni_zprava_auditu_dialog import RocniZpravaAudituDialog


class AudityPage(QWidget):
    """Hlavní stránka modulu Audity systémů řízení."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový audit")
        self.program_btn = QPushButton(AUDIT_PROGRAM_BUTTON_LABEL)
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        self.refresh_btn = QPushButton("Obnovit")
        self.protocol_btn = QPushButton(AUDIT_PROTOCOL_BUTTON_LABEL)
        self.protocol_btn.setEnabled(False)
        self.protocol_btn.setToolTip(
            "Export protokolu je dostupný pouze pro dokončené (uzavřené) audity."
        )
        self.detailed_report_btn = QPushButton(AUDIT_DETAILED_REPORT_BUTTON_LABEL)
        self.detailed_report_btn.setEnabled(False)
        self.detailed_report_btn.setToolTip(
            "Podrobná zpráva je dostupná pouze pro dokončené (uzavřené) audity."
        )
        self.knowledge_editor_btn = QPushButton(KNOWLEDGE_EDITOR_BUTTON_LABEL)
        self.report_btn = QPushButton("Roční zpráva")
        self.report_btn.setToolTip(
            "Roční zpráva z interních auditů za vybraný kalendářní rok."
        )

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            AUDIT_STATUS_FILTER_PROBIHAJICI,
            AUDIT_STATUS_FILTER_PLANOVANE,
            AUDIT_STATUS_FILTER_DOKONCENE,
            AUDIT_STATUS_FILTER_VSE,
        ])
        self.status_filter.setCurrentText(DEFAULT_AUDIT_STATUS_FILTER)

        self.year_filter = QComboBox()
        self._populate_year_filter()

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.program_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.protocol_btn)
        toolbar.addWidget(self.detailed_report_btn)
        toolbar.addWidget(self.knowledge_editor_btn)
        toolbar.addWidget(self.report_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Rok:"))
        toolbar.addWidget(self.year_filter)

        self.table = AuditTable()
        configure_table_columns(self.table, "audity")

        layout.addLayout(toolbar)

        self._program_manager_banner = AuditProgramManagerBannerWidget()
        layout.addWidget(self._program_manager_banner, 0)

        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_audit)
        self.program_btn.clicked.connect(self.open_program_manager)
        self.edit_btn.clicked.connect(self.open_selected_audit)
        self.delete_btn.clicked.connect(self.delete_selected_audit)
        self.refresh_btn.clicked.connect(self.refresh)
        self.protocol_btn.clicked.connect(self.export_selected_protocol)
        self.detailed_report_btn.clicked.connect(self.export_selected_detailed_report)
        self.knowledge_editor_btn.clicked.connect(self.open_knowledge_editor)
        self.report_btn.clicked.connect(self.open_annual_report)
        self.table.doubleClicked.connect(self.open_selected_audit)
        self.table.selectionModel().selectionChanged.connect(
            self._update_protocol_action
        )
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        audits = self._filter_audits(audit_service.get_all())
        self.table.load_audits(audits)
        configure_table_columns(self.table, "audity")
        self._program_manager_banner.refresh()
        self._update_protocol_action()

    def _populate_year_filter(self) -> None:
        current_year = date.today().year

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        self.year_filter.addItem(str(current_year), current_year)
        self.year_filter.addItem(YEAR_FILTER_VSE, YEAR_FILTER_VSE)
        self.year_filter.setCurrentIndex(0)
        self.year_filter.blockSignals(False)

    def _filter_audits(self, audits):
        mode = self.status_filter.currentText()
        if mode != AUDIT_STATUS_FILTER_VSE:
            status = AUDIT_STATUS_BY_FILTER.get(mode)
            if status is not None:
                audits = [
                    audit for audit in audits
                    if audit.status == status
                ]

        year_value = self.year_filter.currentData()
        if year_value != YEAR_FILTER_VSE:
            audits = [
                audit for audit in audits
                if (
                    (audit.audit_date is not None and audit.audit_date.year == year_value)
                    or (audit.audit_date is None and audit.year == year_value)
                )
            ]

        return audits

    def _selected_audit_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _selected_audit(self):
        audit_id = self._selected_audit_id()
        if audit_id is None:
            return None
        return audit_service.get_by_id(audit_id)

    def _update_protocol_action(self, *_args) -> None:
        audit = self._selected_audit()
        enabled = audit is not None and audit.status == AUDIT_STATUS_DOKONCENO
        self.protocol_btn.setEnabled(enabled)
        self.detailed_report_btn.setEnabled(enabled)

    def new_audit(self) -> None:
        dialog = AuditDialog(self)
        if exec_maximized(dialog):
            data = dialog.get_data()
            audit = audit_service.create_audit(**dialog.prepare_save_payload(data))
            dialog.save_commission_members(audit.id, data)
            self.refresh()

    def open_selected_audit(self) -> None:
        audit_id = self._selected_audit_id()
        if audit_id is None:
            QMessageBox.information(self, MODULE_NAME, "Vyberte audit.")
            return

        self.open_audit(audit_id)

    def open_audit(self, audit_id: int) -> None:
        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, MODULE_NAME, "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditDialog(self, audit=audit)
        if exec_maximized(dialog):
            data = dialog.get_data()
            audit_service.update_audit(
                audit_id,
                **dialog.prepare_save_payload(data),
            )
            dialog.save_commission_members(audit_id, data)
            self.refresh()

    def export_selected_protocol(self) -> None:
        audit = self._selected_audit()
        if audit is None:
            QMessageBox.information(self, AUDIT_PROTOCOL_DIALOG_TITLE, "Vyberte audit.")
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                "Protokol lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._update_protocol_action()
            return

        try:
            protokol_audit_service.open_for_audit(audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                f"Protokol se nepodařilo vygenerovat.\n\n{exc}",
            )

    def export_selected_detailed_report(self) -> None:
        audit = self._selected_audit()
        if audit is None:
            QMessageBox.information(
                self, AUDIT_DETAILED_REPORT_DIALOG_TITLE, "Vyberte audit."
            )
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                "Podrobnou zprávu lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._update_protocol_action()
            return

        try:
            protokol_audit_service.open_detailed_report_for_audit(audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                f"Podrobnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def open_knowledge_editor(self) -> None:
        exec_maximized(AudityKnowledgeEditorDialog(self))

    def open_program_manager(self) -> None:
        exec_maximized(AuditProgramManagerDialog(self))

    def open_annual_report(self) -> None:
        year_value = self.year_filter.currentData()
        if year_value == YEAR_FILTER_VSE:
            year_value = date.today().year
        exec_maximized(RocniZpravaAudituDialog(self, year=year_value))

    def delete_selected_audit(self) -> None:
        audit_id = self._selected_audit_id()
        if audit_id is None:
            QMessageBox.information(self, MODULE_NAME, "Vyberte audit.")
            return

        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, MODULE_NAME, "Audit nebyl nalezen.")
            self.refresh()
            return

        answer = QMessageBox.question(
            self,
            "Smazat audit",
            f"Opravdu smazat audit {audit.number or audit_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            audit_service.delete_audit(audit_id)
            self.refresh()
