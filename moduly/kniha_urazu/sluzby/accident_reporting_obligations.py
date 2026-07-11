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
) -> bool:
    if not obligation_key:
        return False

    category = accident_category(accident)
    union_active = (
        employer_union_organization_active()
        if union_organization_active is None
        else union_organization_active
    )

    if obligation_key == OBLIGATION_OO_OHLASENI:
        return union_active

    if obligation_key == OBLIGATION_OIP_OBU_OHLASENI:
        return category in {CATEGORY_SERIOUS, CATEGORY_FATAL}

    if obligation_key == OBLIGATION_POLICIE_OHLASENI:
        return requires_police_obligation(accident)

    if obligation_key == OBLIGATION_ZP_OHLASENI:
        return category == CATEGORY_FATAL

    if obligation_key in {
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_OIP_OBU_ZASLANI,
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
) -> bool:
    return is_obligation_relevant(
        accident,
        obligation_key_from_row(row),
        union_organization_active=union_organization_active,
    )


def _section_for_key(key: str) -> str:
    if key == OBLIGATION_VYHOTOVENI_ZAZNAMU:
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
) -> list[ReportingObligation]:
    items: list[ReportingObligation] = []
    for key, label in OBLIGATION_LABELS.items():
        if not is_obligation_relevant(
            accident,
            key,
            union_organization_active=union_organization_active,
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


def collect_obligation_rows_from_saved_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    rows: list[dict[str, Any]] = []
    rows.extend(data.get("admin_ohlaseni") or [])
    rows.extend(data.get("admin_zaslani") or [])
    return rows


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

    if section == SECTION_OHLASENI or agenda == "ohlaseni":
        return add_workdays(notification_date, 1)

    if section in {SECTION_ZAZNAM, SECTION_ODESLANI, SECTION_PREDANI}:
        return add_workdays(notification_date, 15)

    if "Vyhotovení Záznamu" in label or "Záznam o pracovním úrazu" in label:
        return add_workdays(notification_date, 15)

    return None


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
) -> str | None:
    applicable = applicable_obligations(
        accident,
        union_organization_active=union_organization_active,
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
