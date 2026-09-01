from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QMouseEvent
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.shared.sluzby.finding_service import finding_service
from core.shared.task_source_display import task_source_short_label, task_source_short_labels
from core.widgets.info_tooltip import format_info_card
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_status,
    typed_text,
)
from moduly.ukoly.constants import TASK_TYPE_LABELS
from moduly.ukoly.task_display import (
    COL_DESCRIPTION,
    COL_DUE_DATE,
    COL_ID,
    COL_INDICATOR,
    COL_RESPONSIBLE,
    COL_SOURCE,
    COL_SOURCE_RECORD,
    COL_TYPE,
    COL_WORKPLACE,
    COLUMN_COUNT,
    task_description_table_text,
    task_type_key,
    task_type_table_label,
)

_TASK_STATUS_ORDER = (
    "Aktivní",
    "Splněno - čeká na kontrolu",
    "Ukončeno",
    "Zrušeno",
)
_TASK_TYPE_ORDER = tuple(TASK_TYPE_LABELS.keys())


def _order_status(value: str, order: tuple[str, ...]):
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class TaskTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels([
            "ID",
            "",
            "Popis",
            "Termín",
            "Odpovídá",
            "Pracoviště",
            "Zdroj",
            "Zdrojový záznam",
            "Typ",
        ])

        self.setColumnHidden(COL_ID, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_INDICATOR, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_DESCRIPTION, QHeaderView.Stretch)
        for column in (COL_DUE_DATE, COL_RESPONSIBLE, COL_WORKPLACE, COL_SOURCE, COL_SOURCE_RECORD, COL_TYPE):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.clearCurrentIndex()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        position = event.position().toPoint()
        if not self.indexAt(position).isValid():
            self.clear_selection()
            event.accept()
            return
        super().mousePressEvent(event)

    def load_tasks(self, tasks):
        today = date.today()
        source_labels = task_source_short_labels(tasks)

        with sorting_paused(self):
            self.setRowCount(len(tasks))

            for row, task in enumerate(tasks):
                record_id = int(task.id)
                row_state = self._row_state(task, today)
                source = source_labels.get(record_id, task_source_short_label(task))
                tooltip = self._task_tooltip(task, row_state, source=source)
                description = task_description_table_text(task)
                due_display = "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
                responsible = task.responsible_person or "—"
                workplace = task.workplace_name or "—"
                source_record = self._source_record_display(task)
                type_label = task_type_table_label(task)
                status = task.computed_status or ""
                priority = task.priority or ""

                cells = {
                    COL_ID: create_typed_item(
                        str(record_id),
                        typed_text(str(record_id)),
                        stable_id=record_id,
                    ),
                    COL_INDICATOR: create_typed_item(
                        "",
                        _order_status(status, _TASK_STATUS_ORDER) if status else typed_empty(),
                        stable_id=record_id,
                    ),
                    COL_DESCRIPTION: create_typed_item(
                        description,
                        typed_text(task.title or ""),
                        stable_id=record_id,
                    ),
                    COL_DUE_DATE: create_typed_item(
                        due_display,
                        typed_date(task.due_date) if task.due_date is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    COL_RESPONSIBLE: create_typed_item(
                        responsible,
                        _text_or_empty(responsible),
                        stable_id=record_id,
                    ),
                    COL_WORKPLACE: create_typed_item(
                        workplace,
                        _text_or_empty(workplace),
                        stable_id=record_id,
                    ),
                    COL_SOURCE: create_typed_item(
                        source,
                        _text_or_empty(source),
                        stable_id=record_id,
                    ),
                    COL_SOURCE_RECORD: create_typed_item(
                        source_record,
                        _text_or_empty(source_record),
                        stable_id=record_id,
                    ),
                    COL_TYPE: create_typed_item(
                        type_label,
                        _order_status(task_type_key(task), _TASK_TYPE_ORDER),
                        stable_id=record_id,
                    ),
                }

                for column, item in cells.items():
                    if column == COL_INDICATOR:
                        item.setBackground(QBrush(self._priority_color(priority)))
                        item.setToolTip(f"Priorita: {priority or '—'}\n\n{tooltip}")
                    else:
                        item.setBackground(QBrush(self._row_color(row_state)))
                        item.setToolTip(tooltip)

                    if column == COL_DESCRIPTION:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

                    self.setItem(row, column, item)

        self.resizeRowsToContents()

    def _task_tooltip(self, task, row_state: str, *, source: str | None = None) -> str:
        due_date = "—" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
        completed_date = "—" if task.completed_date is None else task.completed_date.strftime("%d.%m.%Y")
        check_due_date = "—" if task.check_due_date is None else task.check_due_date.strftime("%d.%m.%Y")
        checked_date = "—" if task.checked_date is None else task.checked_date.strftime("%d.%m.%Y")

        rows = [
            ("Typ:", task_type_table_label(task)),
            ("Priorita:", task.priority or "—"),
            ("Odpovídá:", task.responsible_person or "—"),
            ("Pracoviště:", task.workplace_name or "—"),
            ("Termín:", due_date),
            ("Stav:", self._row_tooltip(row_state)),
            ("Splněno dne:", completed_date),
            ("Kontrola do:", check_due_date),
            ("Datum kontroly:", checked_date),
            ("Kontroloval:", task.checked_by_name or "—"),
            ("Zdroj:", source if source is not None else task_source_short_label(task)),
            ("Zdrojový záznam:", self._source_record_display(task)),
        ]

        return format_info_card(
            title=f"Popis:\n{task.title or '—'}",
            rows=rows,
            note=task.note or "",
        )

    def _row_state(self, task, today: date) -> str:
        status = task.computed_status

        if status == "Zrušeno":
            return "canceled"

        if status == "Ukončeno":
            return "done"

        if task.due_date is not None and task.due_date < today:
            return "overdue"

        if status == "Splněno - čeká na kontrolu":
            return "waiting_check"

        return "active"

    def _row_color(self, row_state: str) -> QColor:
        colors = {
            "active": QColor("#ffffff"),
            "overdue": QColor("#ffe0e0"),
            "waiting_check": QColor("#fff2b3"),
            "done": QColor("#d9f2d9"),
            "canceled": QColor("#eeeeee"),
        }
        return colors.get(row_state, QColor("#ffffff"))

    def _row_tooltip(self, row_state: str) -> str:
        tooltips = {
            "active": "Aktivní",
            "overdue": "Po termínu",
            "waiting_check": "Splněno - čeká na kontrolu",
            "done": "Ukončeno",
            "canceled": "Zrušeno",
        }
        return tooltips.get(row_state, "")

    def _source_record_display(self, task) -> str:
        from core.shared.constants import ENTITY_FINDING, ENTITY_MU_INVESTIGATION

        source_module = task.source_module or ""
        if source_module == ENTITY_MU_INVESTIGATION and task.source_record_id:
            return self._mu_investigation_record_label(task.source_record_id)
        if source_module == ENTITY_FINDING and task.source_record_id:
            finding = finding_service.get_by_id(task.source_record_id)
            if finding is not None:
                return self._finding_source_record(finding)
            return "—"

        if source_module in ("kniha_urazu", "kniha_urazu_opatreni", "uraz") and task.source_record_id:
            return self._accident_record_label(task.source_record_id)
        if source_module in ("audity", "audit") and task.source_record_id:
            return self._audit_record_label(task.source_record_id)

        return "—"

    def _finding_source_record(self, finding) -> str:
        from core.shared.constants import ENTITY_ACCIDENT, ENTITY_AUDITY, ENTITY_MU_INVESTIGATION

        if finding.entity_type == ENTITY_AUDITY:
            label = self._audit_record_label(finding.entity_id)
            if label != "—":
                return label
        elif finding.entity_type == ENTITY_ACCIDENT:
            label = self._accident_record_label(finding.entity_id)
            if label != "—":
                return label
        elif finding.entity_type == ENTITY_MU_INVESTIGATION:
            label = self._mu_investigation_record_label(finding.entity_id)
            if label != "—":
                return label

        reference = (finding.reference_label or "").strip()
        if reference:
            return reference

        return "—"

    def _audit_record_label(self, entity_id: int) -> str:
        from moduly.audity.sluzby.audit_service import audit_service

        audit = audit_service.get_by_id(entity_id)
        if audit is not None and audit.number:
            return audit.number
        return "—"

    def _accident_record_label(self, entity_id: int) -> str:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(entity_id)
        if accident is not None and accident.number:
            return accident.number
        return "—"

    def _mu_investigation_record_label(self, entity_id: int) -> str:
        from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service

        investigation = mu_investigation_service.get_by_id(entity_id)
        if investigation is not None and investigation.number:
            return investigation.number
        return "—"

    def _priority_color(self, priority: str) -> QColor:
        if priority == "Kritická":
            return QColor("#e53935")
        if priority == "Vysoká":
            return QColor("#fb8c00")
        if priority == "Normální":
            return QColor("#fdd835")
        if priority == "Nízká":
            return QColor("#43a047")
        return QColor("#bdbdbd")
