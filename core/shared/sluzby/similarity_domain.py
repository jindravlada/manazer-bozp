"""Registry oblastí pro obecnou Analýzu podobností (SIMILARITY-10)."""

from __future__ import annotations

from dataclasses import dataclass

from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_AUDIT_ASSERTION,
    SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
    SIMILARITY_ENTITY_MEASURE,
    SIMILARITY_ENTITY_PBP,
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    SIMILARITY_ENTITY_RISK,
)

# Klíče oblastí v UI / registry (stabilní identifikátory výběru).
SCOPE_PROVERKY = "proverky_kontrolni_otazky"
SCOPE_PBP = "pbp"
SCOPE_AUDIT = "auditni_tvrzeni"
SCOPE_RISKS = "rizika"
SCOPE_MEASURES = "opatreni"
SCOPE_LEGAL = "pravni_pozadavky"

# Orientační limity počtu porovnání pro odhad času a potvrzení.
SIMILARITY_TIME_FEW_SECONDS = 50_000
SIMILARITY_TIME_ONE_MINUTE = 500_000
SIMILARITY_TIME_FEW_MINUTES = 5_000_000
SIMILARITY_LARGE_ANALYSIS_THRESHOLD = 10_000_000


@dataclass(frozen=True)
class SimilarityDomainDef:
    """Definice podporované oblasti analýzy."""

    key: str
    label: str
    entity_type: str


SIMILARITY_DOMAINS: tuple[SimilarityDomainDef, ...] = (
    SimilarityDomainDef(
        SCOPE_PROVERKY,
        "Kontrolní otázky prověrek",
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    ),
    SimilarityDomainDef(
        SCOPE_PBP,
        "Pravidla bezpečné práce",
        SIMILARITY_ENTITY_PBP,
    ),
    SimilarityDomainDef(
        SCOPE_AUDIT,
        "Auditní tvrzení",
        SIMILARITY_ENTITY_AUDIT_ASSERTION,
    ),
    SimilarityDomainDef(
        SCOPE_RISKS,
        "Rizika",
        SIMILARITY_ENTITY_RISK,
    ),
    SimilarityDomainDef(
        SCOPE_MEASURES,
        "Opatření",
        SIMILARITY_ENTITY_MEASURE,
    ),
    SimilarityDomainDef(
        SCOPE_LEGAL,
        "Právní požadavky",
        SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
    ),
)

# Zpětná kompatibilita se starším SIMILARITY_SCOPE_DEFS (key, label, implemented).
SIMILARITY_SCOPE_DEFS = tuple(
    (domain.key, domain.label, True) for domain in SIMILARITY_DOMAINS
)


def domain_by_key(key: str) -> SimilarityDomainDef | None:
    for domain in SIMILARITY_DOMAINS:
        if domain.key == key:
            return domain
    return None


def domain_label(key: str) -> str:
    domain = domain_by_key(key)
    return domain.label if domain is not None else str(key)


def entity_type_for_scope(scope_key: str) -> str:
    domain = domain_by_key(scope_key)
    if domain is None:
        raise ValueError(f"Neznámá oblast podobností: {scope_key}")
    return domain.entity_type


def pair_entity_type_for_scopes(scope_a: str, scope_b: str) -> str:
    """Typ evidence zkontrolované dvojice pro danou kombinaci oblastí."""
    left = entity_type_for_scope(scope_a)
    right = entity_type_for_scope(scope_b)
    if left == right:
        return left
    first, second = sorted((left, right))
    return f"cross:{first}:{second}"


def estimate_comparison_count(count_a: int, count_b: int, *, same_domain: bool) -> int:
    """Přibližný počet porovnání (bez porovnání položky se sebou)."""
    a = max(0, int(count_a))
    b = max(0, int(count_b))
    if same_domain:
        if a < 2:
            return 0
        return a * (a - 1) // 2
    return a * b


def estimate_duration_label(comparison_count: int) -> str:
    """Orientační odhad doby zpracování."""
    n = max(0, int(comparison_count))
    if n <= SIMILARITY_TIME_FEW_SECONDS:
        return "≈ několik sekund"
    if n <= SIMILARITY_TIME_ONE_MINUTE:
        return "≈ do 1 minuty"
    if n <= SIMILARITY_TIME_FEW_MINUTES:
        return "≈ 2–5 minut"
    return "≈ více než 5 minut"


def requires_large_analysis_confirmation(comparison_count: int) -> bool:
    return int(comparison_count) > SIMILARITY_LARGE_ANALYSIS_THRESHOLD
