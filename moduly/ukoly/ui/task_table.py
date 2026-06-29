from datetime import date

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.shared.constants import (
    ENTITY_ACCIDENT,
    ENTITY_AUDITY,
    ENTITY_FINDING,
    ENTITY_MU_INVESTIGATION,
    ENTITY_PROVERKY,
)
from core.shared.sluzby.finding_service import finding_service
from core.widgets.info_tooltip import format_info_card


class TaskTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "",
            "Opatření",
            "Termín",
            "Odpovídá",
            "Pracoviště",
            "Zdroj",
            "Zdrojový záznam",
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
                self._source_type_display(task),
                self._source_record_display(task),
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
            ("Zdroj:", self._source_type_display(task)),
            ("Zdrojový záznam:", self._source_record_display(task)),
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

    def _source_type_display(self, task) -> str:
        source_module = task.source_module or ""
        if source_module == ENTITY_FINDING and task.source_record_id:
            finding = finding_service.get_by_id(task.source_record_id)
            if finding is not None:
                return self._finding_entity_type_label(finding.entity_type)
            return "Zjištění"

        return self._legacy_source_type_label(source_module)

    def _source_record_display(self, task) -> str:
        source_module = task.source_module or ""
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

    def _finding_entity_type_label(self, entity_type: str) -> str:
        labels = {
            ENTITY_AUDITY: "Audit IMS",
            ENTITY_ACCIDENT: "Šetření úrazu",
            ENTITY_MU_INVESTIGATION: "Vyšetřování MU",
            ENTITY_PROVERKY: "Prověrka BOZP",
        }
        return labels.get(entity_type, entity_type or "—")

    def _legacy_source_type_label(self, source: str) -> str:
        mapping = {
            "manual": "Ručně",
            "uraz": "Kniha úrazů",
            "kniha_urazu": "Kniha úrazů",
            "kniha_urazu_opatreni": "Kniha úrazů",
            "audit": "Audit IMS",
            "audity": "Audit IMS",
            "proverka": "Prověrka BOZP",
            "proverky": "Prověrka BOZP",
            "kontrola": "Kontrola",
            ENTITY_FINDING: "Zjištění",
        }
        return mapping.get(source or "", source or "—")

    def _finding_source_record(self, finding) -> str:
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
        from moduly.audity.sluzby.internal_audit_service import internal_audit_service

        audit = internal_audit_service.get_by_id(entity_id)
        if audit is not None and audit.number:
            return f"Audit IMS {audit.number}"
        return "—"

    def _accident_record_label(self, entity_id: int) -> str:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(entity_id)
        if accident is not None and accident.number:
            return f"Úraz č. {accident.number}"
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
