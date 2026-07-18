"""Společný číselník závažnosti následku.

Používá se v řízení rizik; stejné API je připravené i pro další moduly
(Audity, Prověrky, …), které si mohou tooltipy brát z tohoto zdroje.
"""

from __future__ import annotations

RISK_SEVERITY_NEGLIGIBLE = "negligible"
RISK_SEVERITY_MINOR = "minor"
RISK_SEVERITY_MODERATE = "moderate"
RISK_SEVERITY_SERIOUS = "serious"
RISK_SEVERITY_CRITICAL = "critical"

RISK_SEVERITIES = (
    RISK_SEVERITY_NEGLIGIBLE,
    RISK_SEVERITY_MINOR,
    RISK_SEVERITY_MODERATE,
    RISK_SEVERITY_SERIOUS,
    RISK_SEVERITY_CRITICAL,
)

DEFAULT_RISK_SEVERITY = RISK_SEVERITY_MODERATE

RISK_SEVERITY_LABELS = {
    RISK_SEVERITY_NEGLIGIBLE: "Zanedbatelný",
    RISK_SEVERITY_MINOR: "Lehký",
    RISK_SEVERITY_MODERATE: "Závažný",
    RISK_SEVERITY_SERIOUS: "Velmi závažný",
    RISK_SEVERITY_CRITICAL: "Kritický",
}

RISK_SEVERITY_DESCRIPTIONS = {
    RISK_SEVERITY_NEGLIGIBLE: (
        "Bez zranění nebo pouze přechodné drobné obtíže bez potřeby odborného ošetření."
    ),
    RISK_SEVERITY_MINOR: (
        "Lehké zranění nebo zdravotní obtíže bez pracovní neschopnosti."
    ),
    RISK_SEVERITY_MODERATE: (
        "Zranění nebo poškození zdraví s pracovní neschopností."
    ),
    RISK_SEVERITY_SERIOUS: (
        "Těžké zranění, hospitalizace, trvalé následky nebo nemoc z povolání."
    ),
    RISK_SEVERITY_CRITICAL: (
        "Smrtelné zranění nebo událost s možností postižení více osob."
    ),
}


def format_risk_severity_label(severity: str) -> str:
    return RISK_SEVERITY_LABELS.get(severity, severity or "—")


def format_risk_severity_description(severity: str) -> str:
    return RISK_SEVERITY_DESCRIPTIONS.get(severity, "")


def format_severity_tooltip(*, label: str, description: str) -> str:
    """Obecný formát tooltipu: název, prázdný řádek, popis."""
    label = (label or "").strip()
    description = (description or "").strip()
    if label and description:
        return f"{label}\n\n{description}"
    return label or description


def format_risk_severity_tooltip(severity: str) -> str:
    """Tooltip závažnosti z číselníku (stejný popis jako v editoru Posouzení)."""
    if not severity or severity not in RISK_SEVERITY_DESCRIPTIONS:
        return ""
    return format_severity_tooltip(
        label=format_risk_severity_label(severity),
        description=format_risk_severity_description(severity),
    )
