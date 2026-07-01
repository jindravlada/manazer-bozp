import json
from datetime import date

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem
from sqlalchemy import select

from core.database.session import get_session
from core.theme.status_colors import STATUS_DONE_BG, STATUS_MISSING_BG, STATUS_WARNING_BG
from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    collect_obligation_rows_from_saved_data,
    obligations_summary_state,
)
from moduly.ukoly.sluzby.task_service import task_service

_OPATRENI_SOURCE = "kniha_urazu_opatreni"
_INJURY_COLOR_FATAL = "#222222"
_INJURY_COLOR_SERIOUS = "#d32f2f"
_INJURY_COLOR_OVER_3_DAYS = "#ff9800"
_INJURY_COLOR_UP_TO_3_DAYS = "#2e7d32"
_INJURY_COLOR_DEFAULT = "#e0e0e0"


class AccidentTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(10)
        self.setHorizontalHeaderLabels([
            "",
            "ID",
            "Číslo",
            "Datum úrazu",
            "Zraněný",
            "Pracovní pozice",
            "Vedoucí zaměstnanec",
            "Pracoviště",
            "Místo úrazu",
            "ZoÚ",
        ])

        self.setColumnHidden(1, True)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def configure_columns(self):
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        for column, width in {
            0: 22,
            2: 90,
            3: 110,
            9: 35,
        }.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(column, width)
        for column in (4, 5, 6, 7, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

    def load_accidents(self, accidents):
        accident_ids = [accident.id for accident in accidents]
        investigations_by_accident = self._load_investigations(accident_ids)
        today = date.today()

        self.setRowCount(len(accidents))

        for row, accident in enumerate(accidents):
            investigation = investigations_by_accident.get(accident.id)
            obligation_rows = self._obligation_rows(investigation)
            zou_color = self._zou_color(accident, obligation_rows, today)

            values = [
                "",
                str(accident.id),
                accident.number or "—",
                "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y"),
                accident.employee_name or "—",
                accident.druh_vykonavane_prace or "—",
                accident.zapsal_jmeno or "—",
                accident.workplace_name or accident.pracoviste or "—",
                accident.misto_urazu or "—",
                "",
            ]

            tooltip = self._tooltip(accident)

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)

                if column == 0:
                    item.setBackground(self._injury_type_color(accident.druh_urazu or ""))
                elif column == 9 and zou_color is not None:
                    item.setBackground(zou_color)

                self.setItem(row, column, item)

    def compute_summary(self, accidents):
        today = date.today()
        accident_ids = [accident.id for accident in accidents]
        investigations_by_accident = self._load_investigations(accident_ids)
        tasks_by_accident = self._load_opatreni_tasks(accident_ids)

        zou_overdue = 0
        zou_waiting = 0
        zou_done = 0
        op_incomplete = 0

        for accident in accidents:
            investigation = investigations_by_accident.get(accident.id)
            obligation_rows = self._obligation_rows(investigation)
            zou_state = self._zou_summary_state(accident, obligation_rows, today)
            if zou_state == "done":
                zou_done += 1
            elif zou_state == "overdue":
                zou_overdue += 1
            elif zou_state == "waiting":
                zou_waiting += 1

            if self._has_incomplete_opatreni(tasks_by_accident.get(accident.id, [])):
                op_incomplete += 1

        return {
            "zou_overdue": zou_overdue,
            "zou_waiting": zou_waiting,
            "zou_done": zou_done,
            "op_incomplete": op_incomplete,
            # TODO: doplnit logiku dokončeného šetření
            "setreni_incomplete": 0,
        }

    def _load_investigations(self, accident_ids):
        if not accident_ids:
            return {}
        with get_session() as session:
            stmt = select(AccidentInvestigation).where(AccidentInvestigation.accident_id.in_(accident_ids))
            return {inv.accident_id: inv for inv in session.scalars(stmt).all()}

    def _load_opatreni_tasks(self, accident_ids):
        accident_id_set = set(accident_ids)
        tasks_by_accident = {}
        for task in task_service.get_all_tasks():
            if (
                task.source_module == _OPATRENI_SOURCE
                and task.source_record_id in accident_id_set
                and not task.canceled
            ):
                tasks_by_accident.setdefault(task.source_record_id, []).append(task)
        return tasks_by_accident

    def _obligation_rows(self, investigation):
        if investigation is None or not investigation.zajisteni_dukazu_json:
            return []
        try:
            data = json.loads(investigation.zajisteni_dukazu_json or "{}")
        except Exception:
            return []
        return collect_obligation_rows_from_saved_data(data)

    def _zou_summary_state(self, accident, obligation_rows, today):
        return obligations_summary_state(accident, obligation_rows, today)

    def _has_incomplete_opatreni(self, tasks):
        if not tasks:
            return False
        return any(task.computed_status != "Ukončeno" for task in tasks)

    def _zou_color(self, accident, obligation_rows, today):
        state = obligations_summary_state(accident, obligation_rows, today)
        if state is None:
            return None
        if state == "done":
            return QColor(STATUS_DONE_BG)
        if state == "overdue":
            return QColor(STATUS_MISSING_BG)
        return QColor(STATUS_WARNING_BG)

    def _op_color(self, tasks):
        if not tasks:
            return QColor(_INJURY_COLOR_UP_TO_3_DAYS)
        if all(task.computed_status == "Ukončeno" for task in tasks):
            return QColor(_INJURY_COLOR_UP_TO_3_DAYS)
        return QColor(_INJURY_COLOR_SERIOUS)

    def _injury_type_color(self, druh_urazu: str) -> QColor:
        text = (druh_urazu or "").lower()

        if "smrteln" in text:
            return QColor(_INJURY_COLOR_FATAL)
        if "závaž" in text or "zavaz" in text:
            return QColor(_INJURY_COLOR_SERIOUS)
        if "delší než 3" in text or "delsi nez 3" in text:
            return QColor(_INJURY_COLOR_OVER_3_DAYS)
        if "nepřesahující 3" in text or "nepresahujici 3" in text:
            return QColor(_INJURY_COLOR_UP_TO_3_DAYS)

        return QColor(_INJURY_COLOR_DEFAULT)

    def _tooltip(self, accident):
        datum = "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y")
        return (
            f"Pracovní úraz {accident.number or '—'}\n"
            f"Datum: {datum} {accident.accident_time or ''}\n"
            f"Zaměstnanec: {accident.employee_name or '—'}\n"
            f"Pracoviště: {accident.workplace_name or accident.pracoviste or '—'}\n"
            f"Druh úrazu: {accident.druh_urazu or '—'}\n\n"
            f"{accident.popis_urazoveho_deje or ''}"
        )
