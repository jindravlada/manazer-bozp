import traceback
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import (
    ENTITY_AUDITY,
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_NESHODA,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_POZOROVANI,
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_ZJISTENI,
)
from core.shared.sluzby.finding_service import finding_service
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
    SETTLEMENT_OVERVIEW_BUTTON_LABEL,
    DEFAULT_AUDIT_STATUS_FILTER,
    EXTRAORDINARY_QUESTIONS_BUTTON_LABEL,
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
from moduly.audity.ui.extraordinary_questions_dialog import ExtraordinaryQuestionsDialog
from moduly.audity.ui.audit_table import AuditTable
from moduly.audity.ui.prehled_vyporadani_dialog import PrehledVyporadaniDialog
from moduly.audity.ui.rocni_zprava_auditu_dialog import RocniZpravaAudituDialog
from moduly.externi_audity.constants import EXTERNAL_AUDITS_BUTTON_LABEL
from moduly.externi_audity.ui.external_audits_overview_dialog import (
    ExternalAuditsOverviewDialog,
)

_FINDING_COLUMN_BY_TYPE = {
    FINDING_TYPE_ZAVADA: "zavady",
    FINDING_TYPE_NEDOSTATEK: "nedostatky",
    FINDING_TYPE_PORUSENI_PREDPISU: "poruseni",
    FINDING_TYPE_NESHODA: "neshody",
    FINDING_TYPE_POZOROVANI: "pozorovani",
    FINDING_TYPE_ZJISTENI: "zjisteni",
    FINDING_TYPE_PRILEZITOST: "pkz",
}

_COUNT_KEYS = (
    "zavady",
    "nedostatky",
    "poruseni",
    "neshody",
    "pozorovani",
    "zjisteni",
    "pkz",
)


def _empty_finding_counts() -> dict[str, int]:
    return {
        "total": 0,
        "zavady": 0,
        "nedostatky": 0,
        "poruseni": 0,
        "neshody": 0,
        "pozorovani": 0,
        "zjisteni": 0,
        "pkz": 0,
        "ostatni": 0,
    }


class _AuditRow:
    def __init__(self, audit, *, counts: dict[str, int]):
        self.id = audit.id
        self.number = audit.number
        self.year = audit.year
        self.planned_month = audit.planned_month
        self.workplace_name = audit.workplace_name
        self.audit_date = audit.audit_date
        self.status = audit.status
        self.audit_type = audit.audit_type
        self.findings_total_count = int(counts.get("total", 0) or 0)
        self.zavady_count = int(counts.get("zavady", 0) or 0)
        self.nedostatky_count = int(counts.get("nedostatky", 0) or 0)
        self.poruseni_count = int(counts.get("poruseni", 0) or 0)
        self.neshody_count = int(counts.get("neshody", 0) or 0)
        self.pozorovani_count = int(counts.get("pozorovani", 0) or 0)
        self.zjisteni_count = int(counts.get("zjisteni", 0) or 0)
        self.pkz_count = int(counts.get("pkz", 0) or 0)
        self.ostatni_count = int(counts.get("ostatni", 0) or 0)


class AudityPage(QWidget):
    """Hlavní stránka modulu Audity systémů řízení."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový audit")
        self.program_btn = QPushButton(AUDIT_PROGRAM_BUTTON_LABEL)
        self.extraordinary_btn = QPushButton(EXTRAORDINARY_QUESTIONS_BUTTON_LABEL)
        self.external_audits_btn = QPushButton(EXTERNAL_AUDITS_BUTTON_LABEL)
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        self.protocol_btn = QPushButton(AUDIT_PROTOCOL_BUTTON_LABEL)
        self.protocol_btn.setToolTip(
            "Export protokolu je dostupný pouze pro dokončené (uzavřené) audity."
        )
        self.detailed_report_btn = QPushButton(AUDIT_DETAILED_REPORT_BUTTON_LABEL)
        self.detailed_report_btn.setToolTip(
            "Podrobná zpráva je dostupná pouze pro dokončené (uzavřené) audity."
        )
        self.knowledge_editor_btn = QPushButton(KNOWLEDGE_EDITOR_BUTTON_LABEL)
        self.report_btn = QPushButton("Roční zpráva")
        self.report_btn.setToolTip(
            "Roční zpráva z interních auditů za vybraný kalendářní rok."
        )
        self.settlement_btn = QPushButton(SETTLEMENT_OVERVIEW_BUTTON_LABEL)
        self.settlement_btn.setToolTip(
            "Historické přehledy vypořádání zjištění z dokončených interních auditů."
        )

        self._single_record_buttons = (self.edit_btn, self.delete_btn)
        for button in self._single_record_buttons:
            button.setEnabled(False)
        self.protocol_btn.setEnabled(False)
        self.detailed_report_btn.setEnabled(False)

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
        toolbar.addWidget(self.extraordinary_btn)
        toolbar.addWidget(self.external_audits_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.protocol_btn)
        toolbar.addWidget(self.detailed_report_btn)
        toolbar.addWidget(self.knowledge_editor_btn)
        toolbar.addWidget(self.report_btn)
        toolbar.addWidget(self.settlement_btn)
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
        self.extraordinary_btn.clicked.connect(self.open_extraordinary_questions)
        self.external_audits_btn.clicked.connect(self.open_external_audits)
        self.edit_btn.clicked.connect(self.open_selected_audit)
        self.delete_btn.clicked.connect(self.delete_selected_audit)
        self.protocol_btn.clicked.connect(self.export_selected_protocol)
        self.detailed_report_btn.clicked.connect(self.export_selected_detailed_report)
        self.knowledge_editor_btn.clicked.connect(self.open_knowledge_editor)
        self.report_btn.clicked.connect(self.open_annual_report)
        self.settlement_btn.clicked.connect(self.open_settlement_overviews)
        self.table.doubleClicked.connect(self.open_selected_audit)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(
            self._refresh_action_buttons
        )
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        audits = self._filter_audits(audit_service.get_all())
        audit_ids = [int(audit.id) for audit in audits]
        findings = finding_service.get_for_entities(ENTITY_AUDITY, audit_ids)

        counts_by_audit_id: dict[int, dict[str, int]] = {
            audit_id: _empty_finding_counts()
            for audit_id in audit_ids
        }

        for finding in findings:
            audit_id = int(getattr(finding, "entity_id", 0) or 0)
            bucket = counts_by_audit_id.get(audit_id)
            if bucket is None:
                continue

            bucket["total"] += 1
            code = str(getattr(finding, "finding_type", "") or "").strip()
            column = _FINDING_COLUMN_BY_TYPE.get(code)
            if column is not None:
                bucket[column] += 1

        for bucket in counts_by_audit_id.values():
            mapped = sum(int(bucket.get(key, 0) or 0) for key in _COUNT_KEYS)
            bucket["ostatni"] = int(bucket["total"]) - mapped

        rows = [
            _AuditRow(audit, counts=counts_by_audit_id.get(audit.id, _empty_finding_counts()))
            for audit in audits
        ]
        self.table.load_audits(rows)
        configure_table_columns(self.table, "audity")
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self._program_manager_banner.refresh()
        self._refresh_action_buttons()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        single = self._selected_row_count() == 1
        for button in self._single_record_buttons:
            button.setEnabled(single)

        audit = self._selected_audit() if single else None
        completed = audit is not None and audit.status == AUDIT_STATUS_DOKONCENO
        self.protocol_btn.setEnabled(completed)
        self.detailed_report_btn.setEnabled(completed)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        single = self._selected_row_count() == 1
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction(self.edit_btn.text(), self.open_selected_audit)
        delete_action = menu.addAction(self.delete_btn.text(), self.delete_selected_audit)
        edit_action.setEnabled(single)
        delete_action.setEnabled(single)

        if single and self.protocol_btn.isEnabled():
            menu.addSeparator()
            menu.addAction(self.protocol_btn.text(), self.export_selected_protocol)
            menu.addAction(
                self.detailed_report_btn.text(),
                self.export_selected_detailed_report,
            )

        menu.exec(self.table.viewport().mapToGlobal(position))

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
        if self._selected_row_count() != 1:
            return None

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
        # Kompatibilita se staršími testy / voláními.
        self._refresh_action_buttons()

    def new_audit(self) -> None:
        dialog = AuditDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def open_selected_audit(self) -> None:
        audit_id = self._selected_audit_id()
        if audit_id is None:
            return

        self.open_audit(audit_id)

    def open_audit(self, audit_id: int) -> None:
        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, MODULE_NAME, "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditDialog(self, audit=audit)
        exec_maximized(dialog)
        self.refresh()

    def export_selected_protocol(self) -> None:
        audit = self._selected_audit()
        if audit is None:
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                "Protokol lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._refresh_action_buttons()
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
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                "Podrobnou zprávu lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._refresh_action_buttons()
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

    def open_extraordinary_questions(self) -> None:
        exec_maximized(ExtraordinaryQuestionsDialog(self))

    def open_external_audits(self) -> None:
        exec_maximized(ExternalAuditsOverviewDialog(self))

    def open_settlement_overviews(self) -> None:
        exec_maximized(PrehledVyporadaniDialog(self))

    def open_annual_report(self) -> None:
        year_value = self.year_filter.currentData()
        if year_value == YEAR_FILTER_VSE:
            year_value = date.today().year
        exec_maximized(RocniZpravaAudituDialog(self, year=year_value))

    def delete_selected_audit(self) -> None:
        audit_id = self._selected_audit_id()
        if audit_id is None:
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
