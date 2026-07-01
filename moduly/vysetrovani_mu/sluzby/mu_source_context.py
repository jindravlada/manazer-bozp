from dataclasses import dataclass
from datetime import date

from moduly.vysetrovani_mu.constants import (
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPES_WITH_TEXT,
)


@dataclass
class MuSourceContext:
    event_number: str = ""
    affected_person_html: str = ""
    source_record_html: str = ""
    event_datum: date | None = None
    event_cas: str = ""
    default_oznameni_kdo: str = ""
    default_oznameni_komu: str = ""
    default_oznameni_datum: date | None = None
    default_oznameni_cas: str = ""
    default_oznameni_popis: str = ""


def _normalize_time_text(value) -> str:
    if isinstance(value, int):
        if 0 <= value <= 2359:
            hours = value // 100
            minutes = value % 100
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
        value = str(value)

    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(".", ":")
    parts = text.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return text


def resolve_mu_source_context(
    source_type: str,
    source_id: int | None,
    source_label: str = "",
    investigation_number: str = "",
) -> MuSourceContext:
    if source_type == SOURCE_TYPE_ACCIDENT:
        return _context_from_accident(source_id)
    if source_type == SOURCE_TYPE_AUDIT:
        return _context_from_audit(source_id)
    if source_type == SOURCE_TYPE_CONTROL:
        return _context_from_control(source_id)
    if source_type in SOURCE_TYPES_WITH_TEXT:
        return MuSourceContext(
            event_number=investigation_number.strip(),
            source_record_html=(source_label or "").strip(),
        )
    return MuSourceContext(event_number=investigation_number.strip())


def _context_from_accident(source_id: int | None) -> MuSourceContext:
    if not isinstance(source_id, int) or source_id <= 0:
        return MuSourceContext()

    from moduly.kniha_urazu.sluzby.accident_service import accident_service

    accident = accident_service.get_by_id(source_id)
    if accident is None:
        return MuSourceContext()

    datum_urazu = accident.accident_date.strftime("%d.%m.%Y") if accident.accident_date else ""
    event_cas = _normalize_time_text(accident.accident_time)
    workplace = (accident.workplace_name or accident.pracoviste or "").strip()
    affected_person_html = (
        f"<b>Dotčená osoba:</b> {accident.employee_name or ''}<br>"
        f"<b>Pracovní pozice:</b> {accident.druh_vykonavane_prace or ''}<br>"
        f"<b>Pracoviště:</b> {workplace}"
    )
    source_record_html = (
        f"<b>Datum události:</b> {datum_urazu}<br>"
        f"<b>Čas události:</b> {event_cas}<br>"
        f"<b>Místo události:</b> {accident.misto_urazu or ''}<br>"
        f"<b>Druh poškození:</b> {accident.druh_zraneni or ''}"
    )

    return MuSourceContext(
        event_number=accident.number or "",
        affected_person_html=affected_person_html,
        source_record_html=source_record_html,
        event_datum=accident.accident_date,
        event_cas=event_cas,
        default_oznameni_kdo=(accident.employee_name or "").strip(),
        default_oznameni_komu=(accident.zapsal_jmeno or "").strip(),
        default_oznameni_datum=accident.accident_date,
        default_oznameni_cas=event_cas,
        default_oznameni_popis=(accident.popis_urazoveho_deje or "").strip(),
    )


def _context_from_audit(source_id: int | None) -> MuSourceContext:
    if not isinstance(source_id, int) or source_id <= 0:
        return MuSourceContext()

    from moduly.audity.sluzby.audit_service import audit_service

    audit = audit_service.get_by_id(source_id)
    if audit is None:
        return MuSourceContext()

    audit_date = audit.audit_date.strftime("%d.%m.%Y") if audit.audit_date else ""
    source_record_html = (
        f"<b>Číslo auditu:</b> {audit.number or ''}<br>"
        f"<b>Název:</b> {audit.title or ''}<br>"
        f"<b>Datum auditu:</b> {audit_date}<br>"
        f"<b>Auditovaný provoz:</b> {audit.workplace_name or ''}<br>"
        f"<b>Stav:</b> {audit.status or ''}"
    )

    return MuSourceContext(
        event_number=audit.number or "",
        source_record_html=source_record_html,
        default_oznameni_popis=(audit.title or "").strip(),
    )


def _context_from_control(source_id: int | None) -> MuSourceContext:
    if not isinstance(source_id, int) or source_id <= 0:
        return MuSourceContext()

    from moduly.kontroly.sluzby.control_service import control_service

    control = control_service.get_by_id(source_id)
    if control is None:
        return MuSourceContext()

    inspection_date = control.inspection_date.strftime("%d.%m.%Y") if control.inspection_date else ""
    source_record_html = (
        f"<b>Název kontroly:</b> {control.title or ''}<br>"
        f"<b>Datum kontroly:</b> {inspection_date}<br>"
        f"<b>Pracoviště:</b> {control.workplace_name or ''}<br>"
        f"<b>Kontrolující:</b> {control.inspector_name or ''}<br>"
        f"<b>Výsledek:</b> {control.result or ''}"
    )
    if (control.note or "").strip():
        source_record_html = f"{source_record_html}<br><b>Poznámka:</b> {control.note.strip()}"

    return MuSourceContext(
        event_number=str(control.id),
        source_record_html=source_record_html,
        default_oznameni_popis=(control.note or "").strip(),
    )
