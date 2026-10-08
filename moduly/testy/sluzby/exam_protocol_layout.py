"""Společná závěrečná část protokolu pro papírový test i elektronický protokol.

Písemná část se liší: na papíře je ruční zaškrtnutí, u elektronické zkoušky
uložený souhrn. Ústní otázky, ruční výsledky a podpisy jsou tu jednou.
"""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

from moduly.testy.constants import (
    EXAM_ROLE_CHAIR,
    EXAM_ROLE_CHAIR_LABEL,
    EXAM_ROLE_EXAMINER,
    EXAM_ROLE_EXAMINER_LABEL,
    EXAM_ROLE_MEMBER,
    EXAM_ROLE_MEMBER_LABEL,
    EXAMINER_MODE_COMMISSION,
    EXAMINER_MODE_SINGLE,
)

EXAMINEE_SIGNATURE_LABEL = "Zkoušený(á):"

# Ruční datum. Plánované datum z databáze se na doklad netiskne.
BLANK_EXAM_DATE_LINE = "Datum: ______________________"
CHECKBOX = "\u2610"
MANUAL_RESULT_LINE = f"{CHECKBOX} VYHOVĚL(A)        {CHECKBOX} NEVYHOVĚL(A)"
PAPER_RESULT_OPTIONS = f"{CHECKBOX} VYHOVĚL(A) {CHECKBOX} NEVYHOVĚL(A)"
WRITTEN_RESULT_LINE = "Výsledek písemné části: VYHOVĚL(A)"
ERROR_LIST_HEADING = "VÝPIS CHYBNĚ ZODPOVĚZENÝCH OTÁZEK"
NO_WRITTEN_ERRORS_LINE = "Bez chyb."
WRITTEN_CONFIRM_SENTENCE = (
    "S výsledkem písemné části souhlasím, špatné odpovědi mi byly vysvětleny:"
)
WRITTEN_CONFIRM_BLANK = "_" * 30


def render_paper_protocol_xml(
    oral_items: list[tuple[int, str]],
    people: list[tuple[str, str]],
) -> str:
    """Závěr papírového testu. Otázky už jsou v dokumentu před tímto blokem."""
    parts = [
        '<text:p text:style-name="ProtocolDivider">&#160;</text:p>',
        '<text:p text:style-name="ProtocolHeading">PÍSEMNÁ ČÁST</text:p>',
        _paper_result_paragraph("Výsledek písemné části:"),
        render_written_confirmation_xml(),
        render_protocol_closing_xml(oral_items, people, paper_results=True),
    ]
    return "".join(parts)


def render_electronic_protocol_xml(
    summary_lines: list[str],
    oral_items: list[tuple[int, str]],
    people: list[tuple[str, str]],
    *,
    error_listing_xml: str = "",
) -> str:
    """Písemný souhrn, výpis chyb a stejný závěr jako u papírového testu."""
    listing = error_listing_xml or (
        f'<text:p text:style-name="ProtocolHeading">{_xml(ERROR_LIST_HEADING)}</text:p>'
        f'<text:p text:style-name="ProtocolText">{_xml(NO_WRITTEN_ERRORS_LINE)}</text:p>'
    )
    parts = ['<text:p text:style-name="ProtocolHeading">PÍSEMNÁ ČÁST</text:p>']
    for line in summary_lines:
        parts.append(f'<text:p text:style-name="ProtocolText">{_xml(line)}</text:p>')
    parts.append(f'<text:p text:style-name="ProtocolText">{_xml(WRITTEN_RESULT_LINE)}</text:p>')
    parts.append(listing)
    parts.append(render_written_confirmation_xml())
    parts.append(render_protocol_closing_xml(oral_items, people, paper_results=True))
    return "".join(parts)


def render_written_confirmation_xml() -> str:
    """První podpis po písemné části. Závěrečný podpis zkoušeného neruší."""
    line = f"{examinee_role_label()} {WRITTEN_CONFIRM_BLANK}"
    return (
        f'<text:p text:style-name="ProtocolConfirm">{_xml(WRITTEN_CONFIRM_SENTENCE)}</text:p>'
        f'<text:p text:style-name="ProtocolText">{_xml(line)}</text:p>'
    )


def paper_result_text(label: str) -> str:
    """Jeden nezlomitelný řádek výsledku papírového testu."""
    return f"{label} {PAPER_RESULT_OPTIONS}"


def render_protocol_closing_xml(
    oral_items: list[tuple[int, str]],
    people: list[tuple[str, str]],
    *,
    paper_results: bool = False,
) -> str:
    """Ústní otázky, ruční výsledky a podpisy. Prázdný seznam ústních otázek sekci vynechá."""
    parts: list[str] = []
    ordered = sorted(oral_items, key=lambda item: int(item[0]))
    if ordered:
        # Nadpis má keep-with-next, takže nezůstane sám. První otázka ho drží
        # i s druhou. Poslední otázka drží výsledek ústní části. Mezi tím se
        # seznam může rozdělit, celý blok otázek se nedrží pohromadě.
        parts.append('<text:p text:style-name="ProtocolHeading">ÚSTNÍ ČÁST</text:p>')
        last_index = len(ordered) - 1
        for index, (position, text) in enumerate(ordered):
            parts.append(
                _oral_block(
                    position,
                    text,
                    keep_with_next=index == 0 or index == last_index,
                )
            )
        if paper_results:
            parts.append(_paper_result_paragraph("Výsledek ústní části:"))
        else:
            parts.append(_manual_outcome("Výsledek ústní části:"))
    if paper_results:
        parts.append(_paper_result_paragraph("CELKOVÝ VÝSLEDEK ZKOUŠKY:"))
    else:
        parts.append('<text:p text:style-name="ProtocolHeading">CELKOVÝ VÝSLEDEK ZKOUŠKY</text:p>')
        parts.append(f'<text:p text:style-name="ProtocolCheck">{_xml(MANUAL_RESULT_LINE)}</text:p>')
    parts.append(_signature_block(people))
    return "".join(parts)


def protocol_people(exam, examiners) -> list[tuple[str, str]]:
    """Podpisy podle režimu snapshotu. Jména jsou snímek, ne aktuální evidence."""
    people = [(examinee_role_label(), _person_name(exam))]
    ordered = sorted(
        list(examiners or []),
        key=lambda item: (int(getattr(item, "position", 0)), int(getattr(item, "id", 0))),
    )
    mode = str(getattr(exam, "examiner_mode", "") or "")
    if mode == EXAMINER_MODE_SINGLE:
        for person in ordered:
            if str(getattr(person, "role", "")) == EXAM_ROLE_EXAMINER:
                people.append((EXAM_ROLE_EXAMINER_LABEL, _snapshot_name(person)))
    elif mode == EXAMINER_MODE_COMMISSION:
        for person in ordered:
            if str(getattr(person, "role", "")) == EXAM_ROLE_CHAIR:
                people.append((EXAM_ROLE_CHAIR_LABEL, _snapshot_name(person)))
        for person in ordered:
            if str(getattr(person, "role", "")) == EXAM_ROLE_MEMBER:
                people.append((EXAM_ROLE_MEMBER_LABEL, _snapshot_name(person)))
    return people


def protocol_oral_items(questions) -> list[tuple[int, str]]:
    return [
        (int(question.position), str(question.text or ""))
        for question in questions or []
    ]


def _paper_result_paragraph(label: str) -> str:
    return (
        f'<text:p text:style-name="ProtocolResult">{_xml(paper_result_text(label))}</text:p>'
        '<text:p text:style-name="ProtocolResultGap">&#160;</text:p>'
    )


def _manual_outcome(label: str) -> str:
    return (
        f'<text:p text:style-name="ProtocolHeading">{_xml(label)}</text:p>'
        f'<text:p text:style-name="ProtocolCheck">{_xml(MANUAL_RESULT_LINE)}</text:p>'
    )


def examinee_role_label() -> str:
    """Jednotný podpis zkoušeného pro oba podpisy protokolu."""
    return EXAMINEE_SIGNATURE_LABEL


def _oral_block(position: int, text: str, *, keep_with_next: bool) -> str:
    """Jedna otázka jako odstavec. Sama se nedělí; seznam ano, kromě začátku a konce."""
    style = "ProtocolOralNext" if keep_with_next else "ProtocolOralText"
    return f'<text:p text:style-name="{style}">{_xml(f"{int(position)}. {text}")}</text:p>'


def _signature_block(people: list[tuple[str, str]]) -> str:
    lines = []
    for role, name in people:
        lines.append(f'<text:p text:style-name="ProtocolSignRole">{_xml(role)}</text:p>')
        if name:
            lines.append(f'<text:p text:style-name="ProtocolSignName">{_xml(name)}</text:p>')
        lines.append('<text:p text:style-name="ProtocolSignLine">&#160;</text:p>')
    return (
        '<table:table table:style-name="ProtocolSign">'
        '<table:table-column table:style-name="ProtocolSignCol"/>'
        '<table:table-row table:style-name="ProtocolSignRow">'
        '<table:table-cell table:style-name="ProtocolSignCell" office:value-type="string">'
        f"{''.join(lines)}"
        "</table:table-cell></table:table-row></table:table>"
    )


def _person_name(exam) -> str:
    display = str(getattr(exam, "employee_display_name", "") or "").strip()
    if display:
        return display
    parts = [
        str(getattr(exam, "employee_title_before", "") or "").strip(),
        str(getattr(exam, "employee_first_name", "") or "").strip(),
        str(getattr(exam, "employee_last_name", "") or "").strip(),
    ]
    name = " ".join(part for part in parts if part)
    after = str(getattr(exam, "employee_title_after", "") or "").strip()
    if after:
        return f"{name}, {after}" if name else after
    return name


def _snapshot_name(person) -> str:
    return str(getattr(person, "display_name", "") or "").strip()


def _xml(value: object) -> str:
    text = "" if value is None else str(value).strip()
    escaped = xml_escape(text)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<text:line-break/>")
