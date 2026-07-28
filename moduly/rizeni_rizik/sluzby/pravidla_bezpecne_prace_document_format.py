"""Formátování změnových sekcí dokumentu Pravidel bezpečné práce (PBP-5d).

ODT exportér pouze vykresluje data z ``last_comparison`` – logika porovnání
zůstává v PBP-5b.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Callable

from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_comparison import (
    PravidlaBezpecnePraceComparison,
)

if TYPE_CHECKING:
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
    )


def format_change_sections(
    comparison: PravidlaBezpecnePraceComparison | None,
    *,
    current_issued_at: date | datetime,
    date_formatter: Callable[[date | datetime], str],
) -> str:
    """Vrátí text změnových sekcí, nebo prázdný řetězec bez změn / u 1. vydání."""
    if comparison is None or comparison.is_first_edition or not comparison.has_changes:
        return ""

    parts: list[str] = [
        "Shrnutí změn",
        "",
        f"Nová pravidla: {len(comparison.new_rules)}",
        f"Změněná pravidla: {len(comparison.changed_rules)}",
        f"Zrušená pravidla: {len(comparison.removed_rules)}",
        "",
        "Poslední vydání:",
        date_formatter(comparison.previous_issued_at)
        if comparison.previous_issued_at is not None
        else "",
        "",
        "Aktuální vydání:",
        date_formatter(current_issued_at),
    ]

    if comparison.new_rules:
        parts.extend(["", "🟢 Nová pravidla", ""])
        for rule in comparison.new_rules:
            parts.append(f"🟢 {rule.text}")
            parts.append("")
        if parts[-1] == "":
            parts.pop()

    if comparison.changed_rules:
        parts.extend(["", "🟡 Změněná pravidla", ""])
        for index, changed in enumerate(comparison.changed_rules):
            if index:
                parts.append("")
            parts.extend(
                [
                    "Staré:",
                    f"• {changed.previous_text}",
                    "",
                    "Nové:",
                    f"🟡 {changed.current_text}",
                ]
            )

    if comparison.removed_rules:
        parts.extend(["", "🔴 Zrušená pravidla", ""])
        for rule in comparison.removed_rules:
            parts.append(f"🔴 {rule.display_text}")
            parts.append("")
        if parts[-1] == "":
            parts.pop()

    return "\n".join(parts).rstrip() + "\n"


def format_bullet_valid_rules(
    rules: list[PravidloBezpecnePrace],
    comparison: PravidlaBezpecnePraceComparison | None,
) -> list[str]:
    """Odrážková platná pravidla; při změnách označí nová (🟢) a změněná (🟡)."""
    new_norms: set[str] = set()
    changed_norms: set[str] = set()
    if comparison is not None and comparison.has_changes and not comparison.is_first_edition:
        new_norms = {rule.text.casefold() for rule in comparison.new_rules}
        changed_norms = {
            changed.current_text.casefold() for changed in comparison.changed_rules
        }

    lines: list[str] = []
    for rule in rules:
        text = (rule.text or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in new_norms:
            lines.append(f"• 🟢 {text}")
        elif key in changed_norms:
            lines.append(f"• 🟡 {text}")
        else:
            lines.append(f"• {text}")
    return lines


def format_numbered_valid_rules(
    rules: list[PravidloBezpecnePrace],
    comparison: PravidlaBezpecnePraceComparison | None,
) -> str:
    """Číslovaná platná pravidla (koordinace BOZP a starší volající)."""
    new_norms: set[str] = set()
    changed_norms: set[str] = set()
    if comparison is not None and comparison.has_changes and not comparison.is_first_edition:
        new_norms = {rule.text.casefold() for rule in comparison.new_rules}
        changed_norms = {
            changed.current_text.casefold() for changed in comparison.changed_rules
        }

    lines: list[str] = []
    for index, rule in enumerate(rules, start=1):
        text = (rule.text or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in new_norms:
            lines.append(f"{index}. 🟢 {text}")
        elif key in changed_norms:
            lines.append(f"{index}. 🟡 {text}")
        else:
            lines.append(f"{index}. {text}")
    return "\n".join(lines)
