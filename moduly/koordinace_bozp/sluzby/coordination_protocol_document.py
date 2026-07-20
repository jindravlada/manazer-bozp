"""Společný model dokumentu koordinačního protokolu (BUILDER-COORD-1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_OTHER,
    COORDINATION_PBP_INFO_TEXT,
    COORDINATION_PBP_INTRO_TEXT,
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
    PROTOCOL_COORDINATOR_DUTIES,
    PROTOCOL_COORDINATOR_NOMINATION,
    PROTOCOL_COORDINATOR_OBLIGATION,
    PROTOCOL_COORDINATOR_TRAINING,
    PROTOCOL_COORDINATOR_TRAINING_CHECK,
    PROTOCOL_FINAL_PROVISIONS,
    PROTOCOL_INTRO_EMPLOYERS,
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
BLOCK_KIND_BLANK = "blank"
BLOCK_KIND_SIGNATURE_LINE = "signature_line"

BLOCK_STYLE_TITLE = "title"
BLOCK_STYLE_HEADING = "heading"
BLOCK_STYLE_BODY = "body"
BLOCK_STYLE_BULLET = "bullet"


@dataclass(frozen=True)
class ProtocolDocumentBlock:
    kind: str
    text: str = ""
    level: int = 0
    style: str = BLOCK_STYLE_BODY

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def paragraph(self, text: str) -> None:
        if not (text or "").strip():
            return
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_PARAGRAPH, text, style=BLOCK_STYLE_BODY)
        )

    def bullet(self, text: str) -> None:
        if not (text or "").strip():
            return
        self._blocks.append(
            ProtocolDocumentBlock(BLOCK_KIND_BULLET, text, style=BLOCK_STYLE_BULLET)
        )

    def blank(self) -> None:
        self._blocks.append(ProtocolDocumentBlock(BLOCK_KIND_BLANK))

    def signature_line(self, text: str = "_________________________") -> None:
        self._blocks.append(
            ProtocolDocumentBlock(
                BLOCK_KIND_SIGNATURE_LINE,
                text,
                style=BLOCK_STYLE_BODY,
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
        else:
            kind = block.kind
            text = (block.text or "").strip()
            level = block.level
        if kind == BLOCK_KIND_BLANK:
            lines.append("")
            continue
        if kind == BLOCK_KIND_NUMBERED_HEADING:
            lines.append(f"{level}. {text}" if text else f"{level}.")
            continue
        if kind == BLOCK_KIND_BULLET:
            lines.append(f"• {text}" if text else "•")
            continue
        if text:
            lines.append(text)
    return lines


def document_blocks_from_dict(data: Mapping[str, Any] | None) -> list[ProtocolDocumentBlock]:
    blocks = (data or {}).get("blocks") or []
    result: list[ProtocolDocumentBlock] = []
    for item in blocks:
        if isinstance(item, ProtocolDocumentBlock):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(
                ProtocolDocumentBlock(
                    kind=str(item.get("kind") or BLOCK_KIND_PARAGRAPH),
                    text=str(item.get("text") or ""),
                    level=int(item.get("level") or 0),
                    style=str(item.get("style") or BLOCK_STYLE_BODY),
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


def _participant_bullet(participant: Mapping[str, Any]) -> str:
    detail = (participant.get("full_name") or "—").strip()
    role = (participant.get("role") or "").strip()
    if role:
        detail = f"{detail} – {role}"
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


def _contact_detail(contact: Mapping[str, Any]) -> str:
    detail = (contact.get("custom_name") or "").strip()
    role = (contact.get("role") or "").strip()
    if role:
        detail = f"{detail}, {role}" if detail else role
    return detail


def _append_contact_blocks(out: _BlockList, contact: Mapping[str, Any]) -> None:
    detail = _contact_detail(contact)
    if detail:
        out.paragraph(detail)
    phone = (contact.get("phone") or "").strip()
    email = (contact.get("email") or "").strip()
    if phone:
        out.paragraph(f"Telefon: {phone}")
    if email:
        out.paragraph(f"E-mail: {email}")


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
    for group in groups:
        type_label = (group.get("contact_type_label") or "").strip()
        employer_groups = group.get("employer_groups")
        if not employer_groups:
            flat = group.get("contacts") or []
            if not flat:
                continue
            employer_groups = [{"employer_label": "", "contacts": flat}]
        if type_label:
            out.paragraph(type_label)
        for employer_group in employer_groups:
            items = employer_group.get("contacts") or []
            if not items:
                continue
            employer_label = (employer_group.get("employer_label") or "").strip()
            if employer_label and employer_label != CONTACT_EMPLOYER_UNSPECIFIED:
                out.paragraph(employer_label)
            for contact in items:
                _append_contact_blocks(out, contact)


def _append_coordinator_details(
    out: _BlockList,
    coordinator: Mapping[str, Any] | None,
) -> None:
    if not coordinator:
        for label in ("Jméno", "Organizace", "Funkce", "Telefon", "E-mail"):
            out.paragraph(f"{label}: —")
        return
    out.paragraph(f"Jméno: {_display_or_dash(coordinator.get('full_name'))}")
    out.paragraph(f"Organizace: {_display_or_dash(coordinator.get('employer_name'))}")
    out.paragraph(f"Funkce: {_display_or_dash(coordinator.get('role'))}")
    out.paragraph(f"Telefon: {_display_or_dash(coordinator.get('phone'))}")
    out.paragraph(f"E-mail: {_display_or_dash(coordinator.get('email'))}")
    note = (coordinator.get("note") or "").strip()
    if note:
        out.paragraph("Další informace")
        out.paragraph(note)


def _main_employer(protocol_data: Mapping[str, Any]) -> dict[str, Any] | None:
    for employer in protocol_data.get("employers") or []:
        if employer.get("is_main"):
            return employer
    employers = protocol_data.get("employers") or []
    return employers[0] if employers else None


def _risk_status_lines(protocol_data: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in protocol_data.get("risk_handovers") or []:
        employer = row.get("employer") or {}
        if employer.get("is_main"):
            continue
        name = (employer.get("display_name") or "").strip()
        status = (
            row.get("handover_status_label") or row.get("handover_status") or ""
        ).strip()
        abbr = (employer.get("abbreviation") or "").strip()
        if status and abbr:
            lines.append(f"{abbr} předala rizika: {status}")
        elif name and status:
            lines.append(f"{name}: {status}")
        elif status:
            lines.append(status)
    return lines


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
        out.paragraph(f"{employer.get('display_name') or '—'}:")
        for participant in participants:
            out.bullet(_participant_bullet(participant))
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
    has_activities = False
    for group in protocol_data.get("activities_by_employer") or []:
        employer = group.get("employer") or {}
        activities = group.get("activities") or []
        out.paragraph(f"{employer.get('display_name') or '—'}:")
        if not activities:
            out.paragraph("—")
            continue
        has_activities = True
        for activity in activities:
            place = (activity.get("workplace_label") or "").strip()
            suffix = f" ({place})" if place else ""
            out.bullet(f"{activity.get('activity_name') or '—'}{suffix}")
    if not has_activities and not (protocol_data.get("activities_by_employer") or []):
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_SECTION_CONCLUSIONS)

    out.numbered_heading(1, PROTOCOL_CONCLUSION_1_TITLE)
    out.paragraph(_display_or_dash(agreement.get("work_intent_information_text")))

    out.numbered_heading(2, PROTOCOL_CONCLUSION_2_TITLE)
    risk_lines = _risk_status_lines(protocol_data)
    if risk_lines:
        for line in risk_lines:
            out.paragraph(line)
    else:
        out.paragraph("—")

    out.numbered_heading(3, PROTOCOL_CONCLUSION_3_OOPP_INTRO)
    out.paragraph(_display_or_dash(agreement.get("ppe_text")))

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
    out.paragraph(PROTOCOL_FINAL_PROVISIONS)
    final_text = (agreement.get("final_provisions_text") or "").strip()
    if final_text:
        out.paragraph(final_text)
    out.paragraph(PROTOCOL_AGREEMENT_CLOSING)
    place = _display_or_dash(basics.get("place"))
    meeting = _format_date(basics.get("meeting_date"))
    out.paragraph(f"V {place} dne {meeting}")
    for employer in protocol_data.get("employers") or []:
        abbr = (employer.get("abbreviation") or employer.get("company_name") or "—")
        out.paragraph(f"Za {abbr}:")
        out.paragraph("jméno a příjmení, funkce")
        out.signature_line()

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
        for line in pbp.get("content_lines") or []:
            if (line or "").strip():
                out.paragraph(line)
            else:
                out.blank()
    else:
        out.paragraph("—")

    out.blank()
    out.heading(PROTOCOL_APPENDIX_B)
    risk_rows = protocol_data.get("risk_handovers") or []
    contractor_rows = [
        row for row in risk_rows if not (row.get("employer") or {}).get("is_main")
    ]
    if contractor_rows:
        for row in contractor_rows:
            employer = row.get("employer") or {}
            status = (
                row.get("handover_status_label")
                or row.get("handover_status")
                or "—"
            )
            out.bullet(f"{employer.get('display_name') or '—'}: {status}")
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
