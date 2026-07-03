from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QMouseEvent
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.shared.sluzby.finding_service import finding_service
from core.shared.task_source_display import task_source_short_label
from core.widgets.info_tooltip import format_info_card
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
    task_type_table_label,
)


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
        self.setRowCount(len(tasks))

        today = date.today()

        for row, task in enumerate(tasks):
            row_state = self._row_state(task, today)
            tooltip = self._task_tooltip(task, row_state)
            description = task_description_table_text(task)

            values = {
                COL_ID: str(task.id),
                COL_INDICATOR: "",
                COL_DESCRIPTION: description,
                COL_DUE_DATE: "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y"),
                COL_RESPONSIBLE: task.responsible_person or "—",
                COL_WORKPLACE: task.workplace_name or "—",
                COL_SOURCE: task_source_short_label(task),
                COL_SOURCE_RECORD: self._source_record_display(task),
                COL_TYPE: task_type_table_label(task),
            }

            for column, value in values.items():
                item = QTableWidgetItem(value)

                if column == COL_INDICATOR:
                    item.setBackground(QBrush(self._priority_color(task.priority)))
                    item.setToolTip(f"Priorita: {task.priority or '—'}\n\n{tooltip}")
                else:
                    item.setBackground(QBrush(self._row_color(row_state)))
                    item.setToolTip(tooltip)

                if column == COL_DESCRIPTION:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

                self.setItem(row, column, item)

        self.resizeRowsToContents()

    def _task_tooltip(self, task, row_state: str) -> str:
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
            ("Zdroj:", task_source_short_label(task)),
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
