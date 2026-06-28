from datetime import date

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card


class TaskTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "ID",
            "",
            "Opatření",
            "Termín",
            "Odpovídá",
            "Pracoviště",
            "Zdroj",
        ])

        self.setColumnHidden(0, True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setMinimumSectionSize(24)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def load_tasks(self, tasks):
        self.setRowCount(len(tasks))

        today = date.today()

        for row, task in enumerate(tasks):
            row_state = self._row_state(task, today)
            tooltip = self._task_tooltip(task, row_state)

            values = [
                str(task.id),
                "",
                task.title or "—",
                "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y"),
                task.responsible_person or "—",
                task.workplace_name or "—",
                self._source_display(task.source_module),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column == 1:
                    item.setBackground(QBrush(self._priority_color(task.priority)))
                    item.setToolTip(f"Priorita: {task.priority or '—'}\n\n{tooltip}")
                else:
                    item.setBackground(QBrush(self._row_color(row_state)))
                    item.setToolTip(tooltip)

                self.setItem(row, column, item)

    def _task_tooltip(self, task, row_state: str) -> str:
        due_date = "—" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
        completed_date = "—" if task.completed_date is None else task.completed_date.strftime("%d.%m.%Y")
        check_due_date = "—" if task.check_due_date is None else task.check_due_date.strftime("%d.%m.%Y")
        checked_date = "—" if task.checked_date is None else task.checked_date.strftime("%d.%m.%Y")

        rows = [
            ("Priorita:", task.priority or "—"),
            ("Odpovídá:", task.responsible_person or "—"),
            ("Pracoviště:", task.workplace_name or "—"),
            ("Termín:", due_date),
            ("Stav:", self._row_tooltip(row_state)),
            ("Splněno dne:", completed_date),
            ("Kontrola do:", check_due_date),
            ("Datum kontroly:", checked_date),
            ("Kontroloval:", task.checked_by_name or "—"),
            ("Zdroj:", self._source_display(task.source_module)),
        ]

        return format_info_card(
            title=f"Opatření:\n{task.title or '—'}",
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

    def _source_display(self, source: str) -> str:
        mapping = {
            "manual": "Ručně",
            "uraz": "Kniha úrazů",
            "kniha_urazu": "Kniha úrazů",
            "audit": "Audit",
            "proverka": "Prověrka",
            "kontrola": "Kontrola",
        }
        return mapping.get(source or "", source or "—")

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
