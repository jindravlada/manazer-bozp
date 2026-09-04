from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json

from core.shared.constants import ENTITY_ACCIDENT
from moduly.kniha_urazu.modely.accident import Accident
from moduly.kniha_urazu.repository.accident_repository import AccidentRepository
from moduly.kniha_urazu.sluzby.accident_dpn_care import (
    apply_dpn_care_return_to_saved_data,
)
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    apply_dpn_record_update_to_saved_data,
    has_pn,
    is_dpn_over_3_kind,
    is_dpn_up_to_3_kind,
    is_fatal_accident,
    is_serious_accident,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX = "Ověřit druh pracovního úrazu"
# Úkol vytvářet jen při zápisu do 3 kalendářních dnů od data úrazu (zpoždění 0–3).
VERIFY_KIND_TASK_MAX_RECORDING_DELAY_DAYS = 3


def verify_accident_kind_task_title(number: str) -> str:
    return f"{VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX} č. {number}"


def is_verify_accident_kind_task_title(title: str) -> bool:
    text = (title or "").strip()
    return text == VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX or text.startswith(
        f"{VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX} č."
    )


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
        dpn_record_update = data.pop("dpn_record_update", None)
        dpn_care_return = data.pop("dpn_care_return", None)
        self._enrich_workplace(data)
        self._sync_legacy_fields(data)

        accident = Accident(**data)

        if accident.datum_zapisu is None:
            accident.datum_zapisu = accident.accident_date

        if accident.investigation_started_at is None:
            accident.investigation_started_at = datetime.now()

        saved = self.repository.add(accident)
        saved.number = self._make_number(saved.id, saved.year)
        saved = self.repository.update(saved)
        self._create_verify_kind_task(saved)
        self._stamp_combined_record_duty_generation(saved)
        self._sync_dpn_investigation_json(saved, dpn_record_update, dpn_care_return)
        self._sync_reporting_tasks(saved)
        return saved

    def update_accident(self, accident_id: int, **data):
        accident = self.repository.get_by_id(accident_id)
        if accident is None:
            return None

        dpn_record_update = data.pop("dpn_record_update", None)
        dpn_care_return = data.pop("dpn_care_return", None)
        self._enrich_workplace(data)
        self._sync_legacy_fields(data)

        for key, value in data.items():
            if hasattr(accident, key):
                setattr(accident, key, value)

        saved = self.repository.update(accident)
        self._resolve_verify_kind_task_if_needed(saved)
        self._sync_dpn_investigation_json(saved, dpn_record_update, dpn_care_return)
        self._sync_reporting_tasks(saved)
        return saved

    def _sync_reporting_tasks(self, accident: Accident) -> None:
        from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
            accident_reporting_task_service,
        )

        accident_reporting_task_service.sync_for_accident(accident)

    def _load_investigation_saved_data(self, accident_id: int) -> dict:
        from moduly.kniha_urazu.sluzby.investigation_service import investigation_service

        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _sync_dpn_investigation_json(
        self,
        accident: Accident,
        dpn_record_update=None,
        dpn_care_return=None,
    ) -> None:
        from moduly.kniha_urazu.sluzby.investigation_service import investigation_service

        if accident is None or getattr(accident, "id", None) is None:
            return
        current = self._load_investigation_saved_data(accident.id)
        updated = apply_dpn_record_update_to_saved_data(
            current,
            accident=accident,
            ui_state=dpn_record_update,
        )
        updated = apply_dpn_care_return_to_saved_data(
            updated,
            accident=accident,
            ui_state=dpn_care_return,
        )
        if updated == current:
            return
        investigation_service.save_zajisteni_dukazu(
            accident.id,
            json.dumps(updated, ensure_ascii=False),
        )

    def _stamp_combined_record_duty_generation(self, accident: Accident) -> None:
        """Označí nový úraz společnou povinností záznamu. Existující JSON nemění."""
        import json

        from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
            LEGACY_RECORD_DUTY_KEYS,
            RECORD_DUTY_GENERATION_COMBINED,
            RECORD_DUTY_GENERATION_KEY,
            collect_obligation_rows_from_saved_data,
            obligation_key_from_row,
        )
        from moduly.kniha_urazu.sluzby.investigation_service import investigation_service

        if accident is None or getattr(accident, "id", None) is None:
            return

        investigation = investigation_service.get_or_create(accident.id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if str(data.get(RECORD_DUTY_GENERATION_KEY) or "").strip():
            return
        keys = {
            obligation_key_from_row(row)
            for row in collect_obligation_rows_from_saved_data(data)
        }
        if keys & LEGACY_RECORD_DUTY_KEYS:
            return
        data[RECORD_DUTY_GENERATION_KEY] = RECORD_DUTY_GENERATION_COMBINED
        investigation_service.save_zajisteni_dukazu(
            accident.id,
            json.dumps(data, ensure_ascii=False),
        )

    def should_create_verify_kind_task(
        self,
        accident: Accident,
        *,
        today: date | None = None,
    ) -> bool:
        """Úkol jen pro úraz s DPN do 3 dnů, bez závažného/smrtelného a bez zpoždění 4+ dní."""
        if is_serious_accident(accident) or is_fatal_accident(accident):
            return False
        if not is_dpn_up_to_3_kind(getattr(accident, "druh_urazu", "") or ""):
            return False
        if not has_pn(accident):
            return False
        if accident.accident_date is None:
            return True
        reference = today or date.today()
        delay_days = (reference - accident.accident_date).days
        return delay_days <= VERIFY_KIND_TASK_MAX_RECORDING_DELAY_DAYS

    def should_resolve_verify_kind_task(self, accident: Accident) -> bool:
        """Dokončit úkol při změně druhu na >3 dny / závažný / smrtelný (bez čekání na DPN do)."""
        druh = getattr(accident, "druh_urazu", "") or ""
        if is_dpn_over_3_kind(druh):
            return True
        if is_serious_accident(accident) or is_fatal_accident(accident):
            return True
        return False

    def _create_verify_kind_task(self, accident: Accident) -> None:
        if not self.should_create_verify_kind_task(accident):
            return

        from moduly.ukoly.sluzby.task_service import task_service

        number = (accident.number or "").strip() or self._make_number(accident.id, accident.year)
        base_date = accident.accident_date or date.today()
        task_service.create_task(
            title=verify_accident_kind_task_title(number),
            description=(
                f"Ověřit pracovní úraz č. {number} a případně upravit druh "
                "pracovního úrazu podle skutečné délky pracovní neschopnosti."
            ),
            due_date=base_date + timedelta(days=5),
            workplace_id=accident.workplace_id,
            source_module=ENTITY_ACCIDENT,
            source_record_id=accident.id,
            requires_verification=False,
        )

    def _resolve_verify_kind_task_if_needed(self, accident: Accident) -> None:
        if not self.should_resolve_verify_kind_task(accident):
            return

        from moduly.ukoly.sluzby.task_service import task_service

        open_task = self._find_open_verify_kind_task(accident.id)
        if open_task is None:
            return
        task_service.mark_completed(open_task.id)

    def _find_open_verify_kind_task(self, accident_id: int):
        from moduly.ukoly.sluzby.task_service import task_service

        for task in task_service.repository.list_by_source(
            source_module=ENTITY_ACCIDENT,
            source_record_id=accident_id,
        ):
            if task.completed or task.canceled:
                continue
            if is_verify_accident_kind_task_title(task.title):
                return task
        return None

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
