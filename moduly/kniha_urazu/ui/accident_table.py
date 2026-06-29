import json
from datetime import date

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem
from sqlalchemy import select

from core.database.session import get_session
from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
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

        self.setColumnCount(11)
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
            "Op.",
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
            10: 35,
        }.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(column, width)
        for column in (4, 5, 6, 7, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

    def load_accidents(self, accidents):
        accident_ids = [accident.id for accident in accidents]
        investigations_by_accident = self._load_investigations(accident_ids)
        tasks_by_accident = self._load_opatreni_tasks(accident_ids)

        self.setRowCount(len(accidents))

        for row, accident in enumerate(accidents):
            investigation = investigations_by_accident.get(accident.id)
            admin_zaslani = self._admin_zaslani_rows(investigation)
            zou_color = self._zou_color(accident, admin_zaslani)
            op_color = self._op_color(tasks_by_accident.get(accident.id, []))

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
                elif column == 10:
                    item.setBackground(op_color)

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
            admin_zaslani = self._admin_zaslani_rows(investigation)
            zou_state = self._zou_summary_state(accident, admin_zaslani, today)
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

    def _admin_zaslani_rows(self, investigation):
        if investigation is None or not investigation.zajisteni_dukazu_json:
            return []
        try:
            data = json.loads(investigation.zajisteni_dukazu_json or "{}")
        except Exception:
            return []
        return data.get("admin_zaslani") or []

    def _accident_kind_text(self, accident):
        return (getattr(accident, "druh_urazu", "") or "").lower()

    def _is_serious_or_fatal_accident(self, accident):
        text = self._accident_kind_text(accident)
        return "závaž" in text or "zavaz" in text or "smrt" in text

    def _is_fatal_accident(self, accident):
        return "smrt" in self._accident_kind_text(accident)

    def _has_work_incapacity(self, accident):
        for attr in ["dpn_od", "pracovni_neschopnost_od", "doba_pracovni_neschopnosti_od", "absence_from", "pn_od"]:
            if getattr(accident, attr, None):
                return True
        text = self._accident_kind_text(accident)
        return "neschop" in text or "závaž" in text or "zavaz" in text or "smrt" in text

    def _requires_accident_record(self, accident):
        return self._has_work_incapacity(accident) or self._is_serious_or_fatal_accident(accident)

    def _admin_zaslani_row_relevant(self, accident, row):
        name = row.get("nazev", "")
        if not self._requires_accident_record(accident):
            return False
        if "OIP / OBÚ" in name or "Oblastní inspektorát práce" in name or "Obvodní báňský úřad" in name:
            return self._is_serious_or_fatal_accident(accident)
        if "Policie ČR" in name:
            return self._is_fatal_accident(accident)
        if "Zdravotní pojišťovna" in name:
            return self._has_work_incapacity(accident) or self._is_serious_or_fatal_accident(accident)
        return True

    def _admin_row_done(self, row):
        if row.get("predano"):
            return True
        if row.get("kompletni"):
            return True
        if row.get("datum"):
            return True
        return False

    def _parse_json_date(self, value):
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None

    def _admin_row_overdue(self, row, today):
        if self._admin_row_done(row):
            return False
        deadline = self._parse_json_date(row.get("lhuta"))
        return deadline is not None and deadline < today

    def _zou_summary_state(self, accident, admin_zaslani, today):
        if not self._requires_accident_record(accident):
            return None
        relevant = [row for row in admin_zaslani if self._admin_zaslani_row_relevant(accident, row)]
        if not relevant:
            return "waiting"
        if all(self._admin_row_done(row) for row in relevant):
            return "done"
        if any(self._admin_row_overdue(row, today) for row in relevant):
            return "overdue"
        return "waiting"

    def _has_incomplete_opatreni(self, tasks):
        if not tasks:
            return False
        return any(task.computed_status != "Ukončeno" for task in tasks)

    def _zou_color(self, accident, admin_zaslani):
        if not self._requires_accident_record(accident):
            return None
        relevant = [row for row in admin_zaslani if self._admin_zaslani_row_relevant(accident, row)]
        if not relevant:
            return QColor(_INJURY_COLOR_SERIOUS)
        if all(self._admin_row_done(row) for row in relevant):
            return QColor(_INJURY_COLOR_UP_TO_3_DAYS)
        return QColor(_INJURY_COLOR_SERIOUS)

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
