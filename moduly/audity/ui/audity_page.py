from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.audity.constants import (
    AUDIT_STATUS_BY_FILTER,
    AUDIT_STATUS_FILTER_DOKONCENE,
    AUDIT_STATUS_FILTER_PLANOVANE,
    AUDIT_STATUS_FILTER_PROBEHAJICI,
    AUDIT_STATUS_FILTER_VSE,
    DEFAULT_AUDIT_STATUS_FILTER,
)
from moduly.audity.sluzby.internal_audit_service import internal_audit_service
from moduly.audity.ui.internal_audit_dialog import InternalAuditDialog
from moduly.audity.ui.internal_audit_table import InternalAuditTable


class AudityPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový audit")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            AUDIT_STATUS_FILTER_PROBEHAJICI,
            AUDIT_STATUS_FILTER_PLANOVANE,
            AUDIT_STATUS_FILTER_DOKONCENE,
            AUDIT_STATUS_FILTER_VSE,
        ])
        self.status_filter.setCurrentText(DEFAULT_AUDIT_STATUS_FILTER)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.status_filter)

        self.table = InternalAuditTable()
        configure_table_columns(self.table, "internal_audits")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat audit...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_audit)
        self.edit_btn.clicked.connect(self.edit_selected_audit)
        self.delete_btn.clicked.connect(self.delete_selected_audit)
        self.table.doubleClicked.connect(self.edit_selected_audit)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self):
        audits = internal_audit_service.get_all()
        audits = self._filter_audits(audits)
        self.table.load_audits(audits)
        configure_table_columns(self.table, "internal_audits")
        self.text_filter.update_count()

    def _filter_audits(self, audits):
        mode = self.status_filter.currentText()
        if mode == AUDIT_STATUS_FILTER_VSE:
            return audits

        status = AUDIT_STATUS_BY_FILTER.get(mode)
        if status is None:
            return audits

        return [audit for audit in audits if audit.status == status]

    def _selected_audit_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None

        return int(item.text())

    def new_audit(self):
        dialog = InternalAuditDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            workplace = internal_audit_service.resolve_workplace_name(data.pop("workplace_id"))
            internal_audit_service.create_audit(workplace=workplace, **data)
            self.refresh()

    def edit_selected_audit(self):
        audit_id = self._selected_audit_id()
        if audit_id is None:
            QMessageBox.information(self, "Audity", "Vyberte audit.")
            return

        self.open_audit(audit_id)

    def open_audit(self, audit_id: int):
        audit = internal_audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, "Audity", "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = InternalAuditDialog(self, audit=audit)
        if dialog.exec():
            data = dialog.get_data()
            workplace = internal_audit_service.resolve_workplace_name(data.pop("workplace_id"))
            internal_audit_service.update_audit(audit_id, workplace=workplace, **data)
            self.refresh()

    def delete_selected_audit(self):
        audit_id = self._selected_audit_id()
        if audit_id is None:
            QMessageBox.information(self, "Audity", "Vyberte audit.")
            return

        audit = internal_audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, "Audity", "Audit nebyl nalezen.")
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
            internal_audit_service.delete_audit(audit_id)
            self.refresh()
