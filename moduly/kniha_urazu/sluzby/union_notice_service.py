"""Ohlášení pracovního úrazu odborové organizaci – NV 322/2025 Sb., příloha č. 2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import is_fatal_accident
from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
from moduly.nastaveni.sluzby.settings_service import settings_service

MISSING_MARKER = "[CHYBÍ]"
HISTORY_KEY = "union_notice_history"

ACTION_PREVIEW = "preview"
ACTION_PRINT = "print"
ACTION_PDF = "pdf"

ACTION_LABELS = {
    ACTION_PREVIEW: "Vytvořen pracovní náhled ohlášení odborové organizaci",
    ACTION_PRINT: "Vytištěno ohlášení odborové organizaci",
    ACTION_PDF: "Uloženo ohlášení odborové organizaci jako PDF",
}

DOCUMENT_TITLE = "OHLÁŠENÍ PRACOVNÍHO ÚRAZU"
DOCUMENT_SUBTITLE = "odborové organizaci"
DOCUMENT_LEGAL = "Podle § 5 odst. 2 a 5 nařízení vlády č. 322/2025 Sb."

RELATION_EMPLOYMENT = "pracovní poměr"
RELATION_SERVICE = "služební poměr"
RELATION_AGREEMENT = "dohoda o pracích konaných mimo pracovní poměr"
RELATION_OUTSIDE = (
    "osoba vykonávající činnosti nebo poskytující služby mimo pracovněprávní vztah "
    "podle § 12 zákona č. 309/2006 Sb."
)
RELATION_OTHER = "ostatní"

# Vztahy, u kterých je den vzniku právního vztahu povinný (II.g / body 1–3).
RELATIONS_WITH_START_DATE = frozenset(
    {RELATION_EMPLOYMENT, RELATION_SERVICE, RELATION_AGREEMENT}
)


@dataclass
class MissingItem:
    key: str
    label: str
    section: str
    kind: str  # "required" | "not_relevant"


@dataclass
class UnionNoticeData:
    """Jednorázová data ohlášení – nezávislá na uloženém úrazu."""

    accident_id: int = 0

    # I. Zaměstnavatel
    employer_name: str = ""
    employer_ico: str = ""
    employer_birth_date: str = ""
    employer_address: str = ""

    # II. Zaměstnanec
    employee_name: str = ""
    employee_birth_date: str = ""
    employee_gender: str = ""
    employee_citizenship: str = ""
    employee_residence: str = ""
    employee_delivery_address: str = ""
    employee_relation: str = ""
    employee_relation_start: str = ""

    # III–VI
    accident_place_address: str = ""
    workplace_characteristic: str = ""
    activity: str = ""
    cz_isco: str = ""

    # VII
    accident_date: str = ""
    accident_time: str = ""
    death_date: str = ""
    injury_type: str = ""
    body_part: str = ""
    injured_count: str = "1"
    mass_accident: str = ""
    is_fatal: bool = False

    # VIII
    description: str = ""

    # IX
    notifier_name: str = ""
    notifier_phone: str = ""
    notifier_email: str = ""
    notifier_position: str = ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fmt_date(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    text = _text(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except ValueError:
        return text


def normalize_employment_relation(raw: str) -> str:
    text = _text(raw).lower()
    if not text:
        return ""
    if "služebn" in text:
        return RELATION_SERVICE
    if "dohod" in text or "dpp" in text or "dpč" in text:
        return RELATION_AGREEMENT
    if "309/2006" in text or "mimo pracovněprávní" in text:
        return RELATION_OUTSIDE
    if "pracovní poměr" in text or text.startswith("v pracovním"):
        return RELATION_EMPLOYMENT
    if "ostatní" in text:
        return RELATION_OTHER
    # Legacy číselník – mapovat blízké hodnoty.
    if "pracovním poměru" in text:
        return RELATION_EMPLOYMENT
    if "fyzická osoba" in text or "zaměstnavatel, který" in text or "spolupracující" in text:
        return RELATION_OUTSIDE
    if "další členové" in text or "zadavatelem stavby" in text:
        return RELATION_OUTSIDE
    return RELATION_OTHER if text else ""


def _split_phone_email(raw: str) -> tuple[str, str]:
    text = _text(raw)
    if not text:
        return "", ""
    if "@" in text and ("," in text or ";" in text or " " in text):
        parts = [p.strip() for p in text.replace(";", ",").replace(" ", ",").split(",") if p.strip()]
        phones = [p for p in parts if "@" not in p]
        emails = [p for p in parts if "@" in p]
        return " ".join(phones), " ".join(emails)
    if "@" in text:
        return "", text
    return text, ""


def _cz_isco_display(accident) -> str:
    code = _text(getattr(accident, "cz_isco_kod", ""))
    name = _text(getattr(accident, "cz_isco_nazev", ""))
    kind = _text(getattr(accident, "druh_vykonavane_prace", ""))
    if code and name:
        return f"{code} – {name}"
    if kind:
        return kind
    if name:
        return name
    return code


def _build_description(accident) -> str:
    parts: list[str] = []
    deje = _text(getattr(accident, "popis_urazoveho_deje", ""))
    if deje:
        parts.append(deje)
    misto = _text(getattr(accident, "misto_urazu", "")) or _text(
        getattr(accident, "adresa_pracoviste", "")
    )
    if misto:
        parts.append(f"Místo: {misto}")
    pricina = _text(getattr(accident, "pricina_urazu", ""))
    if pricina:
        parts.append(f"Příčina: {pricina}")
    zdroj = _text(getattr(accident, "zdroj_urazu", ""))
    if zdroj:
        parts.append(f"Zdroj: {zdroj}")
    return "\n".join(parts)


class UnionNoticeService:
    def build_from_accident(self, accident) -> UnionNoticeData:
        employer = settings_service.get_employer()
        employer_name = _text(getattr(accident, "zamestnavatel_nazev", "")) or _text(
            getattr(employer, "name", "") if employer else ""
        )
        employer_ico = _text(getattr(accident, "zamestnavatel_ico", "")) or _text(
            getattr(employer, "ico", "") if employer else ""
        )
        employer_address = _text(getattr(accident, "zamestnavatel_adresa", "")) or _text(
            getattr(employer, "address", "") if employer else ""
        )

        phone, email = _split_phone_email(getattr(accident, "podatel_telefon", ""))
        if not email:
            email = _text(getattr(accident, "podatel_email", ""))
        if not phone:
            phone = _text(getattr(accident, "podatel_telefon", ""))
            if "@" in phone:
                phone = ""

        place = _text(getattr(accident, "adresa_pracoviste", "")) or _text(
            getattr(accident, "misto_urazu", "")
        )

        injured = getattr(accident, "celkovy_pocet_zranenych", None)
        injured_text = str(injured) if injured not in (None, "") else "1"

        mass = _text(getattr(accident, "hromadny_uraz", ""))
        if not mass:
            try:
                mass = "Ano" if int(injured_text or "1") > 1 else "Ne"
            except ValueError:
                mass = "Ne"

        return UnionNoticeData(
            accident_id=int(getattr(accident, "id", 0) or 0),
            employer_name=employer_name,
            employer_ico=employer_ico,
            employer_birth_date="",
            employer_address=employer_address,
            employee_name=_text(getattr(accident, "jmeno_prijmeni", ""))
            or _text(getattr(accident, "employee_name", "")),
            employee_birth_date=_fmt_date(getattr(accident, "datum_narozeni", None)),
            employee_gender=_text(getattr(accident, "pohlavi", "")),
            employee_citizenship=_text(getattr(accident, "statni_obcanstvi", "")),
            employee_residence=_text(getattr(accident, "adresa_pobytu", "")),
            employee_delivery_address=_text(getattr(accident, "adresa_dorucovani", "")),
            employee_relation=normalize_employment_relation(
                getattr(accident, "vztah_k_zamestnavateli", "")
            ),
            employee_relation_start=_fmt_date(
                getattr(accident, "den_vzniku_pravniho_vztahu", None)
            ),
            accident_place_address=place,
            workplace_characteristic=_text(
                getattr(accident, "charakteristika_pracoviste", "")
            ),
            activity=_text(getattr(accident, "cinnost_pri_urazu", "")),
            cz_isco=_cz_isco_display(accident),
            accident_date=_fmt_date(getattr(accident, "accident_date", None)),
            accident_time=_text(getattr(accident, "accident_time", "")),
            death_date="",
            injury_type=_text(getattr(accident, "druh_zraneni", ""))
            or _text(getattr(accident, "injury_type", "")),
            body_part=_text(getattr(accident, "zranena_cast_tela", ""))
            or _text(getattr(accident, "injured_body_part", "")),
            injured_count=injured_text,
            mass_accident=mass,
            is_fatal=is_fatal_accident(accident),
            description=_build_description(accident),
            notifier_name=_text(getattr(accident, "podatel_jmeno", "")),
            notifier_phone=phone or _text(getattr(accident, "podatel_telefon", "")),
            notifier_email=email,
            notifier_position=_text(getattr(accident, "podatel_pracovni_zarazeni", "")),
        )

    def validate(self, data: UnionNoticeData) -> list[MissingItem]:
        items: list[MissingItem] = []

        def req(key: str, label: str, section: str, value: str) -> None:
            if not _text(value):
                items.append(MissingItem(key, label, section, "required"))

        def na(key: str, label: str, section: str) -> None:
            items.append(MissingItem(key, label, section, "not_relevant"))

        # I
        req("employer_name", "Jméno zaměstnavatele", "I", data.employer_name)
        if not _text(data.employer_ico) and not _text(data.employer_birth_date):
            req(
                "employer_ico",
                "IČO nebo datum narození zaměstnavatele",
                "I",
                "",
            )
        req("employer_address", "Adresa sídla zaměstnavatele", "I", data.employer_address)

        # II
        req("employee_name", "Jméno zaměstnance", "II", data.employee_name)
        req("employee_birth_date", "Datum narození", "II", data.employee_birth_date)
        req("employee_gender", "Pohlaví", "II", data.employee_gender)
        req("employee_citizenship", "Státní občanství", "II", data.employee_citizenship)
        req("employee_residence", "Adresa místa pobytu", "II", data.employee_residence)

        delivery = _text(data.employee_delivery_address)
        residence = _text(data.employee_residence)
        if delivery and delivery.casefold() != residence.casefold():
            pass  # relevantní a vyplněné
        else:
            na(
                "employee_delivery_address",
                "Doručovací adresa (shodná s pobytem / nevyplněna)",
                "II",
            )

        req("employee_relation", "Vztah k zaměstnavateli", "II", data.employee_relation)
        relation = normalize_employment_relation(data.employee_relation) or _text(
            data.employee_relation
        )
        if relation in RELATIONS_WITH_START_DATE:
            req(
                "employee_relation_start",
                "Den vzniku právního vztahu",
                "II",
                data.employee_relation_start,
            )
        else:
            na(
                "employee_relation_start",
                "Den vzniku právního vztahu (u tohoto vztahu není vyžadován)",
                "II",
            )

        # III – jen pokud se liší od sídla
        place = _text(data.accident_place_address)
        seat = _text(data.employer_address)
        if place and seat and place.casefold() == seat.casefold():
            na(
                "accident_place_address",
                "Adresa místa úrazu (shodná se sídlem zaměstnavatele)",
                "III",
            )
        elif not place and seat:
            na(
                "accident_place_address",
                "Adresa místa úrazu (shodná se sídlem / nevyplněna)",
                "III",
            )
        else:
            req(
                "accident_place_address",
                "Adresa pracoviště nebo místa úrazu",
                "III",
                data.accident_place_address,
            )

        # IV–VI
        req(
            "workplace_characteristic",
            "Charakteristika místa",
            "IV",
            data.workplace_characteristic,
        )
        req("activity", "Činnost při úrazu", "V", data.activity)
        req("cz_isco", "Druh vykonávané práce (CZ-ISCO)", "VI", data.cz_isco)

        # VII
        req("accident_date", "Datum pracovního úrazu", "VII", data.accident_date)
        req("accident_time", "Čas pracovního úrazu", "VII", data.accident_time)
        if data.is_fatal:
            req("death_date", "Datum úmrtí", "VII", data.death_date)
        else:
            na("death_date", "Datum úmrtí (nejde o smrtelný úraz)", "VII")
        req("injury_type", "Druh zranění", "VII", data.injury_type)
        req("body_part", "Zraněná část těla", "VII", data.body_part)
        req("injured_count", "Počet zraněných osob", "VII", data.injured_count)
        req("mass_accident", "Hromadný pracovní úraz", "VII", data.mass_accident)

        # VIII–IX
        req("description", "Popis pracovního úrazu", "VIII", data.description)
        req("notifier_name", "Jméno oznamující osoby", "IX", data.notifier_name)
        req("notifier_phone", "Telefon oznamující osoby", "IX", data.notifier_phone)
        req("notifier_email", "E-mail oznamující osoby", "IX", data.notifier_email)
        req(
            "notifier_position",
            "Pracovní zařazení oznamující osoby",
            "IX",
            data.notifier_position,
        )

        return items

    def required_missing(self, data: UnionNoticeData) -> list[MissingItem]:
        return [item for item in self.validate(data) if item.kind == "required"]

    def display_value(self, value: str, *, draft: bool, required: bool) -> str:
        text = _text(value)
        if text:
            return text
        if draft and required:
            return MISSING_MARKER
        return "—" if draft else ""

    def build_html(self, data: UnionNoticeData, *, draft: bool = False) -> str:
        missing_keys = {item.key for item in self.required_missing(data)}

        def v(key: str, value: str) -> str:
            return self.display_value(
                value, draft=draft, required=key in missing_keys
            )

        rows_i = [
            ("Jméno", v("employer_name", data.employer_name)),
            (
                "IČO / datum narození",
                v(
                    "employer_ico",
                    data.employer_ico or data.employer_birth_date,
                ),
            ),
            ("Adresa sídla / místa pobytu", v("employer_address", data.employer_address)),
        ]
        rows_ii = [
            ("Jméno", v("employee_name", data.employee_name)),
            ("Datum narození", v("employee_birth_date", data.employee_birth_date)),
            ("Pohlaví", v("employee_gender", data.employee_gender)),
            ("Státní občanství", v("employee_citizenship", data.employee_citizenship)),
            ("Adresa místa pobytu", v("employee_residence", data.employee_residence)),
            (
                "Adresa pro doručování",
                _text(data.employee_delivery_address)
                if _text(data.employee_delivery_address)
                and _text(data.employee_delivery_address).casefold()
                != _text(data.employee_residence).casefold()
                else ("není odlišná" if not draft else "není odlišná"),
            ),
            ("Vztah k zaměstnavateli", v("employee_relation", data.employee_relation)),
            (
                "Den vzniku právního vztahu",
                v("employee_relation_start", data.employee_relation_start)
                if (
                    normalize_employment_relation(data.employee_relation)
                    in RELATIONS_WITH_START_DATE
                    or _text(data.employee_relation_start)
                )
                else "není vyžadován",
            ),
        ]
        place_same = (
            _text(data.accident_place_address)
            and _text(data.employer_address)
            and _text(data.accident_place_address).casefold()
            == _text(data.employer_address).casefold()
        ) or (
            not _text(data.accident_place_address) and _text(data.employer_address)
        )
        rows_iii = [
            (
                "Adresa místa úrazu",
                "shodná se sídlem zaměstnavatele"
                if place_same
                else v("accident_place_address", data.accident_place_address),
            )
        ]
        rows_iv = [
            (
                "Charakteristika místa",
                v("workplace_characteristic", data.workplace_characteristic),
            )
        ]
        rows_v = [("Činnost", v("activity", data.activity))]
        rows_vi = [("CZ-ISCO", v("cz_isco", data.cz_isco))]
        rows_vii = [
            ("Datum úrazu", v("accident_date", data.accident_date)),
            ("Čas úrazu", v("accident_time", data.accident_time)),
            (
                "Datum úmrtí",
                v("death_date", data.death_date)
                if data.is_fatal
                else "není relevantní",
            ),
            ("Druh zranění", v("injury_type", data.injury_type)),
            ("Zraněná část těla", v("body_part", data.body_part)),
            ("Počet zraněných osob", v("injured_count", data.injured_count)),
            ("Hromadný pracovní úraz", v("mass_accident", data.mass_accident)),
        ]
        rows_viii = [("Popis", v("description", data.description))]
        rows_ix = [
            ("Jméno", v("notifier_name", data.notifier_name)),
            ("Telefon", v("notifier_phone", data.notifier_phone)),
            ("E-mail", v("notifier_email", data.notifier_email)),
            ("Pracovní zařazení", v("notifier_position", data.notifier_position)),
        ]

        sections = [
            ("I. Údaje o zaměstnavateli úrazem postiženého zaměstnance", rows_i),
            ("II. Údaje o úrazem postiženém zaměstnanci", rows_ii),
            (
                "III. Adresa pracoviště nebo jiného místa, kde k pracovnímu úrazu došlo",
                rows_iii,
            ),
            ("IV. Charakteristika místa", rows_iv),
            ("V. Činnost, při které k pracovnímu úrazu došlo", rows_v),
            ("VI. Druh vykonávané práce podle CZ-ISCO", rows_vi),
            ("VII. Údaje o pracovním úrazu", rows_vii),
            ("VIII. Popis pracovního úrazu", rows_viii),
            ("IX. Osoba oznamující pracovní úraz za zaměstnavatele", rows_ix),
        ]

        draft_banner = ""
        if draft and missing_keys:
            draft_banner = (
                "<p style='color:#b45309;font-weight:bold;'>"
                "Pracovní náhled – chybějící povinné údaje jsou označeny "
                f"{MISSING_MARKER}."
                "</p>"
            )

        body_parts: list[str] = []
        for title, rows in sections:
            body_parts.append(f"<h2>{_escape(title)}</h2>")
            body_parts.append("<table>")
            for label, value in rows:
                style = (
                    " style='color:#b91c1c;font-weight:bold;'"
                    if value == MISSING_MARKER
                    else ""
                )
                body_parts.append(
                    "<tr>"
                    f"<td style='width:38%;vertical-align:top;padding:3px 8px 3px 0;'>"
                    f"<b>{_escape(label)}</b></td>"
                    f"<td style='vertical-align:top;padding:3px 0;'{style}>"
                    f"{_escape(value).replace(chr(10), '<br/>')}</td>"
                    "</tr>"
                )
            body_parts.append("</table>")

        return (
            "<html><head><meta charset='utf-8'></head><body "
            "style='font-family:serif;font-size:11pt;'>"
            f"<h1 style='text-align:center;margin-bottom:4px;'>{DOCUMENT_TITLE}</h1>"
            f"<h2 style='text-align:center;margin-top:0;'>{DOCUMENT_SUBTITLE}</h2>"
            f"<p style='text-align:center;'><i>{DOCUMENT_LEGAL}</i></p>"
            f"{draft_banner}"
            + "".join(body_parts)
            + "</body></html>"
        )

    def record_history(
        self,
        accident_id: int,
        *,
        action: str,
        notifier_name: str = "",
    ) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        try:
            data = json.loads(investigation.zajisteni_dukazu_json or "{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        history = list(data.get(HISTORY_KEY) or [])
        entry = {
            "action": action,
            "label": ACTION_LABELS.get(action, action),
            "at": datetime.now().isoformat(timespec="seconds"),
            "notifier": _text(notifier_name),
        }
        history.append(entry)
        data[HISTORY_KEY] = history
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(data, ensure_ascii=False),
        )
        return entry

    def get_history(self, accident_id: int) -> list[dict]:
        investigation = investigation_service.get_or_create(accident_id)
        try:
            data = json.loads(investigation.zajisteni_dukazu_json or "{}")
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        history = data.get(HISTORY_KEY) or []
        return list(history) if isinstance(history, list) else []

    def write_pdf(self, html: str, path: Path) -> Path:
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        document = QTextDocument()
        document.setHtml(html)
        document.print_(printer)
        return path


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


union_notice_service = UnionNoticeService()
