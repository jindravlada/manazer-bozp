"""Sdílené zobrazení komise v exportních dokumentech (audit / prověrka)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Krátké názvy rolí – jednotné napříč Manažerem BOZP.
COMMISSION_LABEL_LEADER_AUDIT = "Vedoucí auditor"
COMMISSION_LABEL_LEADER_INSPECTION = "Vedoucí prověrky"
COMMISSION_LABEL_WORKPLACE = "Zástupce provozu"
COMMISSION_LABEL_UNION = "Zástupce odborové organizace"
COMMISSION_LABEL_MEMBERS = "Členové komise"
COMMISSION_LABEL_INVITED = "Přizvané osoby"

# Pořadí sekcí jako v dokumentech auditu (+ přizvané osoby u prověrek).
COMMISSION_SECTION_ORDER = (
    "leader",
    "workplace",
    "union",
    "members",
    "invited",
)

# Placeholdery volitelných řádků v ODT šablonách prověrek (prázdné = řádek pryč).
INSPECTION_OPTIONAL_COMMISSION_PLACEHOLDERS = (
    "zastupce_odborove_organizace",
    "zastupce_odboru",
    "clenove_komise_text",
    "prizvane_osoby_text",
)


@dataclass(frozen=True)
class CommissionSection:
    """Jedna sekce komise v dokumentu (label + jména)."""

    key: str
    label: str
    names: tuple[str, ...]

    def body(self) -> str:
        return "\n".join(self.names)

    def as_text(self) -> str:
        return f"{self.label}\n{self.body()}"


def _clean_names(names: Sequence[str] | None) -> tuple[str, ...]:
    cleaned: list[str] = []
    for name in names or ():
        text = str(name or "").strip()
        if text:
            cleaned.append(text)
    return tuple(cleaned)


def build_commission_sections(
    *,
    leader_label: str,
    leader_names: Sequence[str] | None = None,
    workplace_names: Sequence[str] | None = None,
    union_names: Sequence[str] | None = None,
    member_names: Sequence[str] | None = None,
    invited_names: Sequence[str] | None = None,
) -> list[CommissionSection]:
    """Sestaví sekce komise; prázdné sekce vynechá."""
    specs = (
        ("leader", leader_label, leader_names),
        ("workplace", COMMISSION_LABEL_WORKPLACE, workplace_names),
        ("union", COMMISSION_LABEL_UNION, union_names),
        ("members", COMMISSION_LABEL_MEMBERS, member_names),
        ("invited", COMMISSION_LABEL_INVITED, invited_names),
    )
    sections: list[CommissionSection] = []
    for key, label, names in specs:
        cleaned = _clean_names(names)
        if not cleaned:
            continue
        sections.append(CommissionSection(key=key, label=label, names=cleaned))
    return sections


def commission_sections_text(sections: Sequence[CommissionSection]) -> str:
    """Textové složení komise (sekce oddělené prázdným řádkem)."""
    if not sections:
        return "Nejsou evidováni."
    return "\n\n".join(section.as_text() for section in sections)


def basic_info_commission_row_xml(label: str, placeholder: str) -> str:
    """XML řádek tabulky Základní informace ve stejném stylu jako audit."""
    return (
        "<table:table-row>"
        '<table:table-cell office:value-type="string">'
        f'<text:p text:style-name="Standard">{label}</text:p>'
        "</table:table-cell>"
        '<table:table-cell office:value-type="string">'
        f'<text:p text:style-name="Standard">${{{placeholder}}}</text:p>'
        "</table:table-cell>"
        "</table:table-row>"
    )
