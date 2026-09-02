"""Rozpis skutečných Finding podle druhu pro úvod kontrolních zpráv.

Bez Qt. Nečte databázi — pracuje s už načteným seznamem Finding.
Započítává všechny stavy (otevřené, v procesu, vypořádané).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.shared.constants import (
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_NESHODA,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_POZOROVANI,
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_ZJISTENI,
)
from core.shared.sluzby.control_report_language import (
    AUDIT_EMPTY_FOUND_SENTENCE,
    INSPECTION_EMPTY_FOUND_SENTENCE,
)
from core.utils.czech_count import format_czech_count

FINDINGS_TOTAL_OVERVIEW_LABEL = "Zjištění celkem"
OTHER_FINDINGS_OVERVIEW_LABEL = "Ostatní zjištění"

ZJISTENI_COUNT_FORMS = {
    "one": "zjištění",
    "few": "zjištění",
    "many": "zjištění",
}

# Tvary po „z toho“ (akuzativ u ženského rodu: 1 závadu, 1 neshodu).
FINDING_TYPE_SENTENCE_FORMS: dict[str, dict[str, str]] = {
    FINDING_TYPE_ZAVADA: {
        "one": "závadu",
        "few": "závady",
        "many": "závad",
    },
    FINDING_TYPE_NEDOSTATEK: {
        "one": "nedostatek",
        "few": "nedostatky",
        "many": "nedostatků",
    },
    FINDING_TYPE_PORUSENI_PREDPISU: {
        "one": "porušení předpisu",
        "few": "porušení předpisu",
        "many": "porušení předpisů",
    },
    FINDING_TYPE_NESHODA: {
        "one": "neshodu",
        "few": "neshody",
        "many": "neshod",
    },
    FINDING_TYPE_POZOROVANI: {
        "one": "pozorování",
        "few": "pozorování",
        "many": "pozorování",
    },
    FINDING_TYPE_ZJISTENI: {
        "one": "zjištění",
        "few": "zjištění",
        "many": "zjištění",
    },
    FINDING_TYPE_PRILEZITOST: {
        "one": "příležitost ke zlepšení",
        "few": "příležitosti ke zlepšení",
        "many": "příležitostí ke zlepšení",
    },
}

FINDING_TYPE_OVERVIEW_LABELS: dict[str, str] = {
    FINDING_TYPE_ZAVADA: "Závady",
    FINDING_TYPE_NEDOSTATEK: "Nedostatky",
    FINDING_TYPE_PORUSENI_PREDPISU: "Porušení předpisů",
    FINDING_TYPE_NESHODA: "Neshody",
    FINDING_TYPE_POZOROVANI: "Pozorování",
    FINDING_TYPE_ZJISTENI: "Zjištění",
    FINDING_TYPE_PRILEZITOST: "Příležitosti ke zlepšení",
}

OTHER_SENTENCE_FORMS = {
    "one": "ostatní zjištění",
    "few": "ostatní zjištění",
    "many": "ostatních zjištění",
}


@dataclass(frozen=True)
class FindingsTypeBreakdown:
    """Počty Finding podle doménového pořadí; neznámé druhy v ``other_count``."""

    total: int
    ordered_counts: tuple[tuple[str, int], ...]
    other_count: int

    def parts_sum(self) -> int:
        return sum(count for _code, count in self.ordered_counts) + self.other_count


def finding_type_code(finding) -> str:
    return str(getattr(finding, "finding_type", "") or "").strip()


def count_findings_by_type(
    findings,
    type_order: Sequence[str],
) -> FindingsTypeBreakdown:
    """Spočítá všechny předané Finding; status se nefiltruje."""
    allowed = tuple(code for code in type_order if code in FINDING_TYPE_SENTENCE_FORMS)
    allowed_set = set(allowed)
    counts = {code: 0 for code in allowed}
    other = 0
    total = 0
    for finding in findings:
        total += 1
        code = finding_type_code(finding)
        if code in allowed_set:
            counts[code] += 1
        else:
            other += 1
    ordered = tuple((code, counts[code]) for code in allowed if counts[code] > 0)
    return FindingsTypeBreakdown(
        total=total,
        ordered_counts=ordered,
        other_count=other,
    )


def join_czech_enumerated(parts: Sequence[str]) -> str:
    """Spojí části čárkami a před poslední dá „a“."""
    cleaned = [str(item).strip() for item in parts if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return f"{', '.join(cleaned[:-1])} a {cleaned[-1]}"


def format_findings_overview_lines(
    findings,
    type_order: Sequence[str],
) -> list[str]:
    """Řádky Přehledu výsledků: vždy celkem, pak nenulové druhy."""
    breakdown = count_findings_by_type(findings, type_order)
    lines = [f"{FINDINGS_TOTAL_OVERVIEW_LABEL}: {breakdown.total}"]
    for code, count in breakdown.ordered_counts:
        label = FINDING_TYPE_OVERVIEW_LABELS[code]
        lines.append(f"{label}: {count}")
    if breakdown.other_count:
        lines.append(f"{OTHER_FINDINGS_OVERVIEW_LABEL}: {breakdown.other_count}")
    return lines


def format_evidence_findings_sentence(
    findings,
    *,
    domain_label: str,
    type_order: Sequence[str],
    empty_sentence: str,
) -> str:
    """Věta Evidence … obsahuje / neobsahuje. „obsahuje“ se neskloňuje."""
    breakdown = count_findings_by_type(findings, type_order)
    if breakdown.total == 0:
        return empty_sentence
    parts: list[str] = []
    for code, count in breakdown.ordered_counts:
        parts.append(format_czech_count(count, **FINDING_TYPE_SENTENCE_FORMS[code]))
    if breakdown.other_count:
        parts.append(format_czech_count(breakdown.other_count, **OTHER_SENTENCE_FORMS))
    counted = format_czech_count(breakdown.total, **ZJISTENI_COUNT_FORMS)
    return (
        f"Evidence {domain_label} obsahuje {counted}, "
        f"z toho {join_czech_enumerated(parts)}."
    )


def format_inspection_evidence_sentence(findings, type_order: Sequence[str]) -> str:
    return format_evidence_findings_sentence(
        findings,
        domain_label="prověrky",
        type_order=type_order,
        empty_sentence=INSPECTION_EMPTY_FOUND_SENTENCE,
    )


def format_audit_evidence_sentence(findings, type_order: Sequence[str]) -> str:
    return format_evidence_findings_sentence(
        findings,
        domain_label="auditu",
        type_order=type_order,
        empty_sentence=AUDIT_EMPTY_FOUND_SENTENCE,
    )
