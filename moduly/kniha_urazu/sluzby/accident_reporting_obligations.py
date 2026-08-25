from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol


class AccidentLike(Protocol):
    druh_urazu: str
    podezreni_trestny_cin: str
    dpn_od: date | None
    dpn_do: date | None


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

SECTION_OHLASENI = "ohlaseni"
SECTION_ZAZNAM = "zaznam"
SECTION_ODESLANI = "odeslani"
SECTION_PREDANI = "predani"

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
    OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU: "Vyhotovení + zaslání záznamu o pracovním úrazu",
    OBLIGATION_OIP_OBU_ZASLANI: "OIP / OBÚ – zaslání záznamu o pracovním úrazu",
    OBLIGATION_POLICIE_ZASLANI: "Policie ČR – zaslání záznamu o pracovním úrazu",
    OBLIGATION_ZP_ZASLANI: "Zdravotní pojišťovna postiženého – zaslání záznamu o pracovním úrazu",
    OBLIGATION_EZOP: "EZOP – ohlášení pracovního úrazu",
    OBLIGATION_ZAMESTNANEC_PREDANI: "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu",
    OBLIGATION_OO_PREDANI: "Odborová organizace – předání podepsaného záznamu o pracovním úrazu",
    OBLIGATION_RODINA_PREDANI: "Rodinní příslušníci – předání záznamu o pracovním úrazu",
}

LEGACY_LABEL_ALIASES: dict[str, str] = {
    "Záznam o pracovním úrazu – Portál SÚIP": OBLIGATION_VYHOTOVENI_ZAZNAMU,
    "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu": OBLIGATION_ZAMESTNANEC_PREDANI,
    "Odborová organizace – předání podepsaného záznamu o pracovním úrazu": OBLIGATION_OO_PREDANI,
    "Kooperativa": "",
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
    return is_fatal_accident(accident) or is_criminal_suspicion(accident)


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


def _section_for_key(key: str) -> str:
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
    skip = record_duty_keys_hidden_for_generation(generation)
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
        row = dict(rows_by_key.get(obligation.key, {}))
        row.setdefault("key", obligation.key)
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
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def row_is_done(row: dict[str, Any]) -> bool:
    if row.get("predano"):
        return True
    if row.get("kompletni"):
        return True
    if row.get("datum"):
        return True
    return False


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
    ]

    if "overdue" in statuses:
        return "overdue"
    if "waiting" in statuses:
        return "waiting"
    return "done"
