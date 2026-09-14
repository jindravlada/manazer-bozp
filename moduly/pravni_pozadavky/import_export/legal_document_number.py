import re

_NUMBER_YEAR_RE = re.compile(
    r"^(\d+)(?:\s*/\s*(\d{4})\s*(?:Sb\.?)?)?$",
    re.IGNORECASE,
)


def normalize_legal_act_number_and_year(
    number: str,
    year: int | str | None,
) -> tuple[str, int]:
    """Vrátí digit-only číslo a rok pro online kontrolu e-Sbírky.

    Přijme `262`, `262/2006` i `262/2006 Sb.` Při vlastním roku v čísle
    musí souhlasit s předaným rokem.
    """
    raw_number = (number or "").strip()
    if not raw_number:
        raise ValueError("Číslo předpisu je povinné.")

    match = _NUMBER_YEAR_RE.fullmatch(raw_number)
    if match is None:
        raise ValueError("Číslo předpisu smí obsahovat pouze číslice.")

    normalized_number = match.group(1)
    embedded_year_text = match.group(2)

    parsed_year: int | None = None
    if isinstance(year, bool):
        raise ValueError("Rok musí být číslo.")
    if isinstance(year, int):
        parsed_year = year
    elif year is not None:
        year_text = str(year).strip()
        if not year_text.isdigit():
            raise ValueError("Rok musí být číslo.")
        parsed_year = int(year_text)

    if embedded_year_text is not None:
        embedded_year = int(embedded_year_text)
        if parsed_year is not None and parsed_year != embedded_year:
            raise ValueError("Číslo předpisu a rok se neshodují.")
        parsed_year = embedded_year

    if parsed_year is None:
        raise ValueError("Rok předpisu je povinný.")
    if parsed_year < 1 or parsed_year > 9999:
        raise ValueError("Rok musí být číslo.")
    return normalized_number, parsed_year
