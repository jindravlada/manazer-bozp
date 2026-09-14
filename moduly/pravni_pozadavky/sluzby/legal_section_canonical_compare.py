"""Kanonické porovnání znění 3.4.5 (HTML) a Open Data.

Slouží jen k rozhodnutí, zda nastala skutečná obsahová novelizace.
Uložený strom se nemění. Diff po nalezení změny používá nový strom.
"""

from __future__ import annotations

import re
from collections import Counter

from moduly.pravni_pozadavky.constants import (
    SECTION_ATTACHMENT,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_PART,
)

_HIERARCHY_PREFIXES = ("cast:", "hlava:", "dil:")

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_DASH_RE = re.compile(r"[–—−]")
_QUOTE_RE = re.compile(r"[„“”«»]")
_THOUSANDS_RE = re.compile(r"(?<=\d) (?=\d{3}(?:\D|$))")
_PUNCT_SPACE_RE = re.compile(r"\s*([,.;:!?])\s*")
_ITEM_SPLIT_RE = re.compile(r"(?:(?<=\s)|(?<=^))(\d+)\.\s+")
_WORD_RE = re.compile(r"[0-9a-záčďéěíňóřšťúůýž]+", re.IGNORECASE)
_FOOTNOTE_RE = re.compile(
    r"(?<=[A-Za-zÁČĎÉĚÍŇÓŘŠŤÚŮÝŽáčďéěíňóřšťúůýž]{2})\d{1,3}[a-z]?\)"
    r"|(?<=[.,;:\"”'\s])\d{1,3}[a-z]?\)"
    r"|(?<=\d)\d{1,2}[a-z]?\)",
    re.UNICODE,
)
_CATEGORY_PAREN_RE = re.compile(r"(?<=[a-z]\d)\)", re.IGNORECASE)
_ORDINAL = (
    r"první|druhý|druhá|třetí|čtvrtý|čtvrtá|pátý|pátá|šestý|šestá|"
    r"sedmý|sedmá|osmý|osmá|devátý|devátá|desátý|desátá|"
    r"[a-záčďéěíňóřšťúůýž]+tý|[a-záčďéěíňóřšťúůýž]+tá"
)
_LEAKED_STRUCTURE_RE = re.compile(
    rf"\s+(?:"
    rf"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]+\s+ČÁST"
    rf"|ČÁST\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ0-9]+"
    rf"|(?:{_ORDINAL})\s+(?:oddíl|díl|část)"
    rf"|(?:oddíl|díl|část)\s+(?:{_ORDINAL}|[ivxlcdm]+|\d+)"
    rf").*$",
    re.IGNORECASE | re.DOTALL,
)
_BOILERPLATE_RE = re.compile(
    r"\b(?:zrušovací ustanovení|zrušují se:?|zrušuje se:?)\b",
    re.IGNORECASE,
)
_TRAILING_HEADING_RE = re.compile(r"\n[^\n.]{3,80}$")
_NUMBERED_START_RE = re.compile(r"^\s*\d+\.\s")


def canonical_trees_content_equal(*, stored_entries: list, parsed_entries: list) -> bool:
    stored_units = _collapse_to_paragraph(_content_units(stored_entries))
    parsed_units = _collapse_to_paragraph(_content_units(parsed_entries))
    stored_units = _roll_unmatched_into_parents(stored_units, parsed_units)
    parsed_units = _roll_unmatched_into_parents(parsed_units, stored_units)

    stored_keys = set(stored_units)
    parsed_keys = set(parsed_units)
    for key in stored_keys & parsed_keys:
        if not _texts_compatible(stored_units[key], parsed_units[key]):
            return False

    leftover_stored = " ".join(stored_units[key] for key in sorted(stored_keys - parsed_keys))
    leftover_parsed = " ".join(parsed_units[key] for key in sorted(parsed_keys - stored_keys))
    if leftover_stored.strip() or leftover_parsed.strip():
        return _texts_compatible(leftover_stored, leftover_parsed)
    return True


def canonical_compare_text(value: str | None) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u202f", " ")
    text = text.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
    text = text.replace("º", "°")
    text = _DASH_RE.sub("-", text)
    text = _QUOTE_RE.sub('"', text)
    text = _FOOTNOTE_RE.sub("", text)
    text = _CATEGORY_PAREN_RE.sub("", text)
    text = _LEAKED_STRUCTURE_RE.sub("", text)
    text = _BOILERPLATE_RE.sub(" ", text)
    text = _TRAILING_HEADING_RE.sub("", text)
    previous = None
    while previous != text:
        previous = text
        text = _THOUSANDS_RE.sub("", text)
    text = _PUNCT_SPACE_RE.sub(r"\1 ", text)
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()


def _content_units(entries: list) -> dict[str, str]:
    units: dict[str, str] = {}
    for entry in entries:
        key = _canonical_identity_key(entry.identity_key)
        if not key or _is_ignored_key(key):
            continue
        text = getattr(entry, "canonical_text", "") or getattr(entry, "text", "") or ""
        units[key] = f"{units[key]} {text}".strip() if key in units else text
    return units


def _collapse_to_paragraph(units: dict[str, str]) -> dict[str, str]:
    collapsed: dict[str, str] = {}
    for key, text in units.items():
        target = key.split("/", 1)[0] if key.startswith("§:") else key
        collapsed[target] = f"{collapsed.get(target, '')} {text}".strip()
    return collapsed


def _canonical_identity_key(identity_key: str) -> str:
    parts = [
        part
        for part in (identity_key or "").split("/")
        if not part.startswith(_HIERARCHY_PREFIXES)
    ]
    return "/".join(parts)


def _is_ignored_key(identity_key: str) -> bool:
    if identity_key.startswith("priloha:"):
        return True
    last = identity_key.split("/")[-1]
    kind = last.split(":", 1)[0]
    return kind in {SECTION_PART, SECTION_HEAD, SECTION_DIVISION, SECTION_ATTACHMENT}


def _roll_unmatched_into_parents(source: dict[str, str], other: dict[str, str]) -> dict[str, str]:
    rolled = dict(source)
    unmatched = sorted(
        (key for key in rolled if key not in other),
        key=lambda key: key.count("/"),
        reverse=True,
    )
    for key in unmatched:
        parent = key.rsplit("/", 1)[0] if "/" in key else ""
        while parent:
            if parent in other or parent in rolled:
                rolled[parent] = f"{rolled.get(parent, '')} {rolled.pop(key)}".strip()
                break
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
    return rolled


def _texts_compatible(left: str, right: str) -> bool:
    left_norm = canonical_compare_text(left)
    right_norm = canonical_compare_text(right)
    if left_norm == right_norm:
        return True
    left_items = _item_bag(left_norm)
    right_items = _item_bag(right_norm)
    if left_items and left_items == right_items:
        return True
    if _word_set(left_norm) == _word_set(right_norm):
        return True
    if _is_parser_dump(left_norm, right_norm):
        return True
    return False


def _item_bag(text: str) -> Counter[str]:
    if not text:
        return Counter()
    parts = _ITEM_SPLIT_RE.split(text)
    items: list[str] = []
    if parts and parts[0].strip():
        items.append(parts[0].strip())
    for index in range(1, len(parts), 2):
        chunk = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if chunk:
            items.append(chunk)
    return Counter(items)


def _word_set(text: str) -> frozenset[str]:
    return frozenset(word for word in _WORD_RE.findall(text) if len(word) > 1)


def _is_parser_dump(left: str, right: str) -> bool:
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if not shorter:
        return False
    if len(longer) < 8 * max(len(shorter), 1):
        if shorter in longer and len(longer) >= int(1.6 * max(len(shorter), 1)):
            return True
        return False
    if _word_set(shorter) <= _word_set(longer):
        return True
    if _NUMBERED_START_RE.match(longer) and "nabývá účinnosti" in shorter:
        return True
    return False
