"""Přehled externích auditů (EA-1)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_close_push_button, exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    typed_date,
    typed_text,
)
from moduly.externi_audity.constants import (
    EXTERNAL_AUDITS_OVERVIEW_TITLE,
    EXTERNAL_AUDIT_STATUS_FILTER_ALL,
    EXTERNAL_AUDIT_STATUS_LABELS,
    EXTERNAL_AUDIT_YEAR_FILTER_ALL,
    EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE,
    EXTERNAL_AUDIT_YEAR_SPIN_MAX,
    EXTERNAL_AUDIT_YEAR_SPIN_MIN,
    format_display_date,
)
from moduly.externi_audity.sluzby.external_audit_service import (
    ExternalAuditOverviewRow,
    external_audit_service,
)
from moduly.externi_audity.ui.external_audit_editor_dialog import (
    ExternalAuditEditorDialog,
)

COL_FROM = 0
COL_TO = 1
COL_TYPE = 2
COL_ORG = 3
COL_ICO = 4
COL_WP = 5
COL_STATUS = 6
COL_REMIND = 7
COL_NC = 8
COL_PKZ = 9
COL_STRENGTH = 10
COL_TASKS = 11


class ExternalAuditsOverviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(EXTERNAL_AUDITS_OVERVIEW_TITLE)
        self.resize(1280, 620)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový externí audit")
        self.edit_btn = QPushButton("Upravit")
        self.refresh_btn = QPushButton("Obnovit")
        self.status_filter = QComboBox()
        self.status_filter.addItem(EXTERNAL_AUDIT_STATUS_FILTER_ALL, None)
        for value, label in EXTERNAL_AUDIT_STATUS_LABELS.items():
            self.status_filter.addItem(label, value)

        self.year_filter = QSpinBox()
        self.year_filter.setRange(
            EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE, EXTERNAL_AUDIT_YEAR_SPIN_MAX
        )
        self.year_filter.setSpecialValueText(EXTERNAL_AUDIT_YEAR_FILTER_ALL)
        self.year_filter.setValue(date.today().year)
        self.year_all_hint = QLabel(
            f"{EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE} = {EXTERNAL_AUDIT_YEAR_FILTER_ALL}"
        )
        self.year_all_hint.setStyleSheet("color: gray;")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Rok:"))
        toolbar.addWidget(self.year_filter)
        toolbar.addWidget(self.year_all_hint)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels(
            [
                "Termín od",
                "Termín do",
                "Typ auditu",
                "Externí organizace",
                "IČ",
                "Provozy",
                "Stav",
                "Připomenout od",
                "Neshody O/V",
                "PKZ O/V",
                "Silné stránky",
                "Úkoly A/D/Z",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self._refresh_actions)
        enable_typed_sorting(self.table)
        header = self.table.horizontalHeader()
        header.setToolTip("")
        self.table.horizontalHeaderItem(COL_NC).setToolTip(
            "Neshody: otevřené / vypořádané (O/V)"
        )
        self.table.horizontalHeaderItem(COL_PKZ).setToolTip(
            "PKZ: otevřené / vypořádané (O/V)"
        )
        self.table.horizontalHeaderItem(COL_STRENGTH).setToolTip(
            "Počet silných stránek"
        )
        self.table.horizontalHeaderItem(COL_TASKS).setToolTip(
            "Úkoly: aktivní / dokončené / zrušené (A/D/Z). "
            "Aktivní zahrnuje i „Splněno – čeká na kontrolu“."
        )

        self.text_filter = FilterBar(self.table)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_btn = QPushButton()
        configure_close_push_button(self.close_btn)
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

        self.new_btn.clicked.connect(self.new_audit)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.refresh_btn.clicked.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.valueChanged.connect(self.refresh)

        self._rows: list[ExternalAuditOverviewRow] = []
        self.refresh()

    def selected_year(self) -> int | None:
        value = int(self.year_filter.value())
        if value <= EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE:
            return None
        return value

    def refresh(self) -> None:
        self._rows = self._filtered_rows(external_audit_service.list_overview_rows())
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            cells = [
                create_typed_item(
                    format_display_date(row.date_from)
                    if row.date_from is not None
                    else "—",
                    typed_date(row.date_from),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    format_display_date(row.date_to)
                    if row.date_to is not None
                    else "",
                    typed_date(row.date_to),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    row.audit_type_label,
                    typed_text(row.audit_type_label),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    row.organization_name,
                    typed_text(row.organization_name),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    row.organization_ico,
                    typed_text(row.organization_ico),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    row.workplaces_label,
                    typed_text(row.workplaces_label),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    row.status_label,
                    typed_text(row.status_label),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    format_display_date(row.remind_from)
                    if row.remind_from is not None
                    else "",
                    typed_date(row.remind_from),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    f"{row.nonconformity_open}/{row.nonconformity_resolved}",
                    typed_text(
                        f"{row.nonconformity_open:05d}/{row.nonconformity_resolved:05d}"
                    ),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    f"{row.improvement_open}/{row.improvement_resolved}",
                    typed_text(
                        f"{row.improvement_open:05d}/{row.improvement_resolved:05d}"
                    ),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    str(row.strength_count),
                    typed_text(f"{row.strength_count:05d}"),
                    stable_id=row.audit_id,
                ),
                create_typed_item(
                    f"{row.tasks_active}/{row.tasks_done}/{row.tasks_canceled}",
                    typed_text(
                        f"{row.tasks_active:05d}/{row.tasks_done:05d}/{row.tasks_canceled:05d}"
                    ),
                    stable_id=row.audit_id,
                ),
            ]
            cells[COL_NC].setToolTip("Neshody: otevřené / vypořádané")
            cells[COL_PKZ].setToolTip("PKZ: otevřené / vypořádané")
            cells[COL_STRENGTH].setToolTip("Počet silných stránek")
            cells[COL_TASKS].setToolTip(
                "Úkoly: aktivní / dokončené / zrušené"
            )
            for col, item in enumerate(cells):
                if col == COL_ORG:
                    item.setData(Qt.ItemDataRole.UserRole, row.audit_id)
                self.table.setItem(index, col, item)
        self.table.resizeColumnsToContents()
        self.text_filter.apply_filter()
        self._refresh_actions()

    def _filtered_rows(
        self, rows: list[ExternalAuditOverviewRow]
    ) -> list[ExternalAuditOverviewRow]:
        status = self.status_filter.currentData()
        year = self.selected_year()
        result: list[ExternalAuditOverviewRow] = []
        for row in rows:
            if status is not None and row.status != status:
                continue
            if year is None:
                result.append(row)
                continue
            if row.date_from is None:
                # Bez programu zůstávají viditelné jen při „Vše“.
                continue
            if row.date_from.year == year:
                result.append(row)
        return result

    def _selected_audit_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), COL_ORG)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _refresh_actions(self) -> None:
        self.edit_btn.setEnabled(self._selected_audit_id() is not None)

    def new_audit(self) -> None:
        dialog = ExternalAuditEditorDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def edit_selected(self) -> None:
        audit_id = self._selected_audit_id()
        if audit_id is None:
            return
        dialog = ExternalAuditEditorDialog(self, audit_id=audit_id)
        exec_maximized(dialog)
        self.refresh()
