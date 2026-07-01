from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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
OBLIGATION_EZOP = "ezop"
OBLIGATION_VYHOTOVENI_ZAZNAMU = "vyhotoveni_zaznamu"
OBLIGATION_OIP_OBU_ZASLANI = "oip_obu_zaslani"
OBLIGATION_ZP_ZASLANI = "zp_zaslani"
OBLIGATION_POLICIE_ZASLANI = "policie_zaslani"

SECTION_OHLASENI = "ohlaseni"
SECTION_ZAZNAM = "zaznam"
SECTION_ODESLANI = "odeslani"

OBLIGATION_LABELS: dict[str, str] = {
    OBLIGATION_OO_OHLASENI: "Odborová organizace – ohlášení pracovního úrazu",
    OBLIGATION_OIP_OBU_OHLASENI: "OIP / OBÚ – ohlášení závažného nebo smrtelného pracovního úrazu",
    OBLIGATION_POLICIE_OHLASENI: "Policie ČR – ohlášení smrtelného pracovního úrazu / podezření na trestný čin",
    OBLIGATION_ZP_OHLASENI: "Zdravotní pojišťovna postiženého – ohlášení smrtelného pracovního úrazu",
    OBLIGATION_EZOP: "EZOP – ohlášení pracovního úrazu",
    OBLIGATION_VYHOTOVENI_ZAZNAMU: "Vyhotovení Záznamu o pracovním úrazu",
    OBLIGATION_OIP_OBU_ZASLANI: "OIP / OBÚ – zaslání záznamu o pracovním úrazu",
    OBLIGATION_ZP_ZASLANI: "Zdravotní pojišťovna postiženého – zaslání záznamu o pracovním úrazu",
    OBLIGATION_POLICIE_ZASLANI: "Policie ČR – zaslání záznamu o pracovním úrazu",
}

LEGACY_LABEL_ALIASES: dict[str, str] = {
    "Záznam o pracovním úrazu – Portál SÚIP": OBLIGATION_VYHOTOVENI_ZAZNAMU,
    "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu": "",
    "Odborová organizace – předání podepsaného záznamu o pracovním úrazu": "",
    "Kooperativa": "",
}


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
    dpn_od = getattr(accident, "dpn_od", None)
    dpn_do = getattr(accident, "dpn_do", None)
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


def requires_accident_record(accident: AccidentLike | None) -> bool:
    return is_fatal_accident(accident) or has_pn_over_3_days(accident)


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
    return ""


def is_obligation_relevant(
    accident: AccidentLike | None,
    obligation_key: str,
    *,
    union_organization_active: bool | None = None,
) -> bool:
    if not obligation_key:
        return False

    union_active = (
        employer_union_organization_active()
        if union_organization_active is None
        else union_organization_active
    )

    if obligation_key == OBLIGATION_OO_OHLASENI:
        return union_active

    if obligation_key == OBLIGATION_OIP_OBU_OHLASENI:
        return is_serious_or_fatal_accident(accident)

    if obligation_key == OBLIGATION_POLICIE_OHLASENI:
        return requires_police_obligation(accident)

    if obligation_key == OBLIGATION_ZP_OHLASENI:
        return is_fatal_accident(accident)

    if obligation_key == OBLIGATION_EZOP:
        return requires_accident_record(accident)

    if obligation_key == OBLIGATION_VYHOTOVENI_ZAZNAMU:
        return requires_accident_record(accident)

    if not requires_accident_record(accident):
        return False

    if obligation_key == OBLIGATION_OIP_OBU_ZASLANI:
        return is_serious_or_fatal_accident(accident)

    if obligation_key == OBLIGATION_ZP_ZASLANI:
        return True

    if obligation_key == OBLIGATION_POLICIE_ZASLANI:
        return requires_police_obligation(accident)

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
        if key == OBLIGATION_VYHOTOVENI_ZAZNAMU:
            section = SECTION_ZAZNAM
        elif key in {
            OBLIGATION_OIP_OBU_ZASLANI,
            OBLIGATION_ZP_ZASLANI,
            OBLIGATION_POLICIE_ZASLANI,
        }:
            section = SECTION_ODESLANI
        else:
            section = SECTION_OHLASENI
        items.append(ReportingObligation(key=key, section=section, label=label))
    return items


def all_obligation_definitions() -> list[ReportingObligation]:
    items: list[ReportingObligation] = []
    for key, label in OBLIGATION_LABELS.items():
        if key == OBLIGATION_VYHOTOVENI_ZAZNAMU:
            section = SECTION_ZAZNAM
        elif key in {
            OBLIGATION_OIP_OBU_ZASLANI,
            OBLIGATION_ZP_ZASLANI,
            OBLIGATION_POLICIE_ZASLANI,
        }:
            section = SECTION_ODESLANI
        else:
            section = SECTION_OHLASENI
        items.append(ReportingObligation(key=key, section=section, label=label))
    return items
