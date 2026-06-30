from datetime import date, datetime

from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.shared.sluzby.finding_service import finding_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.vysetrovani_mu.constants import DEFAULT_MU_STATUS, VALID_MU_STATUSES
from moduly.vysetrovani_mu.modely.mu_investigation import MuInvestigation
from moduly.vysetrovani_mu.repository.mu_investigation_repository import MuInvestigationRepository
from moduly.vysetrovani_mu.sluzby.mu_number_utils import mu_number_sort_key

_OZNAMENI_FIELDS = (
    "oznameni_kdo",
    "oznameni_komu",
    "oznameni_datum",
    "oznameni_cas",
    "oznameni_bezodkladne",
    "oznameni_duvod_pozde",
    "oznameni_popis",
    "opatreni_prvni_pomoc",
    "opatreni_zzs",
    "opatreni_zastavena_cinnost",
    "opatreni_zajisteno_misto",
    "opatreni_zabraneno_manipulaci",
    "opatreni_informovan_nadrizeny",
    "opatreni_informovan_bozp",
    "oznameni_bozp_datum",
    "oznameni_bozp_cas",
    "opatreni_informovany_dalsi",
    "dalsi_postup",
    "dalsi_postup_jiny",
)


class MuInvestigationService:
    def __init__(self):
        self.repository = MuInvestigationRepository()

    def get_all(self) -> list[MuInvestigation]:
        investigations = self.repository.get_all()
        return sorted(
            investigations,
            key=lambda investigation: mu_number_sort_key(investigation.number or ""),
            reverse=True,
        )

    def get_by_id(self, investigation_id: int) -> MuInvestigation | None:
        return self.repository.get_by_id(investigation_id)

    def create_investigation(
        self,
        title: str = "",
        event_character: str = "",
        source_type: str = "",
        source_id: int | None = None,
        source_label: str = "",
        started_at: date | None = None,
        status: str = DEFAULT_MU_STATUS,
        lead_thp_worker_id: int | None = None,
        lead_thp_worker_name: str = "",
        short_description: str = "",
        conclusion: str = "",
        ohledani_mista_json: str = "",
        zajisteni_dukazu_json: str = "",
        svedci_json: str = "",
        casova_osa_json: str = "",
        dodrzovani_predpisu_json: str = "",
        kontrola_souladu_json: str = "",
        zaver_json: str = "",
        ishikawa_json: str = "",
        **kwargs,
    ) -> MuInvestigation:
        if status not in VALID_MU_STATUSES:
            raise ValueError(f"Neplatný stav vyšetřování: {status}")

        investigation = MuInvestigation(
            title=title.strip(),
            event_character=event_character.strip(),
            source_type=source_type.strip(),
            source_id=source_id,
            source_label=source_label.strip(),
            started_at=started_at,
            status=status,
            lead_thp_worker_id=lead_thp_worker_id,
            lead_thp_worker_name=lead_thp_worker_name.strip() or self.resolve_lead_thp_worker_name(lead_thp_worker_id),
            short_description=short_description.strip(),
            conclusion=conclusion.strip(),
            ohledani_mista_json=ohledani_mista_json or "",
            zajisteni_dukazu_json=zajisteni_dukazu_json or "",
            svedci_json=svedci_json or "",
            casova_osa_json=casova_osa_json or "",
            dodrzovani_predpisu_json=dodrzovani_predpisu_json or "",
            kontrola_souladu_json=kontrola_souladu_json or "",
            zaver_json=zaver_json or "",
            ishikawa_json=ishikawa_json or "",
        )
        self._apply_oznameni_fields(investigation, kwargs)
        saved = self.repository.add(investigation)
        saved.number = self._make_number(saved)
        return self.repository.update(saved)

    def update_investigation(
        self,
        investigation_id: int,
        title: str = "",
        event_character: str = "",
        source_type: str = "",
        source_id: int | None = None,
        source_label: str = "",
        started_at: date | None = None,
        status: str = DEFAULT_MU_STATUS,
        lead_thp_worker_id: int | None = None,
        lead_thp_worker_name: str = "",
        short_description: str = "",
        conclusion: str = "",
        ohledani_mista_json: str = "",
        zajisteni_dukazu_json: str = "",
        svedci_json: str = "",
        casova_osa_json: str = "",
        dodrzovani_predpisu_json: str = "",
        kontrola_souladu_json: str = "",
        zaver_json: str = "",
        ishikawa_json: str = "",
        **kwargs,
    ) -> MuInvestigation | None:
        investigation = self.repository.get_by_id(investigation_id)
        if investigation is None:
            return None

        if status not in VALID_MU_STATUSES:
            raise ValueError(f"Neplatný stav vyšetřování: {status}")

        investigation.title = title.strip()
        investigation.event_character = event_character.strip()
        investigation.source_type = source_type.strip()
        investigation.source_id = source_id
        investigation.source_label = source_label.strip()
        investigation.started_at = started_at
        investigation.status = status
        investigation.lead_thp_worker_id = lead_thp_worker_id
        investigation.lead_thp_worker_name = lead_thp_worker_name.strip() or self.resolve_lead_thp_worker_name(lead_thp_worker_id)
        investigation.short_description = short_description.strip()
        investigation.conclusion = conclusion.strip()
        investigation.ohledani_mista_json = ohledani_mista_json or ""
        investigation.zajisteni_dukazu_json = zajisteni_dukazu_json or ""
        investigation.svedci_json = svedci_json or ""
        investigation.casova_osa_json = casova_osa_json or ""
        investigation.dodrzovani_predpisu_json = dodrzovani_predpisu_json or ""
        investigation.kontrola_souladu_json = kontrola_souladu_json or ""
        investigation.zaver_json = zaver_json or ""
        investigation.ishikawa_json = ishikawa_json or ""
        self._apply_oznameni_fields(investigation, kwargs)
        investigation.updated_at = datetime.now()

        return self.repository.update(investigation)

    def _apply_oznameni_fields(self, investigation: MuInvestigation, data: dict) -> None:
        for key in _OZNAMENI_FIELDS:
            if key not in data:
                continue
            value = data[key]
            if key in ("oznameni_datum", "oznameni_bozp_datum"):
                setattr(investigation, key, value)
                continue
            if isinstance(value, str):
                setattr(investigation, key, value.strip())
            else:
                setattr(investigation, key, value or "")

    def delete_investigation(self, investigation_id: int) -> bool:
        finding_service.delete_for_entity(ENTITY_MU_INVESTIGATION, investigation_id)
        return self.repository.delete(investigation_id)

    def resolve_lead_thp_worker_name(self, worker_id: int | None) -> str:
        if not worker_id:
            return ""

        worker = settings_service.get_worker_by_id(worker_id)
        return worker.display_name if worker is not None else ""

    def _number_year(self, investigation: MuInvestigation) -> int:
        if investigation.started_at is not None:
            return investigation.started_at.year
        return date.today().year

    def _make_number(self, investigation: MuInvestigation) -> str:
        year = self._number_year(investigation)
        sequence = self._next_sequence(year)
        return f"MU-{sequence}/{year}"

    def _next_sequence(self, year: int) -> int:
        max_sequence = 0
        for investigation in self.repository.get_all():
            if self._number_year(investigation) != year:
                continue
            max_sequence = max(max_sequence, self._parse_sequence(investigation.number, year))
        return max_sequence + 1

    def _parse_sequence(self, number: str, year: int) -> int:
        if not number:
            return 0

        prefix = "MU-"
        suffix = f"/{year}"
        if not number.startswith(prefix) or not number.endswith(suffix):
            return 0

        middle = number[len(prefix) : -len(suffix)]
        try:
            return int(middle)
        except ValueError:
            return 0


mu_investigation_service = MuInvestigationService()
