"""Pomocné funkce pro textové vyhledávání (V1 — bez FTS)."""


def normalize_query(query: str) -> str:
    return query.strip().lower()


def contains_query(query: str, *values: object) -> bool:
    if not query:
        return False
    haystack = " ".join(str(value or "") for value in values).lower()
    if query in haystack:
        return True
    for token in haystack.split():
        if query in token or token in query:
            return True
    return False
