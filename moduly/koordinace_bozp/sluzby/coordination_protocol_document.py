"""Společný model dokumentu koordinačního protokolu (BUILDER-COORD-1 / 1a)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_OTHER,
    PROTOCOL_AGREEMENT_CLOSING,
    PROTOCOL_APPENDIX_A,
    PROTOCOL_APPENDIX_B,
    PROTOCOL_APPENDIX_C,
    PROTOCOL_APPENDIX_C_INTRO,
    PROTOCOL_APPENDIX_OVERVIEW,
    PROTOCOL_APPENDIX_OVERVIEW_INTRO,
    PROTOCOL_CONCLUSION_1_TITLE,
    PROTOCOL_CONCLUSION_2_TITLE,
    PROTOCOL_CONCLUSION_3_OOPP_INTRO,
    PROTOCOL_CONCLUSION_4_COORDINATOR_INTRO,
    PROTOCOL_CONCLUSION_5_TITLE,
    PROTOCOL_CONCLUSION_6_TITLE,
    PROTOCOL_CONCLUSION_7_TITLE,
    PROTOCOL_CONCLUSION_8_TITLE,
    PROTOCOL_COORDINATOR_AGREEMENT_CHANGE,
    PROTOCOL_COORDINATOR_ALIAS,
    PROTOCOL_COORDINATOR_DETAILS_TITLE,
    PROTOCOL_COORDINATOR_DUTIES,
    PROTOCOL_COORDINATOR_NOMINATION,
    PROTOCOL_COORDINATOR_OBLIGATION,
    PROTOCOL_COORDINATOR_TRAINING,
    PROTOCOL_COORDINATOR_TRAINING_CHECK,
    PROTOCOL_FINAL_PROVISIONS_CONTINUATION,
    PROTOCOL_FINAL_PROVISIONS_COPIES,
    PROTOCOL_INTRO_EMPLOYERS,
    PROTOCOL_MAIN_RISKS_VIA_PBP,
    PROTOCOL_PBP_TITLE_TEMPLATE,
    PROTOCOL_SECTION_ACTIVITIES,
    PROTOCOL_SECTION_BASICS,
    PROTOCOL_SECTION_CONCLUSIONS,
    PROTOCOL_SECTION_PARTICIPANTS,
    PROTOCOL_SECTION_WORKPLACES,
    PROTOCOL_SUBTITLE,
    PROTOCOL_TITLE,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    CONTACT_EMPLOYER_UNSPECIFIED,
)


def _protocol_measure_display_text(measure: Mapping[str, Any]) -> str:
    description = (measure.get("description") or "").strip()
    if description:
        return description
    return (measure.get("title") or "").strip() or "—"


BLOCK_KIND_TITLE = "title"
BLOCK_KIND_SUBTITLE = "subtitle"
BLOCK_KIND_HEADING = "heading"
BLOCK_KIND_NUMBERED_HEADING = "numbered_heading"
BLOCK_KIND_PARAGRAPH = "paragraph"
BLOCK_KIND_BULLET = "bullet"
BLOCK_KIND_INDENTED = "indented"
BLOCK_KIND_BLANK = "blank"
BLOCK_KIND_SIGNATURE_LINE = "signature_line"
BLOCK_KIND_PBP_RULE = "pbp_rule"

BLOCK_STYLE_TITLE = "title"
BLOCK_STYLE_HEADING = "heading"
BLOCK_STYLE_BODY = "body"
BLOCK_STYLE_BULLET = "bullet"
BLOCK_STYLE_EMPLOYER_ABBR = "employer_abbr"
BLOCK_STYLE_EMPLOYER_NAME = "employer_name"
BLOCK_STYLE_LABEL = "label"
BLOCK_STYLE_INDENTED = "indented"
BLOCK_STYLE_PBP_RULE = "pbp_rule"
BLOCK_STYLE_COORDINATOR = "coordinator"

_SIGNATURE_DOTS = ".............................................."
_PPE_LETTERED_RE = re.compile(
    r"(?:^|\n)\s*[a-z]\)\s+",
    re.IGNORECASE,
)
_PPE_INLINE_LETTERED_RE = re.compile(r"\b[a-z]\)\s+", re.IGNORECASE)
_PBP_RULE_RE = re.compile(r"^(\d+)\.\s+(.*)$")


@dataclass(frozen=True)
class ProtocolDocumentBlock:
    kind: str
    text: str = ""
    level: int = 0
    style: str = BLOCK_STYLE_BODY
    bold: bool = False
    runs: tuple[tuple[str, bool], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["runs"] = [[text, bold] for text, bold in self.runs]
        return data


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    parts = str(value).split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return str(value)


def _display_or_dash(value: str | None) -> str:
    text = (value or "").strip()
    return text or "—"


def _employer_abbr_and_name(employer: Mapping[str, Any] | None) -> tuple[str, str]:
    """Vrátí (zkratka, název) pro dvouřádkové zobrazení zaměstnavatele."""
    employer = employer or {}
    abbr = (employer.get("abbreviation") or "").strip()
    name = (employer.get("company_name") or "").strip()
    if not name:
        display = (employer.get("display_name") or "").strip()
        if " – " in display:
            left, right = display.split(" – ", 1)
            abbr = abbr or left.strip()
            name = right.strip()
        elif " - " in display and not abbr:
            left, right = display.split(" - ", 1)
            abbr = left.strip()
            name = right.strip()
        else:
            name = display
    if abbr and name == abbr:
        name = ""
    return abbr, name


def parse_ppe_items(text: str | None) -> list[str]:
    """Rozdělí text OOPP na položky (a)/b)/c) nebo řádky → odrážky)."""
    raw = (text or "").strip()
    if not raw:
        return []
    if _PPE_LETTERED_RE.search(raw) or (
        _PPE_INLINE_LETTERED_RE.search(raw) and raw.count(")") >= 2
    ):
        parts = _PPE_INLINE_LETTERED_RE.split(raw)
        return [part.strip().rstrip("; ") for part in parts if part.strip()]
    items: list[str] = []
    for line in raw.splitlines():
        item = re.sub(r"^[\s•\-–*]+\s*", "", line.strip())
        item = re.sub(r"^[a-z]\)\s+", "", item, flags=re.IGNORECASE)
        item = re.sub(r"^\d+[.)]\s+", "", item)
        if item:
            items.append(item)
    return items if items else [raw]


class _BlockList:
    def __init__(self) -> None:
        self._blocks: list[ProtocolDocumentBlock] = []

    def extend(self, blocks: list[ProtocolDocumentBlock]) -> None:
        self._blocks.extend(blocks)

    def title(self, text: str) -> None:
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_TITLE, text, style=BLOCK_STYLE_TITLE)
        )

    def subtitle(self, text: str) -> None:
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_SUBTITLE, text, style=BLOCK_STYLE_BODY)
        )

    def heading(self, text: str) -> None:
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_HEADING, text, style=BLOCK_STYLE_HEADING)
        )

    def numbered_heading(self, number: int, text: str) -> None:
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_NUMBERED_HEADING,
                text,
                level=number,
                style=BLOCK_STYLE_HEADING,
            )
        )

    def paragraph(
        self,
        text: str,
        *,
        bold: bool = False,
        style: str = BLOCK_STYLE_BODY,
        runs: tuple[tuple[str, bool], ...] = (),
    ) -> None:
        if not (text or "").strip() and not runs:
            return
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_PARAGRAPH,
                text,
                style=style,
                bold=bold,
                runs=runs,
            )
        )

    def label(self, text: str) -> None:
        if not (text or "").strip():
            return
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_PARAGRAPH,
                text,
                style=BLOCK_STYLE_LABEL,
                bold=True,
            )
        )

    def employer_heading(self, employer: Mapping[str, Any] | None) -> None:
        """Nadpis skupiny: pouze tučná zkratka (bez opakování celého názvu)."""
        abbr, name = _employer_abbr_and_name(employer)
        label = abbr or name or "—"
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_PARAGRAPH,
                label,
                style=BLOCK_STYLE_EMPLOYER_ABBR,
                bold=True,
            )
        )

    def employer_label_line(self, label: str) -> None:
        text = (label or "").strip()
        if not text or text == CONTACT_EMPLOYER_UNSPECIFIED:
            return
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_PARAGRAPH,
                text,
                style=BLOCK_STYLE_EMPLOYER_ABBR,
                bold=True,
            )
        )

    def bullet(self, text: str) -> None:
        if not (text or "").strip():
            return
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_BULLET, text, style=BLOCK_STYLE_BULLET)
        )

    def indented(self, text: str) -> None:
        if not (text or "").strip():
            return
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_INDENTED,
                text,
                style=BLOCK_STYLE_INDENTED,
            )
        )

    def blank(self) -> None:
        self._blocks.append(ProtocolDocumentBlock(BLOCK_KIND_BLANK))

    def signature_line(self, text: str = _SIGNATURE_DOTS) -> None:
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_SIGNATURE_LINE,
                text,
                style=BLOCK_STYLE_BODY,
            )
        )

    def pbp_rule(self, number: int, text: str) -> None:
        body = (text or "").strip()
        prefix = f"{number}. "
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_PBP_RULE,
                f"{prefix}{body}" if body else prefix.strip(),
                level=number,
                style=BLOCK_STYLE_PBP_RULE,
                runs=((prefix, True), (body, False)) if body else ((prefix.strip(), True),),
            )
        )

    def build(self) -> list[ProtocolDocumentBlock]:
        return list(self._blocks)


def render_blocks_to_plain_lines(
    blocks: list[ProtocolDocumentBlock] | list[dict] | None,
) -> list[str]:
    """Plochý text dokumentu pro testy a porovnání Preview / ODT."""
    lines: list[str] = []
    for block in blocks or []:
        if isinstance(block, Mapping):
            kind = block.get("kind") or ""
            text = (block.get("text") or "").strip()
            level = int(block.get("level") or 0)
            runs = block.get("runs") or ()
        else:
            kind = block.kind
            text = (block.text or "").strip()
            level = block.level
            runs = block.runs
        if kind == BLOCK_KIND_BLANK:
            lines.append("")
            continue
        if kind == BLOCK_KIND_NUMBERED_HEADING:
            lines.append(f"{level}. {text}" if text else f"{level}.")
            continue
        if kind == BLOCK_KIND_BULLET:
            lines.append(f"• {text}" if text else "•")
            continue
        if kind == BLOCK_KIND_INDENTED:
            lines.append(f"  {text}" if text else "")
            continue
        if kind == BLOCK_KIND_PBP_RULE:
            if runs:
                lines.append("".join(str(item[0]) for item in runs))
            elif text:
                lines.append(text)
            continue
        if runs:
            lines.append("".join(str(item[0]) for item in runs))
            continue
        if text:
            lines.append(text)
    return lines


def document_blocks_from_dict(
    data: Mapping[str, Any] | None,
) -> list[ProtocolDocumentBlock]:
    blocks = (data or {}).get("blocks") or []
    result: list[ProtocolDocumentBlock] = []
    for item in blocks:
        if isinstance(item, ProtocolDocumentBlock):
            result.append(item)
        elif isinstance(item, Mapping):
            raw_runs = item.get("runs") or ()
            runs = tuple(
                (str(run[0]), bool(run[1]))
                for run in raw_runs
                if isinstance(run, (list, tuple)) and len(run) >= 2
            )
            result.append(
                ProtocolDocumentBlock(
                    kind=str(item.get("kind") or BLOCK_KIND_PARAGRAPH),
                    text=str(item.get("text") or ""),
                    level=int(item.get("level") or 0),
                    style=str(item.get("style") or BLOCK_STYLE_BODY),
                    bold=bool(item.get("bold")),
                    runs=runs,
                )
            )
    return result


def _employer_protocol_line(employer: Mapping[str, Any], index: int) -> str:
    name = (employer.get("company_name") or employer.get("display_name") or "—").strip()
    ico = (employer.get("ico") or "").strip()
    address = (employer.get("address") or "").strip()
    abbr = (employer.get("abbreviation") or "").strip()
    parts = [name]
    if ico:
        parts.append(f"IČO {ico}")
    if address:
        parts.append(address)
    line = ", ".join(parts)
    if abbr:
        line = f"{line} (dále též {abbr})"
    return f"{index}) {line}"


def _person_display_name(
    *,
    full_name: str | None = None,
    role: str | None = None,
) -> str:
    """Jméno – funkce; bez pomlčky, pokud chybí jméno."""
    name = (full_name or "").strip()
    role_text = (role or "").strip()
    if name and role_text:
        return f"{name} – {role_text}"
    if name:
        return name
    if role_text:
        return role_text
    return "—"


def _participant_bullet(participant: Mapping[str, Any]) -> str:
    detail = _person_display_name(
        full_name=participant.get("full_name"),
        role=participant.get("role"),
    )
    extras = []
    phone = (participant.get("phone") or "").strip()
    email = (participant.get("email") or "").strip()
    if phone:
        extras.append(phone)
    if email:
        extras.append(email)
    if extras:
        detail = f"{detail} ({', '.join(extras)})"
    return detail


def _append_contact_blocks(out: _BlockList, contact: Mapping[str, Any]) -> None:
    name = (contact.get("custom_name") or "").strip()
    role = (contact.get("role") or "").strip()
    if name:
        out.bullet(name)
        if role:
            out.indented(role)
    elif role:
        out.bullet(role)
    else:
        out.bullet("—")
    phone = (contact.get("phone") or "").strip()
    if phone:
        out.indented(f"Tel.: {phone}")
    email = (contact.get("email") or "").strip()
    if email:
        out.indented(f"E-mail: {email}")


def _append_contacts(out: _BlockList, protocol_data: Mapping[str, Any]) -> None:
    groups = list(protocol_data.get("contacts_by_type") or [])
    if not groups:
        contacts = list(protocol_data.get("contacts") or [])
        if contacts:
            groups = [
                {
                    "contact_type_label": "",
                    "employer_groups": [{"employer_label": "", "contacts": contacts}],
                }
            ]
    wrote_any = False
    for group in groups:
        type_label = (group.get("contact_type_label") or "").strip()
        employer_groups = group.get("employer_groups")
        if not employer_groups:
            flat = group.get("contacts") or []
            if not flat:
                continue
            employer_groups = [{"employer_label": "", "contacts": flat}]
        if type_label:
            if wrote_any:
                out.blank()
            out.label(type_label)
        for employer_group in employer_groups:
            items = employer_group.get("contacts") or []
            if not items:
                continue
            employer_label = (employer_group.get("employer_label") or "").strip()
            out.employer_label_line(employer_label)
            for contact in items:
                _append_contact_blocks(out, contact)
                wrote_any = True
    if not wrote_any:
        out.paragraph("—")


def _append_coordinator_details(
    out: _BlockList,
    coordinator: Mapping[str, Any] | None,
) -> None:
    out.blank()
    out.label(PROTOCOL_COORDINATOR_DETAILS_TITLE)
    if not coordinator:
        for label in ("Jméno", "Organizace", "Funkce", "Telefon", "E-mail"):
            out.paragraph(
                f"{label}: —",
                style=BLOCK_STYLE_COORDINATOR,
                runs=((f"{label}:", True), (" —", False)),
            )
        out.blank()
        return
    fields = (
        ("Jméno", coordinator.get("full_name")),
        ("Organizace", coordinator.get("employer_name")),
        ("Funkce", coordinator.get("role")),
        ("Telefon", coordinator.get("phone")),
        ("E-mail", coordinator.get("email")),
    )
    for label, value in fields:
        display = _display_or_dash(value)
        out.paragraph(
            f"{label}: {display}",
            style=BLOCK_STYLE_COORDINATOR,
            runs=((f"{label}:", True), (f" {display}", False)),
        )
    note = (coordinator.get("note") or "").strip()
    if note:
        out.paragraph(
            "Další informace:",
            style=BLOCK_STYLE_COORDINATOR,
            bold=True,
        )
        out.paragraph(note, style=BLOCK_STYLE_COORDINATOR)
    out.blank()


def _main_employer(protocol_data: Mapping[str, Any]) -> dict[str, Any] | None:
    for employer in protocol_data.get("employers") or []:
        if employer.get("is_main"):
            return employer
    employers = protocol_data.get("employers") or []
    return employers[0] if employers else None


def _append_risk_status(out: _BlockList, protocol_data: Mapping[str, Any]) -> None:
    wrote = False
    for row in protocol_data.get("risk_handovers") or []:
        employer = row.get("employer") or {}
        if employer.get("is_main"):
            continue
        abbr, name = _employer_abbr_and_name(employer)
        label = abbr or name or (employer.get("display_name") or "").strip() or "—"
        status = (
            row.get("handover_status_label") or row.get("handover_status") or ""
        ).strip() or "—"
        if wrote:
            out.blank()
        out.paragraph(label, bold=True, style=BLOCK_STYLE_EMPLOYER_ABBR)
        out.paragraph(status)
        wrote = True
    if not wrote:
        out.paragraph("—")
    pbp = protocol_data.get("pbp_snapshot")
    if pbp:
        main = _main_employer(protocol_data)
        main_abbr = (main or {}).get("abbreviation") or "HL"
        out.blank()
        out.paragraph(
            PROTOCOL_MAIN_RISKS_VIA_PBP.format(abbreviation=main_abbr)
        )


def _measure_bullets(protocol_data: Mapping[str, Any]) -> list[str]:
    bullets: list[str] = []
    for group in protocol_data.get("measures_by_category") or []:
        for measure in group.get("measures") or []:
            text = _protocol_measure_display_text(measure)
            if text and text != "—":
                bullets.append(text)
    return bullets


def _other_attachments(protocol_data: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for group in protocol_data.get("attachments_by_group") or []:
        if group.get("attachment_type") != ATTACHMENT_TYPE_OTHER:
            continue
        for attachment in group.get("attachments") or []:
            name = (
                attachment.get("original_filename")
                or attachment.get("description")
                or ""
            ).strip()
            if name:
                names.append(name)
    return names


def _first_participants_by_employer(
    protocol_data: Mapping[str, Any],
) -> dict[Any, Mapping[str, Any]]:
    result: dict[Any, Mapping[str, Any]] = {}
    for group in protocol_data.get("participants_by_employer") or []:
        employer = group.get("employer") or {}
        participants = group.get("participants") or []
        employer_id = employer.get("id")
        if employer_id is None or not participants:
            continue
        result[employer_id] = participants[0]
    return result


def _append_ppe(out: _BlockList, text: str | None) -> None:
    items = parse_ppe_items(text)
    if not items:
        out.paragraph("—")
        return
    raw = (text or "").strip()
    looks_like_list = bool(
        _PPE_LETTERED_RE.search(raw)
        or _PPE_INLINE_LETTERED_RE.search(raw)
        or "\n" in raw
        or raw.startswith("•")
    )
    if len(items) == 1 and not looks_like_list:
        out.paragraph(items[0])
        return
    for item in items:
        out.bullet(item)


def _append_pbp_content(out: _BlockList, pbp: Mapping[str, Any] | None) -> None:
    if not pbp:
        out.paragraph("—")
        return
    for line in pbp.get("content_lines") or []:
        stripped = (line or "").strip()
        if not stripped:
            out.blank()
            continue
        match = _PBP_RULE_RE.match(stripped)
        if match:
            out.pbp_rule(int(match.group(1)), match.group(2))
            out.blank()
        else:
            out.paragraph(stripped)


def _append_signatures(out: _BlockList, protocol_data: Mapping[str, Any]) -> None:
    first_by_employer = _first_participants_by_employer(protocol_data)
    for employer in protocol_data.get("employers") or []:
        abbr, name = _employer_abbr_and_name(employer)
        label = abbr or name or "—"
        out.paragraph(f"Za {label}")
        out.signature_line()
        participant = first_by_employer.get(employer.get("id"))
        if participant:
            full_name = (participant.get("full_name") or "").strip()
            if full_name:
                out.paragraph(full_name)
            role = (participant.get("role") or "").strip()
            if role:
                out.paragraph(role)
        out.blank()


def build_protocol_document(protocol_data: Mapping[str, Any]) -> dict[str, Any]:
    """Sestaví kanonický model dokumentu z protocol_data."""
    out = _BlockList()
    basics = protocol_data.get("basics") or {}
    agreement = protocol_data.get("coordination_agreement") or {}
    procedures = protocol_data.get("emergency_procedures") or {}
    main = _main_employer(protocol_data)
    main_abbr = (main or {}).get("abbreviation") or "HL"

    out.title(PROTOCOL_TITLE)
    out.blank()
    out.subtitle(PROTOCOL_SUBTITLE)
    out.blank()
    out.paragraph(PROTOCOL_INTRO_EMPLOYERS)
    for index, employer in enumerate(protocol_data.get("employers") or [], start=1):
        out.paragraph(_employer_protocol_line(employer, index))

    out.blank()
    out.heading(PROTOCOL_SECTION_BASICS)
    out.paragraph(f"Číslo: {_display_or_dash(basics.get('coordination_number'))}")
    out.paragraph(f"Název akce: {_display_or_dash(basics.get('subject'))}")
    out.paragraph(f"Místo: {_display_or_dash(basics.get('place'))}")
    out.paragraph(
        f"Datum schůzky: {_format_date(basics.get('meeting_date'))}"
    )

    out.blank()
    out.heading(PROTOCOL_SECTION_PARTICIPANTS)
    has_participants = False
    for group in protocol_data.get("participants_by_employer") or []:
        employer = group.get("employer") or {}
        participants = group.get("participants") or []
        if not participants:
            continue
        has_participants = True
        out.employer_heading(employer)
        for participant in participants:
            out.bullet(_participant_bullet(participant))
        out.blank()
    if not has_participants:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_SECTION_WORKPLACES)
    workplaces = protocol_data.get("workplaces") or []
    if workplaces:
        for item in workplaces:
            out.bullet(item.get("label") or "—")
    else:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_SECTION_ACTIVITIES)
    activity_groups = protocol_data.get("activities_by_employer") or []
    if activity_groups:
        for group in activity_groups:
            employer = group.get("employer") or {}
            activities = group.get("activities") or []
            out.employer_heading(employer)
            if not activities:
                out.paragraph("—")
            else:
                for activity in activities:
                    place = (activity.get("workplace_label") or "").strip()
                    suffix = f" ({place})" if place else ""
                    out.bullet(f"{activity.get('activity_name') or '—'}{suffix}")
            out.blank()
    else:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_SECTION_CONCLUSIONS)

    out.numbered_heading(1, PROTOCOL_CONCLUSION_1_TITLE)
    out.paragraph(_display_or_dash(agreement.get("work_intent_information_text")))

    out.numbered_heading(2, PROTOCOL_CONCLUSION_2_TITLE)
    _append_risk_status(out, protocol_data)

    out.numbered_heading(3, PROTOCOL_CONCLUSION_3_OOPP_INTRO)
    _append_ppe(out, agreement.get("ppe_text"))

    out.numbered_heading(4, PROTOCOL_CONCLUSION_4_COORDINATOR_INTRO)
    out.paragraph(PROTOCOL_COORDINATOR_NOMINATION)
    _append_coordinator_details(out, protocol_data.get("coordinator"))
    out.paragraph(PROTOCOL_COORDINATOR_ALIAS)
    out.paragraph(PROTOCOL_COORDINATOR_DUTIES)
    out.paragraph(PROTOCOL_COORDINATOR_AGREEMENT_CHANGE)
    out.paragraph(PROTOCOL_COORDINATOR_OBLIGATION)
    out.paragraph(PROTOCOL_COORDINATOR_TRAINING)
    out.paragraph(
        PROTOCOL_COORDINATOR_TRAINING_CHECK.format(abbreviation=main_abbr)
    )

    out.numbered_heading(5, PROTOCOL_CONCLUSION_5_TITLE)
    _append_contacts(out, protocol_data)

    out.numbered_heading(6, PROTOCOL_CONCLUSION_6_TITLE)
    emergency_rows = (
        ("Mimořádná událost", procedures.get("emergency_reporting")),
        ("Pracovní úraz", procedures.get("accident_reporting")),
        ("Požár", procedures.get("fire_reporting")),
        ("Evakuace", procedures.get("evacuation_instructions")),
    )
    for label, value in emergency_rows:
        out.paragraph(f"{label}: {_display_or_dash(value)}")

    out.numbered_heading(7, PROTOCOL_CONCLUSION_7_TITLE)
    measure_bullets = _measure_bullets(protocol_data)
    if measure_bullets:
        for text in measure_bullets:
            out.bullet(text)
    else:
        out.paragraph("—")

    out.numbered_heading(8, PROTOCOL_CONCLUSION_8_TITLE)
    employer_count = len(protocol_data.get("employers") or [])
    out.paragraph(
        PROTOCOL_FINAL_PROVISIONS_COPIES.format(count=employer_count or 1)
    )
    out.paragraph(PROTOCOL_FINAL_PROVISIONS_CONTINUATION)
    final_text = (agreement.get("final_provisions_text") or "").strip()
    if final_text:
        out.paragraph(final_text)
    out.paragraph(PROTOCOL_AGREEMENT_CLOSING)
    place = _display_or_dash(basics.get("place"))
    meeting = _format_date(basics.get("meeting_date"))
    out.paragraph(f"V {place} dne {meeting}")
    out.blank()
    _append_signatures(out, protocol_data)

    out.blank()
    out.heading(PROTOCOL_APPENDIX_OVERVIEW)
    out.paragraph(PROTOCOL_APPENDIX_OVERVIEW_INTRO)
    out.bullet("A – Pravidla bezpečné práce (PBP)")
    out.bullet("B – Přehled předaných rizik zaměstnavatelů")
    out.bullet("C+ – Další přiložené dokumenty (pouze seznam)")

    out.blank()
    out.heading(PROTOCOL_APPENDIX_A)
    pbp = protocol_data.get("pbp_snapshot")
    if pbp:
        out.paragraph(
            PROTOCOL_PBP_TITLE_TEMPLATE.format(
                abbreviation=(main or {}).get("abbreviation") or main_abbr
            )
        )
        _append_pbp_content(out, pbp)
    else:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_APPENDIX_B)
    risk_rows = protocol_data.get("risk_handovers") or []
    contractor_rows = [
        row for row in risk_rows if not (row.get("employer") or {}).get("is_main")
    ]
    if contractor_rows:
        for index, row in enumerate(contractor_rows):
            if index:
                out.blank()
            employer = row.get("employer") or {}
            abbr, name = _employer_abbr_and_name(employer)
            label = abbr or name or (employer.get("display_name") or "—")
            status = (
                row.get("handover_status_label")
                or row.get("handover_status")
                or "—"
            )
            out.paragraph(str(label), bold=True, style=BLOCK_STYLE_EMPLOYER_ABBR)
            out.paragraph(str(status))
    else:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_APPENDIX_C)
    out.paragraph(PROTOCOL_APPENDIX_C_INTRO)
    other_names = _other_attachments(protocol_data)
    if other_names:
        for name in other_names:
            out.bullet(name)
    else:
        out.paragraph("—")

    blocks = out.build()
    return {"blocks": [block.to_dict() for block in blocks]}
