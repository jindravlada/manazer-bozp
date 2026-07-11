from dataclasses import dataclass
from datetime import date, datetime, timedelta

from moduly.kniha_urazu.modely.accident import Accident
from moduly.kniha_urazu.repository.accident_repository import AccidentRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


@dataclass(frozen=True)
class AccidentDashboardSummary:
    has_accidents: bool
    total_this_year: int = 0
    last_30_days: int = 0
    days_without_accident: int = 0


class AccidentService:
    def __init__(self):
        self.repository = AccidentRepository()

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, accident_id: int):
        return self.repository.get_by_id(accident_id)

    def get_last_accident_date(self) -> date | None:
        dates = [
            accident.accident_date
            for accident in self.get_all()
            if accident.accident_date is not None
        ]
        return max(dates) if dates else None

    def get_dashboard_summary(self) -> AccidentDashboardSummary:
        today = date.today()
        year_start = date(today.year, 1, 1)
        threshold_30_days = today - timedelta(days=30)

        accident_dates = [
            accident.accident_date
            for accident in self.get_all()
            if accident.accident_date is not None
        ]

        if not accident_dates:
            return AccidentDashboardSummary(has_accidents=False)

        last_date = max(accident_dates)
        return AccidentDashboardSummary(
            has_accidents=True,
            total_this_year=sum(1 for accident_date in accident_dates if accident_date >= year_start),
            last_30_days=sum(1 for accident_date in accident_dates if accident_date >= threshold_30_days),
            days_without_accident=(today - last_date).days,
        )

    def create_accident(self, **data):
        self._enrich_workplace(data)
        self._sync_legacy_fields(data)

        accident = Accident(**data)

        if accident.datum_zapisu is None:
            accident.datum_zapisu = accident.accident_date

        if accident.investigation_started_at is None:
            accident.investigation_started_at = datetime.now()

        saved = self.repository.add(accident)
        saved.number = self._make_number(saved.id, saved.year)
        return self.repository.update(saved)

    def update_accident(self, accident_id: int, **data):
        accident = self.repository.get_by_id(accident_id)
        if accident is None:
            return None

        self._enrich_workplace(data)
        self._sync_legacy_fields(data)

        for key, value in data.items():
            if hasattr(accident, key):
                setattr(accident, key, value)

        return self.repository.update(accident)

    def _sync_legacy_fields(self, data: dict) -> None:
        """
        Vyplní starší sloupce, které v testovací DB vznikly jako NOT NULL.
        """
        full_name = (data.get("jmeno_prijmeni") or "").strip()
        parts = full_name.split()

        if len(parts) >= 2:
            first_name = " ".join(parts[:-1])
            last_name = parts[-1]
        else:
            first_name = ""
            last_name = full_name

        data.setdefault("employee_first_name", first_name)
        data.setdefault("employee_last_name", last_name)
        data.setdefault("employee_personal_number", data.get("osobni_cislo") or "")
        data.setdefault("injury_type", data.get("druh_zraneni") or "")
        data.setdefault("injured_body_part", data.get("zranena_cast_tela") or "")
        data.setdefault("description", data.get("popis_urazoveho_deje") or "")
        data.setdefault("measures_summary", data.get("opatreni") or "")

    def _enrich_workplace(self, data: dict):
        workplace_id = data.get("workplace_id")
        incoming_name = (
            str(data.get("workplace_name") or data.get("pracoviste") or "").strip()
        )

        if workplace_id:
            workplace = settings_service.get_workplace_by_id(workplace_id)
            workplace_name = workplace.name if workplace else incoming_name
            data["workplace_id"] = workplace_id
            data["workplace_name"] = workplace_name
            if workplace_name and not str(data.get("pracoviste") or "").strip():
                data["pracoviste"] = workplace_name
            return

        # Vlastní text mimo číselník – uložit jen na úraz, nepřidávat do nastavení.
        data["workplace_id"] = None
        data["workplace_name"] = incoming_name
        if incoming_name and not str(data.get("pracoviste") or "").strip():
            data["pracoviste"] = incoming_name

    def _make_number(self, accident_id: int, year: int) -> str:
        return f"{accident_id}/{year}"


accident_service = AccidentService()
