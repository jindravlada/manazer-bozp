import re
import unicodedata


# Česká abeceda včetně CH jako samostatného písmene za H.
_CZ_ORDER = {
    "a": 1, "á": 1,
    "b": 2,
    "c": 3,
    "č": 4,
    "d": 5,
    "ď": 6,
    "e": 7, "é": 7, "ě": 7,
    "f": 8,
    "g": 9,
    "h": 10,
    "ch": 11,
    "i": 12, "í": 12,
    "j": 13,
    "k": 14,
    "l": 15,
    "m": 16,
    "n": 17,
    "ň": 18,
    "o": 19, "ó": 19,
    "p": 20,
    "q": 21,
    "r": 22,
    "ř": 23,
    "s": 24,
    "š": 25,
    "t": 26,
    "ť": 27,
    "u": 28, "ú": 28, "ů": 28,
    "v": 29,
    "w": 30,
    "x": 31,
    "y": 32, "ý": 32,
    "z": 33,
    "ž": 34,
}


_TITLES = {
    "bc", "bc.", "ing", "ing.", "mgr", "mgr.", "mudr", "mudr.",
    "judr", "judr.", "phdr", "phdr.", "rndr", "rndr.",
    "doc", "doc.", "prof", "prof.", "dis", "dis.",
    "mba", "llm", "ll.m", "ll.m.", "phd", "ph.d", "ph.d.",
}


def _normalize(value) -> str:
    return unicodedata.normalize("NFC", str(value or "").strip().lower())


def _split_natural(text: str):
    return re.split(r"(\d+)", text)


def _text_key(text: str):
    """
    Vrací porovnatelný klíč pro text podle české abecedy.

    Důležité:
    - Č je hned za C.
    - Š je hned za S.
    - Ž je hned za Z.
    - CH je samostatné písmeno za H.
    """
    text = _normalize(text)
    result = []

    i = 0
    while i < len(text):
        if text[i:i + 2] == "ch":
            result.append((0, _CZ_ORDER["ch"], "ch"))
            i += 2
            continue

        char = text[i]
        if char in _CZ_ORDER:
            result.append((0, _CZ_ORDER[char], char))
        else:
            result.append((1, ord(char), char))

        i += 1

    return tuple(result)


def czech_sort_key(value):
    """
    Globální český řadicí klíč pro celý MB 3.0.

    Používat místo:
    - sorted(...)
    - list.sort(...)
    - SQL ORDER BY pro textové položky
    """
    text = _normalize(value)
    key = []

    for token in _split_natural(text):
        if token.isdigit():
            key.append((0, int(token)))
        else:
            key.append((1, _text_key(token)))

    return tuple(key)


def czech_sorted(items, key=None, reverse: bool = False):
    if key is None:
        return sorted(items, key=czech_sort_key, reverse=reverse)

    return sorted(items, key=lambda item: czech_sort_key(key(item)), reverse=reverse)


def person_display_name_sort_key(text: str) -> str:
    """
    Textové jméno typu:
    - Ing. Vladimír Jindra
    - PhDr. Zdeněk Testovací, Ph.D.

    vrací klíč:
    - Jindra Vladimír
    - Testovací Zdeněk

    Tedy zobrazení může zůstat Jméno Příjmení,
    ale řazení je podle příjmení.
    """
    text = str(text or "").replace(",", " ").strip()
    parts = [part for part in text.split() if part.strip()]

    clean = []
    for part in parts:
        normalized = part.lower().strip()
        if normalized in _TITLES:
            continue
        clean.append(part)

    if len(clean) >= 2:
        return f"{clean[-1]} {' '.join(clean[:-1])}"

    return " ".join(clean) or text


def worker_sort_key(worker) -> str:
    """
    Řazení THP pracovníků podle příjmení.
    Funguje pro různé názvy atributů napříč vývojem MB 3.0.
    """
    last_name = (
        getattr(worker, "last_name", "")
        or getattr(worker, "surname", "")
        or getattr(worker, "prijmeni", "")
        or getattr(worker, "last", "")
        or ""
    )
    first_name = (
        getattr(worker, "first_name", "")
        or getattr(worker, "first", "")
        or getattr(worker, "jmeno", "")
        or ""
    )

    if last_name:
        return f"{last_name} {first_name}"

    return person_display_name_sort_key(getattr(worker, "display_name", "") or "")
