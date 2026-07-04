import re

_NEGATIVE_MARKERS = (
    "neprobíh",
    "neproběh",
    "chybí",
    "chyba",
    "není",
    "nezajišt",
    "nedostateč",
    "neúpln",
    "nevhodn",
    "chybn",
    "zanedban",
    "porušen",
    "chyběj",
    "absence",
    "nedodrž",
    "neřešen",
    "problém",
    "nedostateč",
    "opakovan",
)

_IMPERATIVE_PREFIXES = (
    "doplnit",
    "zajistit",
    "upřesnit",
    "provést",
    "zavést",
    "aktualizovat",
    "dokončit",
    "opravit",
    "odstranit",
    "zkontrolovat",
    "navrhnout",
    "zlepšit",
    "posílit",
)

_POSITIVE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"probíhají\s+pravideln", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"probíhá\s+pravideln", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"kontrol.*\s+probíhají", re.I), "Neprobíhají pravidelné kontroly pracovišť."),
    (re.compile(r"přístup\s+.*\s+je\s+voln", re.I), "Přístup k hydrantu není volný."),
    (re.compile(r"je\s+schválen", re.I), "Politika není schválena nebo není dostupná zaměstnancům."),
    (re.compile(r"jsou\s+schválen", re.I), "Politiky nejsou schváleny nebo nejsou dostupné zaměstnancům."),
)


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def is_problem_statement(label: str) -> bool:
    lower = label.lower().strip()
    if any(lower.startswith(prefix) for prefix in _IMPERATIVE_PREFIXES):
        return True
    return any(marker in lower for marker in _NEGATIVE_MARKERS)


def normalize_attention_problem(label: str) -> str | None:
    """Převede auditní tvrzení na formulaci skutečného problému."""
    label = _text(label)
    if not label or label == "—":
        return None
    if is_problem_statement(label):
        return label

    lower = label.lower()
    for pattern, replacement in _POSITIVE_REPLACEMENTS:
        if pattern.search(lower):
            return replacement

    if re.search(r"\bje\s+", lower) and "není" not in lower:
        inverted = re.sub(r"\bje\b", "není", label, count=1, flags=re.I)
        if inverted.lower() != lower:
            return inverted
    if re.search(r"\bjsou\s+", lower) and "nejsou" not in lower:
        inverted = re.sub(r"\bjsou\b", "nejsou", label, count=1, flags=re.I)
        if inverted.lower() != lower:
            return inverted
    if re.search(r"\bprobíhají\b", lower):
        return "Neprobíhají pravidelné kontroly pracovišť."

    return None
