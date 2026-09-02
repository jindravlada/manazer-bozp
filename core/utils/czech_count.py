"""České tvary počítaných podstatných jmen podle číselně zapsaného počtu.

Pravidlo je určené pro reporty: rozhoduje celé číslo, ne poslední číslice.
Bez Qt, databáze a vazby na konkrétní modul.
"""

from enum import Enum


class CzechCountForm(Enum):
    """Tvar podstatného jména podle číselně zapsaného počtu."""

    ONE = "one"
    FEW = "few"
    MANY = "many"


_COUNT_NOT_NONNEGATIVE_INT = "count musí být nezáporné celé číslo."
_FORM_EMPTY = "tvar {name} musí být neprázdný řetězec."


def _require_nonnegative_int(count: object) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError(_COUNT_NOT_NONNEGATIVE_INT)
    if count < 0:
        raise ValueError(_COUNT_NOT_NONNEGATIVE_INT)
    return count


def _require_form(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(_FORM_EMPTY.format(name=name))
    text = value.strip()
    if not text:
        raise ValueError(_FORM_EMPTY.format(name=name))
    return text


def czech_count_form(count: int) -> CzechCountForm:
    """Vrátí ONE / FEW / MANY pro číselně zapsaný nezáporný počet."""
    value = _require_nonnegative_int(count)
    if value == 1:
        return CzechCountForm.ONE
    if value in (2, 3, 4):
        return CzechCountForm.FEW
    return CzechCountForm.MANY


def format_czech_count(
    count: int,
    *,
    one: str,
    few: str,
    many: str,
) -> str:
    """Spojí počet s ořezaným tvarem slova, např. ``5 příležitostí``."""
    form = czech_count_form(count)
    words = {
        CzechCountForm.ONE: _require_form(one, name="one"),
        CzechCountForm.FEW: _require_form(few, name="few"),
        CzechCountForm.MANY: _require_form(many, name="many"),
    }
    return f"{count} {words[form]}"
