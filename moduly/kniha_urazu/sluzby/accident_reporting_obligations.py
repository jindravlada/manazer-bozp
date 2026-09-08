from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol


class AccidentLike(Protocol):
    druh_urazu: str
    podezreni_trestny_cin: str
    dpn_od: date | None
    dpn_do: date | None
    accident_date: date | None


OBLIGATION_OO_OHLASENI = "oo_ohlaseni"
OBLIGATION_OIP_OBU_OHLASENI = "oip_obu_ohlaseni"
OBLIGATION_POLICIE_OHLASENI = "policie_ohlaseni"
OBLIGATION_ZP_OHLASENI = "zp_ohlaseni"
OBLIGATION_VYHOTOVENI_ZAZNAMU = "vyhotoveni_zaznamu"
OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU = "vyhotoveni_zaslani_zaznamu"
OBLIGATION_OIP_OBU_ZASLANI = "oip_obu_zaslani"
OBLIGATION_POLICIE_ZASLANI = "policie_zaslani"
OBLIGATION_ZP_ZASLANI = "zp_zaslani"
OBLIGATION_EZOP = "ezop"
OBLIGATION_ZAMESTNANEC_PREDANI = "zamestnanec_predani"
OBLIGATION_OO_PREDANI = "oo_predani"
OBLIGATION_RODINA_PREDANI = "rodina_predani"
OBLIGATION_CSSZ_USSZ_NEMOCENSKE = "cssz_ussz_nemocenske"
OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN = "aktualizace_zaznamu_po_dpn"
OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL = "aktualizace_oip_obu_portal"
OBLIGATION_AKTUALIZACE_ZP = "aktualizace_zp"
OBLIGATION_AKTUALIZACE_ZAMESTNANEC = "aktualizace_zamestnanec"
OBLIGATION_AKTUALIZACE_OO = "aktualizace_oo"
OBLIGATION_AKTUALIZACE_POLICIE = "aktualizace_policie"
OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI = "zakonna_pojistovna_hlaseni"
OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU = "zakonna_pojistovna_aktualizace_zou"

SECTION_OHLASENI = "ohlaseni"
SECTION_ZAZNAM = "zaznam"
SECTION_ODESLANI = "odeslani"
SECTION_PREDANI = "predani"
SECTION_NEMOCENSKE = "nemocenske"
SECTION_AKTUALIZACE_PO_DPN = "aktualizace_po_dpn"
SECTION_ZAKONNA_POJISTOVNA = "zakonna_pojistovna"

CATEGORY_NO_PN = "no_pn"
CATEGORY_PN_UP_TO_3 = "pn_up_to_3"
CATEGORY_PN_OVER_3 = "pn_over_3"
CATEGORY_SERIOUS = "serious"
CATEGORY_FATAL = "fatal"

OBLIGATION_LABELS: dict[str, str] = {
    OBLIGATION_OO_OHLASENI: "Odborová organizace – ohlášení pracovního úrazu",
    OBLIGATION_OIP_OBU_OHLASENI: "OIP / OBÚ – ohlášení závažného nebo smrtelného pracovního úrazu",
    OBLIGATION_POLICIE_OHLASENI: "Policie ČR – ohlášení smrtelného pracovního úrazu / podezření na trestný čin",
    OBLIGATION_ZP_OHLASENI: "Zdravotní pojišťovna postiženého – ohlášení smrtelného pracovního úrazu",
    OBLIGATION_VYHOTOVENI_ZAZNAMU: "Vyhotovení Záznamu o pracovním úrazu",
    OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU: "Vyhotovení + zaslání záznamu o pracovním úrazu – OIP/OBÚ",
    OBLIGATION_OIP_OBU_ZASLANI: "OIP / OBÚ – zaslání záznamu o pracovním úrazu",
    OBLIGATION_POLICIE_ZASLANI: "Policie ČR – zaslání záznamu o pracovním úrazu",
    OBLIGATION_ZP_ZASLANI: "Zdravotní pojišťovna postiženého – zaslání záznamu o pracovním úrazu",
    OBLIGATION_EZOP: "EZOP – ohlášení pracovního úrazu",
    OBLIGATION_ZAMESTNANEC_PREDANI: "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu",
    OBLIGATION_OO_PREDANI: "Odborová organizace – předání podepsaného záznamu o pracovním úrazu",
    OBLIGATION_RODINA_PREDANI: "Rodinní příslušníci – předání záznamu o pracovním úrazu",
    OBLIGATION_CSSZ_USSZ_NEMOCENSKE: "ČSSZ / ÚSSZ – podklady k nemocenskému",
    OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL: (
        "OIP / OBÚ – aktualizace záznamu přes Portál SÚIP"
    ),
    OBLIGATION_AKTUALIZACE_ZP: (
        "Zdravotní pojišťovna postiženého – zaslání aktualizovaného záznamu o pracovním úrazu"
    ),
    OBLIGATION_AKTUALIZACE_ZAMESTNANEC: (
        "Postižený zaměstnanec – předání aktualizovaného záznamu o pracovním úrazu"
    ),
    OBLIGATION_AKTUALIZACE_OO: (
        "Odborová organizace – předání aktualizovaného záznamu o pracovním úrazu"
    ),
    OBLIGATION_AKTUALIZACE_POLICIE: (
        "Policie ČR – zaslání aktualizovaného záznamu o pracovním úrazu"
    ),
    OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI: (
        "Zákonná pojišťovna – nahlášení pojistné události"
    ),
    OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU: (
        "Zákonná pojišťovna – doplnění aktualizovaného záznamu o pracovním úrazu"
    ),
}

LEGACY_LABEL_ALIASES: dict[str, str] = {
    "Záznam o pracovním úrazu – Portál SÚIP": OBLIGATION_VYHOTOVENI_ZAZNAMU,
    "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu": OBLIGATION_ZAMESTNANEC_PREDANI,
    "Odborová organizace – předání podepsaného záznamu o pracovním úrazu": OBLIGATION_OO_PREDANI,
    "Aktualizace záznamu po ukončení DPN": "",
    "Kooperativa": OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
}

_RECORD_MATRIX_CATEGORIES = frozenset({
    CATEGORY_PN_OVER_3,
    CATEGORY_SERIOUS,
    CATEGORY_FATAL,
})

RECORD_DUTY_GENERATION_KEY = "record_duty_generation"
RECORD_DUTY_GENERATION_LEGACY = "legacy"
RECORD_DUTY_GENERATION_COMBINED = "combined"

LEGACY_RECORD_DUTY_KEYS = frozenset({
    OBLIGATION_VYHOTOVENI_ZAZNAMU,
    OBLIGATION_OIP_OBU_ZASLANI,
})

METHOD_PORTAL_SUIP = "Portál SÚIP"
PORTAL_SUIP_OIP_NOTICE_FROM = date(2026, 1, 1)

POST_DPN_SOURCE_OBLIGATION: dict[str, str] = {
    OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL: "",
    OBLIGATION_AKTUALIZACE_ZP: OBLIGATION_ZP_ZASLANI,
    OBLIGATION_AKTUALIZACE_ZAMESTNANEC: OBLIGATION_ZAMESTNANEC_PREDANI,
    OBLIGATION_AKTUALIZACE_OO: OBLIGATION_OO_PREDANI,
    OBLIGATION_AKTUALIZACE_POLICIE: OBLIGATION_POLICIE_ZASLANI,
}
POST_DPN_OBLIGATION_KEYS = frozenset(POST_DPN_SOURCE_OBLIGATION)
POST_DPN_SIGNED_RECORD_KEYS = frozenset(
    key
    for key in POST_DPN_OBLIGATION_KEYS
    if key != OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
)
ZAKONNA_POJISTOVNA_KEYS = frozenset({
    OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
    OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU,
})

ZAKONNA_HLASENI_STATUS_DONE = "✔ Nahlášeno"
ZAKONNA_HLASENI_STATUS_WAITING = "Dosud nenahlášeno"
ZAKONNA_AKTUALIZACE_STATUS_DONE = "✔ Doplněno"
ZAKONNA_AKTUALIZACE_STATUS_WAITING = "Dosud nedoplněno"
ZAKONNA_TOGETHER_CHECKBOX_LABEL = "Nahlášení včetně aktuálního podepsaného ZoÚ"

DPN_RECORD_UPDATE_KEY = "dpn_record_update"
DPN_RECORD_UPDATE_PORTAL_DONE = "portal_suip_done"
DPN_RECORD_UPDATE_PORTAL_DATE = "portal_suip_date"
DPN_RECORD_UPDATE_SIGNED_DONE = "signed_record_done"
DPN_RECORD_UPDATE_SIGNED_DATE = "signed_record_date"
# Interní organizační termín Manažera BOZP, ne zákonná lhůta.
DPN_SIGNED_RECORD_REMINDER_CALENDAR_DAYS = 2


@dataclass(frozen=True)
class ReportingObligation:
    key: str
    section: str
    label: str


def accident_kind_text(accident: AccidentLike | None) -> str:
    if accident is None:
        return ""
    return (getattr(accident, "druh_urazu", "") or "").lower()


def is_fatal_accident(accident: AccidentLike | None) -> bool:
    return "smrt" in accident_kind_text(accident)


def is_serious_accident(accident: AccidentLike | None) -> bool:
    text = accident_kind_text(accident)
    return "závaž" in text or "zavaz" in text


def is_serious_or_fatal_accident(accident: AccidentLike | None) -> bool:
    return is_serious_accident(accident) or is_fatal_accident(accident)


def is_criminal_suspicion(accident: AccidentLike | None) -> bool:
    if accident is None:
        return False
    return (getattr(accident, "podezreni_trestny_cin", "") or "").strip().upper() == "ANO"


def requires_police_obligation(accident: AccidentLike | None) -> bool:
    """Povinnosti vůči Policii ČR.

    U smrtelného pracovního úrazu vznikají vždy, bez ohledu na pole
    podezření na trestný čin. U ostatních druhů úrazu jen při ručně
    zadaném podezření (hodnota ANO).
    """
    if is_fatal_accident(accident):
        return True
    return is_criminal_suspicion(accident)


def accident_event_date(accident: AccidentLike | None) -> date | None:
    if accident is None:
        return None
    raw = getattr(accident, "accident_date", None)
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return None


def oip_notice_uses_fixed_portal_suip(accident: AccidentLike | None) -> bool:
    """Ohlášení OIP/OBÚ od 1. 1. 2026 jen Portálem SÚIP (NV č. 322/2025 Sb.)."""
    event_date = accident_event_date(accident)
    if event_date is None:
        return True
    return event_date >= PORTAL_SUIP_OIP_NOTICE_FROM


def pn_calendar_days(accident: AccidentLike | None) -> int | None:
    if accident is None:
        return None
    return dpn_calendar_days(
        getattr(accident, "dpn_od", None),
        getattr(accident, "dpn_do", None),
    )


def dpn_calendar_days(dpn_od: date | None, dpn_do: date | None) -> int | None:
    """Počet kalendářních dnů DPN včetně prvního i posledního dne."""
    if dpn_od and dpn_do:
        return (dpn_do - dpn_od).days + 1
    return None


CSSZ_DPN_REQUIRED_AFTER_DAYS = 14
CSSZ_STATUS_DONE = "✔ Odesláno"
CSSZ_STATUS_REQUIRED = "Povinné – dosud neodesláno"
CSSZ_STATUS_OPTIONAL = "Lze odeslat předem – zatím není povinné"


def _cssz_as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_saved_date(value)


def cssz_dpn_calendar_days(
    dpn_od: date | None,
    dpn_do: date | None,
    *,
    today: date | None = None,
) -> int | None:
    """Délka DPN pro povinnost ČSSZ/ÚSSZ.

    Uzavřená DPN: včetně prvního i posledního dne.
    Probíhající DPN (chybí ``dpn_do``): včetně prvního dne vůči ``today``.
    Neplatný nebo budoucí interval vrací ``None`` – nevznikne falešná povinnost.
    """
    reference = _cssz_as_date(today) or date.today()
    start = _cssz_as_date(dpn_od)
    if start is None:
        return None
    if start > reference:
        return None
    end = _cssz_as_date(dpn_do)
    if end is None:
        return (reference - start).days + 1
    if end < start:
        return None
    if end > reference:
        end = reference
    return (end - start).days + 1


def cssz_nemocenske_is_required(
    accident: AccidentLike | None,
    *,
    today: date | None = None,
) -> bool:
    """True, pokud DPN trvá nebo trvala déle než 14 kalendářních dnů."""
    if accident is None:
        return False
    days = cssz_dpn_calendar_days(
        getattr(accident, "dpn_od", None),
        getattr(accident, "dpn_do", None),
        today=today,
    )
    return days is not None and days > CSSZ_DPN_REQUIRED_AFTER_DAYS


DPN_KIND_MISMATCH_MESSAGE = (
    "⚠ Druh pracovního úrazu pravděpodobně neodpovídá délce pracovní neschopnosti."
)
DPN_KIND_MISMATCH_BLOCK_MESSAGE = (
    "Druh pracovního úrazu neodpovídá délce pracovní neschopnosti.\n\n"
    "• Při DPN delší než 3 kalendářní dny nelze zvolit druh "
    "s pracovní neschopností do 3 kalendářních dnů.\n"
    "• Při DPN 0–3 kalendářní dny musí druh úrazu odpovídat "
    "zadané délce (bez PN / do 3 dnů)."
)

DPN_START_BEFORE_ACCIDENT_MESSAGE = (
    "Datum zahájení DPN nesmí být před datem pracovního úrazu."
)
DPN_END_BEFORE_START_MESSAGE = (
    "Datum ukončení DPN nesmí být před datem zahájení DPN."
)
DPN_END_IN_FUTURE_MESSAGE = (
    "Datum ukončení DPN nesmí být v budoucnosti."
)


def is_dpn_up_to_3_kind(druh_urazu: str) -> bool:
    text = (druh_urazu or "").lower()
    return (
        "nepřesahující 3" in text
        or "nepresahujici 3" in text
        or "do 3 kalendářních" in text
        or "do 3 kalendarnich" in text
    )


def is_dpn_over_3_kind(druh_urazu: str) -> bool:
    text = (druh_urazu or "").lower()
    return "delší než 3" in text or "delsi nez 3" in text or "nad 3" in text


def is_no_pn_kind(druh_urazu: str) -> bool:
    text = (druh_urazu or "").lower()
    return "bez pracovní neschopnosti" in text or "bez pn" in text


def is_dpn_kind_mismatch(druh_urazu: str, days: int | None) -> bool:
    """True, pokud zvolený druh úrazu neodpovídá známé délce DPN.

    Pokud délka DPN není známá (``days is None``), neshodu nehlásí –
    při prvotním zápisu délka často ještě není zjištěná.
    """
    if days is None:
        return False
    if is_dpn_up_to_3_kind(druh_urazu) and days > 3:
        return True
    if is_dpn_over_3_kind(druh_urazu) and days <= 3:
        return True
    if is_no_pn_kind(druh_urazu) and days > 0:
        return True
    return False


def is_dpn_start_before_accident(
    dpn_od: date | None,
    accident_date: date | None,
) -> bool:
    if dpn_od is None or accident_date is None:
        return False
    return dpn_od < accident_date


def is_dpn_end_before_start(
    dpn_od: date | None,
    dpn_do: date | None,
) -> bool:
    if dpn_od is None or dpn_do is None:
        return False
    return dpn_do < dpn_od


def is_dpn_end_in_future(
    dpn_do: date | None,
    *,
    today: date | None = None,
) -> bool:
    if dpn_do is None:
        return False
    return dpn_do > (today or date.today())


def is_dpn_ended(dpn_do: date | None) -> bool:
    """True, pokud je vyplněno existující pole ``Accident.dpn_do``."""
    return dpn_do is not None


def is_dpn_record_update_relevant(accident: AccidentLike | None) -> bool:
    """Aktualizace ZoÚ po DPN jen u úrazů se záznamem a vyplněným ``dpn_do``."""
    if accident is None:
        return False
    if not is_dpn_ended(getattr(accident, "dpn_do", None)):
        return False
    return requires_accident_record(accident)


def dpn_record_update_belongs_in_upcoming(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None = None,
    *,
    union_organization_active: bool | None = None,
) -> bool:
    """Povinná Aktualizace záznamu s termínem ``dpn_do``, dosud neodeslaná na Portál SÚIP.

    Podepsaný aktualizovaný záznam se pro Nadcházející nevyžaduje.
    """
    if not is_dpn_record_update_relevant(accident):
        return False
    if getattr(accident, "dpn_do", None) is None:
        return False
    overview = dpn_record_update_overview_from_saved_data(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    )
    return not dpn_record_update_is_submitted(overview)


def dpn_signed_record_is_ensured(state: dict[str, Any] | None) -> bool:
    """Zajištění podpisů aktualizovaného záznamu – samostatný stav, ne odvozený z odeslání."""
    data = normalize_dpn_record_update(state)
    return bool(data[DPN_RECORD_UPDATE_SIGNED_DONE])


def dpn_signed_record_reminder_due(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None = None,
    *,
    union_organization_active: bool | None = None,
) -> date | None:
    """Interní termín: datum skutečného provedení aktualizace + 2 kalendářní dny."""
    if not is_dpn_record_update_relevant(accident):
        return None
    overview = dpn_record_update_overview_from_saved_data(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    )
    if not dpn_record_update_is_submitted(overview):
        return None
    if dpn_signed_record_is_ensured(overview):
        return None
    submitted = parse_saved_date(overview.get(DPN_RECORD_UPDATE_PORTAL_DATE))
    if submitted is None:
        stored = dpn_record_update_from_saved_data(saved_data)
        submitted = parse_saved_date(stored.get(DPN_RECORD_UPDATE_PORTAL_DATE))
    if submitted is None:
        return None
    return submitted + timedelta(days=DPN_SIGNED_RECORD_REMINDER_CALENDAR_DAYS)


def dpn_signed_record_belongs_in_upcoming(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None = None,
    *,
    union_organization_active: bool | None = None,
) -> bool:
    return dpn_signed_record_reminder_due(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    ) is not None


def is_post_dpn_obligation_key(obligation_key: str) -> bool:
    return obligation_key in POST_DPN_OBLIGATION_KEYS


def is_post_dpn_obligation_relevant(
    accident: AccidentLike | None,
    obligation_key: str,
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    """Konkrétní povinnost po DPN jen pokud vzniká i původní povinnost danému adresátovi."""
    if obligation_key not in POST_DPN_SOURCE_OBLIGATION:
        return False
    if not is_dpn_record_update_relevant(accident):
        return False
    source_key = POST_DPN_SOURCE_OBLIGATION[obligation_key]
    if not source_key:
        return True
    return is_obligation_relevant(
        accident,
        source_key,
        union_organization_active=union_organization_active,
        saved_data=saved_data,
        record_duty_generation=record_duty_generation,
    )


def empty_dpn_record_update() -> dict[str, Any]:
    return {
        DPN_RECORD_UPDATE_PORTAL_DONE: False,
        DPN_RECORD_UPDATE_PORTAL_DATE: None,
        DPN_RECORD_UPDATE_SIGNED_DONE: False,
        DPN_RECORD_UPDATE_SIGNED_DATE: None,
    }


def _dpn_record_update_date_json(value: Any) -> str | None:
    parsed = parse_saved_date(value)
    return parsed.isoformat() if parsed is not None else None


def normalize_dpn_record_update(state: dict[str, Any] | None) -> dict[str, Any]:
    raw = state or {}
    return {
        DPN_RECORD_UPDATE_PORTAL_DONE: bool(raw.get(DPN_RECORD_UPDATE_PORTAL_DONE)),
        DPN_RECORD_UPDATE_PORTAL_DATE: _dpn_record_update_date_json(
            raw.get(DPN_RECORD_UPDATE_PORTAL_DATE)
        ),
        DPN_RECORD_UPDATE_SIGNED_DONE: bool(raw.get(DPN_RECORD_UPDATE_SIGNED_DONE)),
        DPN_RECORD_UPDATE_SIGNED_DATE: _dpn_record_update_date_json(
            raw.get(DPN_RECORD_UPDATE_SIGNED_DATE)
        ),
    }


def dpn_record_update_from_saved_data(saved_data: dict[str, Any] | None) -> dict[str, Any]:
    if not saved_data:
        return empty_dpn_record_update()
    raw = saved_data.get(DPN_RECORD_UPDATE_KEY)
    if not isinstance(raw, dict):
        return empty_dpn_record_update()
    return normalize_dpn_record_update(raw)


def dpn_record_update_has_progress(state: dict[str, Any] | None) -> bool:
    data = normalize_dpn_record_update(state)
    return bool(
        data[DPN_RECORD_UPDATE_PORTAL_DONE]
        or data[DPN_RECORD_UPDATE_PORTAL_DATE]
        or data[DPN_RECORD_UPDATE_SIGNED_DONE]
        or data[DPN_RECORD_UPDATE_SIGNED_DATE]
    )


def dpn_record_update_is_submitted(state: dict[str, Any] | None) -> bool:
    """Provedení / odeslání aktualizace (Portál SÚIP) – termínovaná povinnost Nadcházejících."""
    data = normalize_dpn_record_update(state)
    return bool(data[DPN_RECORD_UPDATE_PORTAL_DONE])


def dpn_record_update_is_done(state: dict[str, Any] | None) -> bool:
    """Kompletní evidence aktualizace včetně podepsaného záznamu (nepoužívat pro Nadcházející)."""
    data = normalize_dpn_record_update(state)
    return bool(
        data[DPN_RECORD_UPDATE_PORTAL_DONE]
        and data[DPN_RECORD_UPDATE_PORTAL_DATE]
        and data[DPN_RECORD_UPDATE_SIGNED_DONE]
        and data[DPN_RECORD_UPDATE_SIGNED_DATE]
    )


def dpn_record_update_completion_date(state: dict[str, Any] | None) -> date | None:
    data = normalize_dpn_record_update(state)
    dates = [
        parse_saved_date(data[DPN_RECORD_UPDATE_PORTAL_DATE]),
        parse_saved_date(data[DPN_RECORD_UPDATE_SIGNED_DATE]),
    ]
    present = [item for item in dates if item is not None]
    if not present:
        return None
    return max(present)


def apply_dpn_record_update_to_saved_data(
    saved_data: dict[str, Any] | None,
    *,
    accident: AccidentLike | None,
    ui_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotentní zápis stavu aktualizace ZoÚ. Nevyřízenou položku při odebrání ``dpn_do`` odstraní."""
    data = dict(saved_data or {})
    existing = dpn_record_update_from_saved_data(data)
    if not is_dpn_ended(getattr(accident, "dpn_do", None) if accident is not None else None):
        if dpn_record_update_is_done(existing):
            return data
        data.pop(DPN_RECORD_UPDATE_KEY, None)
        return data
    if ui_state is None:
        return data
    normalized = normalize_dpn_record_update(ui_state)
    if not dpn_record_update_has_progress(normalized):
        if dpn_record_update_is_done(existing):
            return data
        data.pop(DPN_RECORD_UPDATE_KEY, None)
        return data
    data[DPN_RECORD_UPDATE_KEY] = normalized
    return data


ACCIDENT_DATE_FUTURE_MESSAGE = "Datum pracovního úrazu nemůže být v budoucnosti."
RECORD_DATE_BEFORE_ACCIDENT_MESSAGE = (
    "Datum zápisu nemůže být dřívější než datum pracovního úrazu."
)
ACCIDENT_DATE_DELAY_WARNING = (
    "⚠ Úraz je zadáván se zpožděním delším než 14 dní. "
    "Ověřte správnost data a splnění zákonných lhůt."
)
INVESTIGATION_BEFORE_ACCIDENT_WARNING = (
    "⚠ Datum zahájení šetření je dřívější než datum pracovního úrazu. "
    "Ověřte správnost údajů."
)
SERIOUS_KIND_INFO = "Jedná se o závažný pracovní úraz."
FATAL_KIND_INFO = "Jedná se o smrtelný pracovní úraz."

_ACCIDENT_DATE_DELAY_DAYS = 14


def is_accident_date_in_future(accident_date: date | None, *, today: date | None = None) -> bool:
    if accident_date is None:
        return False
    return accident_date > (today or date.today())


def is_accident_date_delayed(accident_date: date | None, *, today: date | None = None) -> bool:
    if accident_date is None:
        return False
    reference = today or date.today()
    return (reference - accident_date).days > _ACCIDENT_DATE_DELAY_DAYS


def is_record_date_before_accident(
    datum_zapisu: date | None,
    accident_date: date | None,
) -> bool:
    if datum_zapisu is None or accident_date is None:
        return False
    return datum_zapisu < accident_date


def is_investigation_before_accident(
    investigation_date: date | None,
    accident_date: date | None,
) -> bool:
    if investigation_date is None or accident_date is None:
        return False
    return investigation_date < accident_date


def accident_kind_info_message(druh_urazu: str) -> str | None:
    text = (druh_urazu or "").lower()
    if "smrt" in text:
        return FATAL_KIND_INFO
    if "závaž" in text or "zavaz" in text:
        return SERIOUS_KIND_INFO
    return None


def has_pn(accident: AccidentLike | None) -> bool:
    if accident is None:
        return False
    if getattr(accident, "dpn_od", None):
        return True
    return "neschop" in accident_kind_text(accident)


def has_pn_over_3_days(accident: AccidentLike | None) -> bool:
    text = accident_kind_text(accident)
    if "delší než 3" in text or "delsi nez 3" in text or "nad 3" in text:
        return True
    days = pn_calendar_days(accident)
    return days is not None and days > 3


def accident_category(accident: AccidentLike | None) -> str:
    if is_fatal_accident(accident):
        return CATEGORY_FATAL
    if is_serious_accident(accident):
        return CATEGORY_SERIOUS
    if has_pn_over_3_days(accident):
        return CATEGORY_PN_OVER_3
    if has_pn(accident):
        return CATEGORY_PN_UP_TO_3
    return CATEGORY_NO_PN


def requires_accident_record(accident: AccidentLike | None) -> bool:
    return accident_category(accident) in _RECORD_MATRIX_CATEGORIES


def employer_union_organization_active() -> bool:
    try:
        from core.settings.settings_manager import settings

        settings.load()
        return bool(settings.get("odborova_organizace_pusobi", True))
    except Exception:
        return True


def obligation_key_from_row(row: dict[str, Any]) -> str:
    key = (row.get("key") or "").strip()
    if key:
        return key

    nazev = row.get("nazev", "")
    for mapped_key, label in OBLIGATION_LABELS.items():
        if nazev == label:
            return mapped_key

    legacy = LEGACY_LABEL_ALIASES.get(nazev)
    if legacy is not None:
        return legacy

    nazev_lower = str(nazev).lower()
    if "zákonná pojišťovna" in nazev_lower or nazev == "Kooperativa":
        if "aktualizovan" in nazev_lower or "doplnění" in nazev_lower:
            return OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU
        return OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI
    if "aktualizovan" in nazev_lower or "aktualizace záznamu přes portál" in nazev_lower:
        if "portál súip" in nazev_lower or "portal suip" in nazev_lower:
            return OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
        if "Zdravotní pojišťovna" in nazev:
            return OBLIGATION_AKTUALIZACE_ZP
        if "Postižený zaměstnanec" in nazev:
            return OBLIGATION_AKTUALIZACE_ZAMESTNANEC
        if "Odborová organizace" in nazev:
            return OBLIGATION_AKTUALIZACE_OO
        if "Policie ČR" in nazev:
            return OBLIGATION_AKTUALIZACE_POLICIE

    if "Odborová organizace" in nazev and "ohlášení" in nazev:
        return OBLIGATION_OO_OHLASENI
    if "OIP / OBÚ" in nazev and "ohlášení" in nazev:
        return OBLIGATION_OIP_OBU_OHLASENI
    if "Policie ČR" in nazev and "ohlášení" in nazev:
        return OBLIGATION_POLICIE_OHLASENI
    if "Zdravotní pojišťovna" in nazev and "ohlášení" in nazev:
        return OBLIGATION_ZP_OHLASENI
    if "EZOP" in nazev:
        return OBLIGATION_EZOP
    if "Vyhotovení + zaslání" in nazev:
        return OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
    if "Vyhotovení Záznamu" in nazev or ("Záznam o pracovním úrazu" in nazev and "Portál SÚIP" in nazev):
        return OBLIGATION_VYHOTOVENI_ZAZNAMU
    if "OIP / OBÚ" in nazev and "zaslání" in nazev:
        return OBLIGATION_OIP_OBU_ZASLANI
    if "Zdravotní pojišťovna" in nazev and "zaslání" in nazev:
        return OBLIGATION_ZP_ZASLANI
    if "Policie ČR" in nazev and "zaslání" in nazev:
        return OBLIGATION_POLICIE_ZASLANI
    if "Postižený zaměstnanec" in nazev and "předání" in nazev:
        return OBLIGATION_ZAMESTNANEC_PREDANI
    if "Odborová organizace" in nazev and "předání" in nazev:
        return OBLIGATION_OO_PREDANI
    if "Rodinní příslušníci" in nazev:
        return OBLIGATION_RODINA_PREDANI
    return ""


def is_obligation_relevant(
    accident: AccidentLike | None,
    obligation_key: str,
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    if not obligation_key:
        return False

    category = accident_category(accident)
    union_active = (
        employer_union_organization_active()
        if union_organization_active is None
        else union_organization_active
    )
    generation = resolve_record_duty_generation(
        saved_data,
        record_duty_generation=record_duty_generation,
    )

    if obligation_key == OBLIGATION_OO_OHLASENI:
        return union_active

    if obligation_key == OBLIGATION_OIP_OBU_OHLASENI:
        return category in {CATEGORY_SERIOUS, CATEGORY_FATAL}

    if obligation_key == OBLIGATION_POLICIE_OHLASENI:
        return requires_police_obligation(accident)

    if obligation_key == OBLIGATION_ZP_OHLASENI:
        return category == CATEGORY_FATAL

    if obligation_key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU:
        return (
            generation == RECORD_DUTY_GENERATION_COMBINED
            and category in _RECORD_MATRIX_CATEGORIES
        )

    if obligation_key in LEGACY_RECORD_DUTY_KEYS:
        if generation == RECORD_DUTY_GENERATION_COMBINED:
            return False
        return category in _RECORD_MATRIX_CATEGORIES

    if obligation_key in {
        OBLIGATION_ZP_ZASLANI,
        OBLIGATION_EZOP,
    }:
        return category in _RECORD_MATRIX_CATEGORIES

    if obligation_key == OBLIGATION_POLICIE_ZASLANI:
        return category in _RECORD_MATRIX_CATEGORIES and requires_police_obligation(accident)

    if obligation_key == OBLIGATION_ZAMESTNANEC_PREDANI:
        return category in {CATEGORY_PN_OVER_3, CATEGORY_SERIOUS}

    if obligation_key == OBLIGATION_OO_PREDANI:
        return category in _RECORD_MATRIX_CATEGORIES and union_active

    if obligation_key == OBLIGATION_RODINA_PREDANI:
        return category == CATEGORY_FATAL

    if obligation_key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
        # ČSSZ/ÚSSZ není adresát NV 322/2025 Sb. – nesmí vstoupit do ZoÚ, úkolů ani matice záznamu.
        return False

    if obligation_key in ZAKONNA_POJISTOVNA_KEYS:
        # Pojistná událost je samostatná agenda – nesmí blokovat indikátor ZoÚ.
        return False

    if obligation_key == OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN:
        # Souhrnná položka z PU-DPN-2 už není zdrojem pravdy ani čekající povinností ZoÚ.
        return False

    if obligation_key in POST_DPN_OBLIGATION_KEYS:
        return is_post_dpn_obligation_relevant(
            accident,
            obligation_key,
            union_organization_active=union_organization_active,
            saved_data=saved_data,
            record_duty_generation=record_duty_generation,
        )

    return False


def is_row_relevant(
    accident: AccidentLike | None,
    row: dict[str, Any],
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    return is_obligation_relevant(
        accident,
        obligation_key_from_row(row),
        union_organization_active=union_organization_active,
        saved_data=saved_data,
        record_duty_generation=record_duty_generation,
    )


def cssz_row_has_recorded_data(row: dict[str, Any] | None) -> bool:
    """True, pokud řádek ČSSZ/ÚSSZ už nese evidované údaje (nesmí se ztratit)."""
    if not row:
        return False
    predano = row.get("predano")
    if predano is True or predano == 1:
        return True
    kompletni = row.get("kompletni")
    if kompletni is True or kompletni == 1:
        return True
    datum = row.get("datum")
    if isinstance(datum, datetime):
        return True
    if isinstance(datum, date):
        return True
    if isinstance(datum, str) and datum.strip():
        return True
    for field in ("cas", "zpusob", "upresneni"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return True
    return False


def cssz_saved_row(saved_data: dict[str, Any] | None) -> dict[str, Any]:
    return obligation_row_from_saved_data(saved_data, OBLIGATION_CSSZ_USSZ_NEMOCENSKE)


def obligation_row_from_saved_data(
    saved_data: dict[str, Any] | None,
    obligation_key: str,
) -> dict[str, Any]:
    if not saved_data or not obligation_key:
        return {}
    for row in collect_obligation_rows_from_saved_data(saved_data):
        if obligation_key_from_row(row) == obligation_key:
            return row
    return {}


def is_cssz_nemocenske_visible(
    accident: AccidentLike | None,
    *,
    row: dict[str, Any] | None = None,
    saved_data: dict[str, Any] | None = None,
) -> bool:
    """Viditelnost ČSSZ/ÚSSZ: vyplněné ``dpn_od`` nebo už uložené údaje."""
    if accident is not None and getattr(accident, "dpn_od", None):
        return True
    if cssz_row_has_recorded_data(row):
        return True
    return cssz_row_has_recorded_data(cssz_saved_row(saved_data))


def is_obligation_visible(
    accident: AccidentLike | None,
    obligation_key: str,
    *,
    row: dict[str, Any] | None = None,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    if obligation_key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
        return is_cssz_nemocenske_visible(accident, row=row, saved_data=saved_data)
    if obligation_key == OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI:
        return True
    if obligation_key == OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU:
        if is_dpn_record_update_relevant(accident):
            return True
        if cssz_row_has_recorded_data(row):
            return True
        return cssz_row_has_recorded_data(
            obligation_row_from_saved_data(saved_data, obligation_key)
        )
    if obligation_key in POST_DPN_OBLIGATION_KEYS:
        if is_obligation_relevant(
            accident,
            obligation_key,
            union_organization_active=union_organization_active,
            saved_data=saved_data,
            record_duty_generation=record_duty_generation,
        ):
            return True
        if cssz_row_has_recorded_data(row):
            return True
        return cssz_row_has_recorded_data(
            obligation_row_from_saved_data(saved_data, obligation_key)
        )
    return is_obligation_relevant(
        accident,
        obligation_key,
        union_organization_active=union_organization_active,
        saved_data=saved_data,
        record_duty_generation=record_duty_generation,
    )


def is_row_visible(
    accident: AccidentLike | None,
    row: dict[str, Any],
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    return is_obligation_visible(
        accident,
        obligation_key_from_row(row),
        row=row,
        union_organization_active=union_organization_active,
        saved_data=saved_data,
        record_duty_generation=record_duty_generation,
    )


def is_obligation_required(
    accident: AccidentLike | None,
    obligation_key: str,
    *,
    today: date | None = None,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> bool:
    if obligation_key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
        return cssz_nemocenske_is_required(accident, today=today)
    if obligation_key in ZAKONNA_POJISTOVNA_KEYS:
        return False
    return is_obligation_relevant(
        accident,
        obligation_key,
        union_organization_active=union_organization_active,
        saved_data=saved_data,
        record_duty_generation=record_duty_generation,
    )


def cssz_row_ui_state(
    accident: AccidentLike | None,
    row: dict[str, Any] | None,
    *,
    today: date | None = None,
) -> str:
    """Stav položky ČSSZ/ÚSSZ: ``done`` / ``required`` / ``optional``."""
    if row_is_done(row or {}):
        return "done"
    if cssz_nemocenske_is_required(accident, today=today):
        return "required"
    return "optional"


def zakonna_row_ui_state(row: dict[str, Any] | None) -> str:
    """Stav položky zákonné pojišťovny: ``done`` / ``waiting`` (bez termínu)."""
    if row_is_done(row or {}):
        return "done"
    return "waiting"


def zakonna_together_checkbox_default(
    *,
    dpn_ended: bool,
    hlaseni_row: dict[str, Any] | None,
    aktualizace_row: dict[str, Any] | None,
) -> bool:
    """True, pokud jde o jedno nahlášení až po DPN spolu s aktuálním ZoÚ."""
    if not dpn_ended:
        return False
    if not row_is_done(hlaseni_row or {}):
        return True
    hlaseni_date = parse_saved_date((hlaseni_row or {}).get("datum"))
    update_date = parse_saved_date((aktualizace_row or {}).get("datum"))
    return hlaseni_date is not None and hlaseni_date == update_date


def _section_for_key(key: str) -> str:
    if key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
        return SECTION_NEMOCENSKE
    if key in ZAKONNA_POJISTOVNA_KEYS:
        return SECTION_ZAKONNA_POJISTOVNA
    if key in POST_DPN_OBLIGATION_KEYS:
        return SECTION_AKTUALIZACE_PO_DPN
    if key in {OBLIGATION_VYHOTOVENI_ZAZNAMU, OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU}:
        return SECTION_ZAZNAM
    if key in {
        OBLIGATION_OIP_OBU_ZASLANI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_ZP_ZASLANI,
        OBLIGATION_EZOP,
    }:
        return SECTION_ODESLANI
    if key in {
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_OO_PREDANI,
        OBLIGATION_RODINA_PREDANI,
    }:
        return SECTION_PREDANI
    return SECTION_OHLASENI


def applicable_obligations(
    accident: AccidentLike | None,
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> list[ReportingObligation]:
    items: list[ReportingObligation] = []
    for key, label in OBLIGATION_LABELS.items():
        if not is_obligation_relevant(
            accident,
            key,
            union_organization_active=union_organization_active,
            saved_data=saved_data,
            record_duty_generation=record_duty_generation,
        ):
            continue
        items.append(
            ReportingObligation(
                key=key,
                section=_section_for_key(key),
                label=label,
            )
        )
    return items


def all_obligation_definitions() -> list[ReportingObligation]:
    return [
        ReportingObligation(key=key, section=_section_for_key(key), label=label)
        for key, label in OBLIGATION_LABELS.items()
    ]


def obligation_definitions_for_accident(
    accident: AccidentLike | None = None,
    saved_data: dict[str, Any] | None = None,
    *,
    record_duty_generation: str | None = None,
) -> list[ReportingObligation]:
    """Definice widgetů pro konkrétní úraz: bez klíčů druhé generace záznamu."""
    del accident  # kategorie se filtruje až v is_row_relevant
    generation = resolve_record_duty_generation(
        saved_data,
        record_duty_generation=record_duty_generation,
    )
    skip = record_duty_keys_hidden_for_generation(generation) | {
        OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
    }
    return [
        item
        for item in all_obligation_definitions()
        if item.key not in skip
    ]


def collect_obligation_rows_from_saved_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    rows: list[dict[str, Any]] = []
    rows.extend(data.get("admin_ohlaseni") or [])
    rows.extend(data.get("admin_zaslani") or [])
    return rows


def record_duty_keys_hidden_for_generation(generation: str) -> frozenset[str]:
    if generation == RECORD_DUTY_GENERATION_COMBINED:
        return LEGACY_RECORD_DUTY_KEYS
    return frozenset({OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU})


def resolve_record_duty_generation(
    saved_data: dict[str, Any] | None = None,
    *,
    record_duty_generation: str | None = None,
) -> str:
    """Určí generaci záznamu. Bez značky a bez nových klíčů zůstává legacy sada."""
    if record_duty_generation in {
        RECORD_DUTY_GENERATION_LEGACY,
        RECORD_DUTY_GENERATION_COMBINED,
    }:
        return record_duty_generation

    data = saved_data or {}
    explicit = str(data.get(RECORD_DUTY_GENERATION_KEY) or "").strip()
    if explicit == RECORD_DUTY_GENERATION_COMBINED:
        return RECORD_DUTY_GENERATION_COMBINED
    if explicit == RECORD_DUTY_GENERATION_LEGACY:
        return RECORD_DUTY_GENERATION_LEGACY

    keys = {
        obligation_key_from_row(row)
        for row in collect_obligation_rows_from_saved_data(data)
    }
    keys.discard("")
    if keys & LEGACY_RECORD_DUTY_KEYS:
        return RECORD_DUTY_GENERATION_LEGACY
    if OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU in keys:
        return RECORD_DUTY_GENERATION_COMBINED
    return RECORD_DUTY_GENERATION_LEGACY


def add_workdays(start_date: date, days: int) -> date:
    result = start_date
    added = 0
    while added < days:
        result = result + timedelta(days=1)
        if result.weekday() < 5:
            added += 1
    return result


def obligation_notification_date(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None = None,
) -> date | None:
    if saved_data:
        parsed = parse_saved_date(saved_data.get("oznameni_datum"))
        if parsed is not None:
            return parsed
    if accident is not None:
        accident_date = getattr(accident, "accident_date", None)
        if accident_date is not None:
            return accident_date
    return None


def obligation_default_deadline(
    notification_date: date | None,
    *,
    obligation_key: str = "",
    section: str = "",
    label: str = "",
    agenda: str = "",
) -> date | None:
    if obligation_key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE or section == SECTION_NEMOCENSKE:
        return None
    if obligation_key == OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN:
        return None
    if obligation_key in POST_DPN_OBLIGATION_KEYS or section == SECTION_AKTUALIZACE_PO_DPN:
        return None
    if obligation_key in ZAKONNA_POJISTOVNA_KEYS or section == SECTION_ZAKONNA_POJISTOVNA:
        return None
    if "ČSSZ" in label or "ÚSSZ" in label:
        return None

    if notification_date is None:
        return None

    if "Kooperativa" in label or "Zákonná pojišťovna" in label:
        return None

    if obligation_key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU:
        return combined_record_duty_deadline(notification_date)

    if section == SECTION_OHLASENI or agenda == "ohlaseni":
        return add_workdays(notification_date, 1)

    if section in {SECTION_ZAZNAM, SECTION_ODESLANI, SECTION_PREDANI}:
        return add_workdays(notification_date, 15)

    if "Vyhotovení + zaslání" in label:
        return combined_record_duty_deadline(notification_date)

    if "Vyhotovení Záznamu" in label or "Záznam o pracovním úrazu" in label:
        return add_workdays(notification_date, 15)

    return None


def combined_record_duty_deadline(notification_date: date | None) -> date | None:
    """Dřívější z termínů vyhotovení a zaslání (dnes oba 15 pracovních dnů)."""
    vyhotoveni = obligation_default_deadline(
        notification_date,
        obligation_key=OBLIGATION_VYHOTOVENI_ZAZNAMU,
        section=SECTION_ZAZNAM,
        label=OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZAZNAMU],
    )
    zaslani = obligation_default_deadline(
        notification_date,
        obligation_key=OBLIGATION_OIP_OBU_ZASLANI,
        section=SECTION_ODESLANI,
        label=OBLIGATION_LABELS[OBLIGATION_OIP_OBU_ZASLANI],
    )
    dates = [item for item in (vyhotoveni, zaslani) if item is not None]
    if not dates:
        return None
    return min(dates)


def obligation_rows_for_summary(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None,
    *,
    union_organization_active: bool | None = None,
) -> list[dict[str, Any]]:
    saved_data = saved_data or {}
    rows_by_key: dict[str, dict[str, Any]] = {}
    for row in collect_obligation_rows_from_saved_data(saved_data):
        key = obligation_key_from_row(row)
        if key:
            rows_by_key[key] = row

    notification_date = obligation_notification_date(accident, saved_data)
    result: list[dict[str, Any]] = []

    for obligation in applicable_obligations(
        accident,
        union_organization_active=union_organization_active,
        saved_data=saved_data,
    ):
        if obligation.key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
            continue
        if obligation.key in ZAKONNA_POJISTOVNA_KEYS:
            continue
        row = dict(rows_by_key.get(obligation.key, {}))
        row.setdefault("key", obligation.key)
        if obligation.key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU:
            row["nazev"] = obligation.label
        else:
            row.setdefault("nazev", obligation.label)
        row.setdefault("section", obligation.section)

        if row_is_done(row):
            result.append(row)
            continue

        deadline = obligation_default_deadline(
            notification_date,
            obligation_key=obligation.key,
            section=obligation.section,
            label=obligation.label,
        )
        if deadline is not None:
            row["lhuta"] = deadline.isoformat()

        result.append(row)

    return result


def parse_saved_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        pass
    first_token = text.split()[0] if text else text
    for candidate in (first_token, text):
        for fmt in ("%d.%m.%Y", "%d. %m. %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except Exception:
                continue
    return None


def row_is_done(row: dict[str, Any]) -> bool:
    if row.get("predano"):
        return True
    if row.get("kompletni"):
        return True
    if row.get("datum"):
        return True
    return False


def dpn_record_update_overview_from_saved_data(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None,
    *,
    union_organization_active: bool | None = None,
) -> dict[str, Any]:
    """Souhrn záložky Po ukončení DPN.

    Provedení aktualizace čte z Ohlašovací povinnosti (Portál SÚIP).
    Podepsaný aktualizovaný záznam čte z evidovaného pole ``dpn_record_update``.
    """
    rows_by_key: dict[str, dict[str, Any]] = {}
    for row in obligation_rows_for_summary(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    ):
        key = obligation_key_from_row(row)
        if key:
            rows_by_key[key] = row

    portal_row = rows_by_key.get(OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL, {})
    portal_done = row_is_done(portal_row)
    stored = dpn_record_update_from_saved_data(saved_data)
    portal_date = parse_saved_date(portal_row.get("datum")) if portal_row else None
    if portal_date is None:
        portal_date = parse_saved_date(stored.get(DPN_RECORD_UPDATE_PORTAL_DATE))

    return normalize_dpn_record_update(
        {
            DPN_RECORD_UPDATE_PORTAL_DONE: portal_done,
            DPN_RECORD_UPDATE_PORTAL_DATE: portal_date,
            DPN_RECORD_UPDATE_SIGNED_DONE: stored[DPN_RECORD_UPDATE_SIGNED_DONE],
            DPN_RECORD_UPDATE_SIGNED_DATE: stored[DPN_RECORD_UPDATE_SIGNED_DATE],
        }
    )


def row_status(row: dict[str, Any], today: date) -> str:
    if row_is_done(row):
        return "done"
    deadline = parse_saved_date(row.get("lhuta"))
    if deadline is not None and deadline < today:
        return "overdue"
    return "waiting"


def row_is_overdue(row: dict[str, Any], today: date) -> bool:
    return row_status(row, today) == "overdue"


def obligations_summary_state(
    accident: AccidentLike | None,
    rows: list[dict[str, Any]],
    today: date,
    *,
    union_organization_active: bool | None = None,
    saved_data: dict[str, Any] | None = None,
    record_duty_generation: str | None = None,
) -> str | None:
    applicable = applicable_obligations(
        accident,
        union_organization_active=union_organization_active,
        saved_data=(
            saved_data
            if saved_data is not None
            else ({"admin_zaslani": rows} if rows else None)
        ),
        record_duty_generation=record_duty_generation,
    )
    if not applicable:
        return None

    rows_by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = obligation_key_from_row(row)
        if key:
            rows_by_key[key] = row

    statuses = [
        row_status(rows_by_key.get(obligation.key, {"key": obligation.key}), today)
        for obligation in applicable
        if obligation.key not in ZAKONNA_POJISTOVNA_KEYS
        and obligation.key != OBLIGATION_CSSZ_USSZ_NEMOCENSKE
    ]

    if "overdue" in statuses:
        return "overdue"
    if "waiting" in statuses:
        return "waiting"
    return "done"
