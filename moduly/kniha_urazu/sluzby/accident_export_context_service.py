import json
from dataclasses import dataclass
from datetime import date, datetime

from core.shared.constants import ENTITY_MU_INVESTIGATION
from core.shared.sluzby.finding_service import finding_service
from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_LEVEL_BEZPROSTREDNI,
    ISHIKAWA_LEVEL_SYSTEMOVA,
    ISHIKAWA_LEVEL_ZAKLADNI,
    ISHIKAWA_STATUS_VYVRACENO,
    MU_STATUS_DOKONCENO,
    SOURCE_TYPE_ACCIDENT,
)
from moduly.vysetrovani_mu.modely.mu_investigation import MuInvestigation
from moduly.vysetrovani_mu.sluzby.mu_chronologie_events import build_system_chronologie_events
from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service


def _parse_json(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _first_nonempty(*values):
    for value in values:
        if _is_nonempty(value):
            return value
    return ""


def _text(value) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class AccidentExportContext:
    """Sjednocený kontext exportu úrazu s prioritou dat z Vyšetřování MU."""

    accident_id: int
    admin_investigation: AccidentInvestigation
    legacy_data: dict
    mu_investigation: MuInvestigation | None

    @property
    def has_mu(self) -> bool:
        return self.mu_investigation is not None

    @property
    def mu_id(self) -> int | None:
        return self.mu_investigation.id if self.mu_investigation is not None else None

    def merged_data(self) -> dict:
        """Legacy JSON tvar s hodnotami z MU (pokud existuje) nad fallbackem administrace."""
        merged = dict(self.legacy_data)
        if not self.has_mu:
            return merged

        mu = self.mu_investigation
        for key, value in self._mu_legacy_field_map().items():
            if _is_nonempty(value):
                merged[key] = value

        return merged

    def oznameni_value(self, field_name: str):
        if self.has_mu:
            mu_value = getattr(self.mu_investigation, field_name, None)
            if _is_nonempty(mu_value):
                return mu_value
        return getattr(self.admin_investigation, field_name, None)

    def investigation_started_at(self, accident) -> date | None:
        if self.has_mu and self.mu_investigation.started_at is not None:
            return self.mu_investigation.started_at
        legacy = self.legacy_data.get("admin_zahajeni")
        if legacy:
            return self._parse_date_value(legacy)
        return getattr(accident, "investigation_started_at", None)

    def investigation_closed_at(self) -> date | None:
        if self.has_mu:
            zaver = _parse_json(self.mu_investigation.zaver_json)
            closed = self._parse_date_value(zaver.get("uzavreni_datum"))
            if closed is not None:
                return closed
        legacy = self.legacy_data.get("admin_ukonceni")
        if legacy:
            return self._parse_date_value(legacy)
        return None

    def investigator_name(self) -> str:
        if self.has_mu:
            zaver = _parse_json(self.mu_investigation.zaver_json)
            return _text(
                _first_nonempty(
                    zaver.get("uzavreni_vedouci"),
                    self.mu_investigation.lead_thp_worker_name,
                )
            )
        return _text(
            _first_nonempty(
                self.legacy_data.get("admin_setreni_jmeno"),
                self.legacy_data.get("provedl"),
                self.admin_investigation.oznameni_komu,
            )
        )

    def investigation_status_label(self) -> str:
        if self.has_mu and _text(self.mu_investigation.status):
            return _text(self.mu_investigation.status)
        return "Zahájeno"

    def case_closed_label(self, accident) -> str:
        if self.has_mu and self.mu_investigation.status == MU_STATUS_DOKONCENO:
            return "ANO"
        if self.legacy_data.get("admin_pripad_uzavren") in ("ANO", "NE"):
            return self.legacy_data.get("admin_pripad_uzavren")
        return "ANO" if getattr(accident, "closed", False) else "NE"

    def collect_tasks(self):
        tasks = []
        seen: set[int] = set()

        def add_task(task) -> None:
            if task is None or task.id in seen:
                return
            seen.add(task.id)
            tasks.append(task)

        accident_id = self.accident_id
        mu_id = self.mu_id

        for task in task_service.get_all_tasks():
            source_module = getattr(task, "source_module", "") or ""
            source_record_id = getattr(task, "source_record_id", None)
            if source_module in ("accident", "kniha_urazu", "kniha_urazu_opatreni", "uraz"):
                if source_record_id == accident_id:
                    add_task(task)
            elif mu_id is not None and source_module == ENTITY_MU_INVESTIGATION:
                if source_record_id == mu_id:
                    add_task(task)

        if mu_id is not None:
            try:
                findings = finding_service.get_for_entity(ENTITY_MU_INVESTIGATION, mu_id)
            except Exception:
                findings = []
            for finding in findings:
                task_id = getattr(finding, "task_id", None)
                if task_id:
                    add_task(task_service.get_task_by_id(task_id))

        return tasks

    def witness_lines(self, accident) -> str | None:
        """Vrátí text svědků nebo None pro fallback na údaje z karty úrazu."""
        if not self.has_mu:
            return None

        svedci = _parse_json(self.mu_investigation.svedci_json)
        lines: list[str] = []
        for name in svedci.get("svedci", []) or []:
            text = _text(name)
            if text:
                lines.append(text)
        obsah = _text(svedci.get("obsah"))
        if obsah:
            lines.append(obsah)
        if not lines:
            return None
        return "\n".join(lines)

    def immediate_measures_summary(self) -> str:
        if not self.has_mu:
            return ""

        mu = self.mu_investigation
        labels = []
        mapping = (
            (mu.opatreni_prvni_pomoc, "První pomoc"),
            (mu.opatreni_zzs, "ZZS"),
            (mu.opatreni_policie, "PČR"),
            (mu.opatreni_hzs, "HZS"),
            (mu.opatreni_zastavena_cinnost, "Zastavena činnost"),
            (mu.opatreni_zajisteno_misto, "Zajištěno místo"),
            (mu.opatreni_zabraneno_manipulaci, "Zabráněna manipulace"),
            (mu.opatreni_informovan_nadrizeny, "Informován nadřízený"),
            (mu.opatreni_informovan_bozp, "Informován BOZP"),
            (mu.opatreni_informovany_dalsi, "Informovány další osoby"),
        )
        for value, label in mapping:
            if _text(value).upper() == "ANO":
                labels.append(label)
        return ", ".join(labels)

    def chronologie_summary(self) -> str:
        if not self.has_mu:
            return ""

        mu = self.mu_investigation
        casova = _parse_json(mu.casova_osa_json)
        manual_entries = casova.get("chronologie", []) or []
        system_entries = build_system_chronologie_events(
            started_at=mu.started_at,
            source_type=mu.source_type or SOURCE_TYPE_ACCIDENT,
            source_id=mu.source_id,
            oznameni_datum=mu.oznameni_datum,
            oznameni_cas=mu.oznameni_cas,
        )
        merged = list(system_entries) + list(manual_entries)
        if not merged:
            return ""

        lines = []
        for entry in sorted(merged, key=self._chronologie_sort_key):
            datum = _text(entry.get("datum"))
            cas = _text(entry.get("cas"))
            typ = _text(entry.get("typ"))
            popis = _text(entry.get("popis"))
            when = f"{datum} {cas}".strip() if cas else datum
            parts = [part for part in (when, typ, popis) if part]
            if parts:
                lines.append(" – ".join(parts))
        return "\n".join(lines)

    def findings_summary(self) -> str:
        if not self.has_mu or self.mu_id is None:
            return ""

        try:
            findings = finding_service.get_for_entity(ENTITY_MU_INVESTIGATION, self.mu_id)
        except Exception:
            return ""

        lines = []
        for index, finding in enumerate(findings, start=1):
            description = _text(getattr(finding, "description", ""))
            if not description:
                continue
            reference = _text(getattr(finding, "reference_label", ""))
            prefix = f"{index}. "
            if reference:
                prefix = f"{index}. [{reference}] "
            lines.append(f"{prefix}{description}")
        return "\n\n".join(lines)

    def _mu_legacy_field_map(self) -> dict:
        mu = self.mu_investigation
        zaver = _parse_json(mu.zaver_json)
        soulad = _parse_json(mu.kontrola_souladu_json)
        dodrz = _parse_json(mu.dodrzovani_predpisu_json)
        ohledani = _parse_json(mu.ohledani_mista_json)

        ishikawa_data = _parse_json(mu.ishikawa_json)
        causes = ishikawa_data.get("causes", []) if isinstance(ishikawa_data, dict) else []

        return {
            **{key: value for key, value in soulad.items() if key.startswith("soulad_")},
            **{key: value for key, value in dodrz.items() if key.startswith("dodrz_")},
            **{key: value for key, value in ohledani.items() if key.startswith("ohledani_")},
            "analyza_shrnuti_skutecneho_stavu": _first_nonempty(
                zaver.get("vysledek_prubeh"),
                mu.short_description,
            ),
            "analyza_zjistene_skutecnosti": _first_nonempty(
                zaver.get("vysledek_hlavni_zjisteni"),
                self.findings_summary(),
            ),
            "analyza_bezprostredni_pricina": self._ishikawa_level_text(causes, ISHIKAWA_LEVEL_BEZPROSTREDNI),
            "analyza_korenova_pricina": _first_nonempty(
                zaver.get("vysledek_hlavni_priciny"),
                self._ishikawa_level_text(causes, ISHIKAWA_LEVEL_ZAKLADNI),
            ),
            "analyza_proc_5": self._ishikawa_level_text(causes, ISHIKAWA_LEVEL_SYSTEMOVA),
            "analyza_poznamka_bozp": soulad.get("soulad_poznamky", ""),
        }

    def _ishikawa_level_text(self, causes: list, level: str) -> str:
        lines = []
        for cause in causes:
            if not isinstance(cause, dict):
                continue
            if _text(cause.get("cause_level")) != level:
                continue
            if _text(cause.get("status")) == ISHIKAWA_STATUS_VYVRACENO:
                continue
            description = _text(cause.get("description"))
            if description:
                lines.append(description)
        return "\n".join(lines)

    @staticmethod
    def _parse_date_value(value) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = _text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text).date()
        except Exception:
            return None

    @staticmethod
    def _chronologie_sort_key(entry: dict) -> tuple:
        datum = _text(entry.get("datum"))
        cas = _text(entry.get("cas"))
        return (datum, cas, _text(entry.get("typ")), _text(entry.get("popis")))


class AccidentExportContextService:
    def build(self, accident) -> AccidentExportContext:
        if accident is None or not getattr(accident, "id", None):
            raise ValueError("Není vybraný uložený úraz.")

        accident_id = int(accident.id)
        admin = investigation_service.get_or_create(accident_id)
        legacy_data = _parse_json(getattr(admin, "zajisteni_dukazu_json", ""))
        mu = mu_investigation_service.find_by_source(SOURCE_TYPE_ACCIDENT, accident_id)

        return AccidentExportContext(
            accident_id=accident_id,
            admin_investigation=admin,
            legacy_data=legacy_data,
            mu_investigation=mu,
        )


accident_export_context_service = AccidentExportContextService()
