from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_close_box, exec_maximized
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.proverky.constants import (
    INSPECTION_SPIS_STATUSES,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

_ROLE_INSPECTION_ID = Qt.ItemDataRole.UserRole


def _status_sort(status: str):
    try:
        order = INSPECTION_SPIS_STATUSES.index(status)
    except ValueError:
        order = len(INSPECTION_SPIS_STATUSES)
    return typed_status(order, label=status or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


def _month_sort_value(inspection):
    if inspection.planned_month is not None and 1 <= inspection.planned_month <= 12:
        return typed_int(inspection.planned_month)
    if inspection.inspection_date is not None:
        return typed_int(inspection.inspection_date.month)
    return typed_empty()


class RocniPlanDialog(QDialog):
    """Přehled prověrek BOZP za vybraný rok (Plán kontrol)."""

    _TABLE_COLUMNS = (
        "Měsíc",
        "Pracoviště",
        "Datum prověrky",
        "Stav",
        "Typ prověrky",
    )

    def __init__(self, parent=None, *, year: int | None = None):
        super().__init__(parent)

        self._year = year or date.today().year

        self.setWindowTitle("Roční plán prověrek BOZP")
        self.resize(860, 520)

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Rok:"))
        self.year_combo = QComboBox()
        header_row.addWidget(self.year_combo)
        header_row.addStretch()
        self.summary_label = QLabel()
        self.summary_label.setObjectName("InfoText")
        header_row.addWidget(self.summary_label)
        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self._TABLE_COLUMNS))
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        enable_typed_sorting(self.table)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.open_btn = QPushButton("Otevřít")
        self.open_btn.clicked.connect(self.open_selected_inspection)
        actions.addWidget(self.open_btn)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.table.doubleClicked.connect(self._on_row_double_clicked)

        self._populate_year_combo()
        self.year_combo.setCurrentText(str(self._year))
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        self._load_year(self._year)

    def _populate_year_combo(self) -> None:
        years = {date.today().year, self._year}
        for inspection in bozp_inspection_service.get_all():
            if inspection.year is not None:
                years.add(inspection.year)
            if inspection.inspection_date is not None:
                years.add(inspection.inspection_date.year)

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for year in sorted(years, reverse=True):
            self.year_combo.addItem(str(year), year)
        self.year_combo.blockSignals(False)

    def _on_year_changed(self) -> None:
        year = self.year_combo.currentData()
        if isinstance(year, int):
            self._load_year(year)

    def _load_year(self, year: int) -> None:
        self._year = year
        inspections = bozp_inspection_service.get_for_year(year)

        with sorting_paused(self.table):
            self.table.setRowCount(len(inspections))

            for row, inspection in enumerate(inspections):
                record_id = int(inspection.id)
                workplace = inspection.workplace_name or "—"
                status = inspection.status or ""
                inspection_type = inspection.inspection_type or "—"
                values = [
                    (self._format_month(inspection), _month_sort_value(inspection)),
                    (workplace, _text_or_empty(workplace)),
                    (
                        self._format_date(inspection.inspection_date),
                        typed_date(inspection.inspection_date),
                    ),
                    (
                        status or "—",
                        _status_sort(status) if status else typed_empty(),
                    ),
                    (inspection_type, _text_or_empty(inspection_type)),
                ]
                for column, (display_text, sort_value) in enumerate(values):
                    item = create_typed_item(display_text, sort_value, stable_id=record_id)
                    if column == 0:
                        item.setData(_ROLE_INSPECTION_ID, inspection.id)
                    if column == 1:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row, column, item)

        count = len(inspections)
        if count == 0:
            self.summary_label.setText(f"Pro rok {year} nejsou evidovány žádné prověrky.")
        elif count == 1:
            self.summary_label.setText(f"Pro rok {year} je evidována 1 prověrka.")
        else:
            self.summary_label.setText(f"Pro rok {year} jsou evidovány {count} prověrky.")

    def _selected_inspection_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return self._inspection_id_at_row(selected[0].row())

    def _inspection_id_at_row(self, row: int) -> int | None:
        if row < 0 or row >= self.table.rowCount():
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(_ROLE_INSPECTION_ID)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _on_row_double_clicked(self, index) -> None:
        """Dvojklik: vybere řádek a otevře stejnou cestou jako tlačítko Otevřít."""
        if index is None or not index.isValid():
            return
        row = index.row()
        if self._inspection_id_at_row(row) is None:
            return
        self.table.selectRow(row)
        self.open_selected_inspection()

    def open_selected_inspection(self) -> None:
        """Sdílená akce pro tlačítko Otevřít i dvojklik."""
        inspection_id = self._selected_inspection_id()
        if inspection_id is None:
            # Jen při volání z tlačítka (dvojklik bez ID sem nedojde).
            if self.sender() is self.open_btn:
                QMessageBox.information(self, self.windowTitle(), "Vyberte prověrku.")
            return
        self.open_inspection(inspection_id)

    def open_inspection(self, inspection_id: int) -> None:
        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, self.windowTitle(), "Prověrka nebyla nalezena.")
            self._load_year(self._year)
            return

        dialog = BozpInspectionDialog(self, inspection=inspection)
        if exec_maximized(dialog):
            data = dialog.get_data()
            payload = self._prepare_spis_data(data)
            bozp_inspection_service.update_inspection(inspection_id, **payload)
            members = data.get("commission_members")
            if members is not None:
                bozp_inspection_commission_service.save_members(inspection_id, members)

        # Po zavření editoru vždy obnovit plán (termín, stav, pracoviště…).
        self._load_year(self._year)
        parent = self.parent()
        if parent is not None and hasattr(parent, "refresh"):
            parent.refresh()

    @staticmethod
    def _prepare_spis_data(data: dict) -> dict:
        payload = {key: value for key, value in data.items() if key != "commission_members"}
        workplace_id = payload.get("workplace_id")
        if workplace_id is None:
            workplace_id = bozp_inspection_service.resolve_workplace_id_by_name(
                payload.get("workplace_name", "")
            )
            payload["workplace_id"] = workplace_id
        payload["workplace_name"] = bozp_inspection_service.resolve_workplace_name(
            workplace_id
        )
        return payload

    @staticmethod
    def _format_month(inspection) -> str:
        if inspection.planned_month is not None and 1 <= inspection.planned_month <= 12:
            return PLANNED_MONTH_NAMES[inspection.planned_month - 1]
        if inspection.inspection_date is not None:
            return PLANNED_MONTH_NAMES[inspection.inspection_date.month - 1]
        return PLANNED_MONTH_NOT_SET_LABEL

    @staticmethod
    def _format_date(value) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y")
