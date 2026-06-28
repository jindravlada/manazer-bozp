from datetime import datetime

from moduly.kniha_urazu.modely.accident import Accident
from moduly.kniha_urazu.repository.accident_repository import AccidentRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


class AccidentService:
    def __init__(self):
        self.repository = AccidentRepository()

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, accident_id: int):
        return self.repository.get_by_id(accident_id)

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
        workplace_name = ""

        if workplace_id:
            workplace = settings_service.get_workplace_by_id(workplace_id)
            workplace_name = workplace.name if workplace else ""

        data["workplace_name"] = workplace_name

        if workplace_name and not data.get("pracoviste"):
            data["pracoviste"] = workplace_name

    def _make_number(self, accident_id: int, year: int) -> str:
        return f"{accident_id}/{year}"


accident_service = AccidentService()
