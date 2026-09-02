"""Gramaticky správné klauzule o zjištěných položkách ženského rodu.

Určeno pro reporty kontrol (prověrky, audity). Bez Qt.
Používá `czech_count_form` a `format_czech_count`.
"""

from collections.abc import Sequence

from core.utils.czech_count import CzechCountForm, czech_count_form, format_czech_count

_FEMININE_FOUND_VERBS = {
    CzechCountForm.ONE: "byla zjištěna",
    CzechCountForm.FEW: "byly zjištěny",
    CzechCountForm.MANY: "bylo zjištěno",
}

ZAVADA_FORMS = {
    "one": "závada",
    "few": "závady",
    "many": "závad",
}

NESHODA_FORMS = {
    "one": "neshoda",
    "few": "neshody",
    "many": "neshod",
}

PRILEZITOST_FORMS = {
    "one": "příležitost ke zlepšení",
    "few": "příležitosti ke zlepšení",
    "many": "příležitostí ke zlepšení",
}


def format_feminine_found_clause(
    count: int,
    *,
    one: str,
    few: str,
    many: str,
) -> str:
    """Vrátí klauzuli typu ``bylo zjištěno 5 závad``."""
    form = czech_count_form(count)
    counted = format_czech_count(count, one=one, few=few, many=many)
    return f"{_FEMININE_FOUND_VERBS[form]} {counted}"


def join_found_clauses(clauses: Sequence[str]) -> str:
    """Spojí 1–2 klauzule bez společného přísudku."""
    cleaned = [str(item).strip() for item in clauses if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return f"{cleaned[0]} a {cleaned[1]}"


def format_during_found_sentence(
    *,
    during: str,
    clauses: Sequence[str],
    empty: str,
) -> str:
    """Sestaví větu ``Během … {klauzule}.`` nebo vrátí ``empty``."""
    joined = join_found_clauses(clauses)
    if not joined:
        return empty
    return f"{during.strip()} {joined}."
