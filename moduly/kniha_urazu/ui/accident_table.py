import json
from datetime import date, datetime, time

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget
from sqlalchemy import select

from core.database.session import get_session
from core.theme.status_colors import STATUS_DONE_BG, STATUS_MISSING_BG, STATUS_WARNING_BG
from core.widgets.info_tooltip import format_info_card
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_datetime,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    obligation_rows_for_summary,
    obligations_summary_state,
)
from moduly.ukoly.sluzby.task_service import task_service

_OPATRENI_SOURCE = "kniha_urazu_opatreni"
_INJURY_COLOR_FATAL = "#222222"
_INJURY_COLOR_SERIOUS = "#d32f2f"
_INJURY_COLOR_OVER_3_DAYS = "#ff9800"
_INJURY_COLOR_UP_TO_3_DAYS = "#2e7d32"
_INJURY_COLOR_DEFAULT = "#e0e0e0"

_ZOU_STATE_ORDER = ("overdue", "waiting", "done")
_INJURY_SEVERITY_ORDER = ("fatal", "serious", "over_3_days", "up_to_3_days", "other")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


def _order_status(value: str, order: tuple[str, ...], *, label: str = ""):
    try:
        return typed_status(order.index(value), label=label or value or "")
    except ValueError:
        return typed_status(len(order), label=label or value or "")


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
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        enable_typed_sorting(self)

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

        with sorting_paused(self):
            self.setRowCount(len(accidents))

            for row, accident in enumerate(accidents):
                record_id = int(accident.id)
                investigation = investigations_by_accident.get(accident.id)
                saved_data = self._investigation_saved_data(investigation)
                obligation_rows = obligation_rows_for_summary(accident, saved_data)
                zou_state = self._zou_summary_state(accident, obligation_rows, today)
                zou_color = self._zou_color(accident, obligation_rows, today)
                injury_key = self._injury_severity_key(accident.druh_urazu or "")
                number = accident.number or "—"
                date_display = (
                    "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y")
                )
                employee = accident.employee_name or "—"
                position = accident.druh_vykonavane_prace or "—"
                supervisor = accident.zapsal_jmeno or "—"
                workplace = accident.workplace_name or accident.pracoviste or "—"
                place = accident.misto_urazu or "—"
                tooltip = self._tooltip(accident)

                cells = [
                    create_typed_item(
                        "",
                        _order_status(injury_key, _INJURY_SEVERITY_ORDER, label=accident.druh_urazu or ""),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        number,
                        self._accident_number_sort(accident),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        date_display,
                        self._accident_moment_sort(accident),
                        stable_id=record_id,
                    ),
                    create_typed_item(employee, _text_or_empty(employee), stable_id=record_id),
                    create_typed_item(position, _text_or_empty(position), stable_id=record_id),
                    create_typed_item(supervisor, _text_or_empty(supervisor), stable_id=record_id),
                    create_typed_item(workplace, _text_or_empty(workplace), stable_id=record_id),
                    create_typed_item(place, _text_or_empty(place), stable_id=record_id),
                    create_typed_item(
                        "",
                        (
                            _order_status(zou_state, _ZOU_STATE_ORDER, label=zou_state)
                            if zou_state
                            else typed_empty()
                        ),
                        stable_id=record_id,
                    ),
                ]

                for column, item in enumerate(cells):
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
            saved_data = self._investigation_saved_data(investigation)
            obligation_rows = obligation_rows_for_summary(accident, saved_data)
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

    def _investigation_saved_data(self, investigation):
        if investigation is None or not investigation.zajisteni_dukazu_json:
            return {}
        try:
            data = json.loads(investigation.zajisteni_dukazu_json or "{}")
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _obligation_rows(self, investigation, accident):
        return obligation_rows_for_summary(
            accident,
            self._investigation_saved_data(investigation),
        )

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

    def _injury_severity_key(self, druh_urazu: str) -> str:
        text = (druh_urazu or "").lower()
        if "smrteln" in text:
            return "fatal"
        if "závaž" in text or "zavaz" in text:
            return "serious"
        if "delší než 3" in text or "delsi nez 3" in text:
            return "over_3_days"
        if "nepřesahující 3" in text or "nepresahujici 3" in text:
            return "up_to_3_days"
        return "other"

    def _injury_type_color(self, druh_urazu: str) -> QColor:
        key = self._injury_severity_key(druh_urazu)
        colors = {
            "fatal": QColor(_INJURY_COLOR_FATAL),
            "serious": QColor(_INJURY_COLOR_SERIOUS),
            "over_3_days": QColor(_INJURY_COLOR_OVER_3_DAYS),
            "up_to_3_days": QColor(_INJURY_COLOR_UP_TO_3_DAYS),
        }
        return colors.get(key, QColor(_INJURY_COLOR_DEFAULT))

    @staticmethod
    def _accident_number_sort(accident):
        year = getattr(accident, "year", None)
        record_id = getattr(accident, "id", None)
        if year is not None and record_id is not None:
            return typed_int(int(year) * 1_000_000 + int(record_id))

        number = (getattr(accident, "number", None) or "").strip()
        if "/" in number:
            try:
                seq_text, year_text = number.split("/", 1)
                return typed_int(int(year_text) * 1_000_000 + int(seq_text))
            except ValueError:
                pass
        return typed_text(number) if number else typed_empty()

    @staticmethod
    def _accident_moment_sort(accident):
        accident_date = getattr(accident, "accident_date", None)
        if accident_date is None:
            return typed_empty()

        raw_time = (getattr(accident, "accident_time", None) or "").strip()
        if not raw_time:
            return typed_date(accident_date)

        try:
            parts = raw_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return typed_datetime(datetime.combine(accident_date, time(hour=hour, minute=minute)))
        except (TypeError, ValueError):
            return typed_date(accident_date)

    def _tooltip(self, accident):
        datum = "" if accident.accident_date is None else accident.accident_date.strftime("%d.%m.%Y")
        rows = [
            ("Číslo:", accident.number or "—"),
            ("Datum:", f"{datum} {accident.accident_time or ''}".strip()),
            ("Zaměstnanec:", accident.employee_name or "—"),
            ("Pracoviště:", accident.workplace_name or accident.pracoviste or "—"),
            ("Druh úrazu:", accident.druh_urazu or "—"),
        ]
        return format_info_card(
            title="Pracovní úraz",
            rows=rows,
            note=accident.popis_urazoveho_deje or "",
        )
