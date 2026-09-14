from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from typing import Sequence

from moduly.pravni_pozadavky.constants import (
    SECTION_ATTACHMENT,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    ESbirkaOpenDataFragmentContent,
    ESbirkaOpenDataFragmentRef,
    ESbirkaOpenDataWordingDocument,
    legal_document_esbirka_opendata_client,
)
from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_VAR_RE = re.compile(r"<var>(.*?)</var>", re.DOTALL | re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+", re.UNICODE)
_LEADING_LETTER_RE = re.compile(
    r"^[a-záčďéěíňóřšťúůýž]\)\s*",
    re.IGNORECASE,
)
_LEADING_SUBSECTION_RE = re.compile(r"^\(\d+[a-z]?\)\s*")
_PATH_SEGMENT_RE = re.compile(r"^([A-Za-z]+)(?:_([A-Za-z0-9.:-]+))?$")
_INT_RE = re.compile(r"^(\d+)")

_STRUCTURAL_KINDS = {
    "cast": SECTION_PART,
    "hlava": SECTION_HEAD,
    "dil": SECTION_DIVISION,
    "par": SECTION_PARAGRAPH,
    "odst": SECTION_SUBSECTION,
    "pism": SECTION_LETTER,
    "priloha": SECTION_ATTACHMENT,
}
_HEADING_TYPES = {"Nadpis", "Nadpis_pod", "Nadpis_nad"}
_BODY_TYPES = {
    "Odstavec_Dc",
    "Pokracovani_Text",
    "Tabulka",
    "Bod_Dd",
    "Hlavicka_priloha",
}
_CZECH_ORDINALS = {
    1: "PRVNÍ",
    2: "DRUHÁ",
    3: "TŘETÍ",
    4: "ČTVRTÁ",
    5: "PÁTÁ",
    6: "ŠESTÁ",
    7: "SEDMÁ",
    8: "OSMÁ",
    9: "DEVÁTÁ",
    10: "DESÁTÁ",
    11: "JEDENÁCTÁ",
    12: "DVANÁCTÁ",
    13: "TŘINÁCTÁ",
    14: "ČTRNÁCTÁ",
    15: "PATNÁCTÁ",
    16: "ŠESTNÁCTÁ",
    17: "SEDMNÁCTÁ",
    18: "OSMNÁCTÁ",
    19: "DEVATENÁCTÁ",
    20: "DVACÁTÁ",
}
_ROMAN = (
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


@dataclass(frozen=True)
class ESbirkaOpenDataParsedTree:
    source_eli: str
    source_url: str
    effective_from: date | None
    version_label: str
    sections: tuple[ParsedLegalSection, ...]


class LegalDocumentESbirkaOpenDataTreeBuilder:
    def fetch_in_force_tree(
        self,
        *,
        year: int | str,
        number: str,
        on_date: date,
    ) -> ESbirkaOpenDataParsedTree:
        wording = legal_document_esbirka_opendata_client.fetch_in_force_wording_fragments(
            year=year,
            number=number,
            on_date=on_date,
        )
        contents = legal_document_esbirka_opendata_client.fetch_wording_fragment_contents(
            wording.source_eli,
        )
        sections = self.build_parsed_sections(wording, contents)
        return ESbirkaOpenDataParsedTree(
            source_eli=wording.source_eli,
            source_url=wording.source_url,
            effective_from=wording.effective_from,
            version_label=f"e-Sbírka {wording.source_eli}",
            sections=tuple(sections),
        )

    def fetch_in_force_parsed_sections(
        self,
        *,
        year: int | str,
        number: str,
        on_date: date,
    ) -> list[ParsedLegalSection]:
        return list(self.fetch_in_force_tree(year=year, number=number, on_date=on_date).sections)

    def build_parsed_sections(
        self,
        wording: ESbirkaOpenDataWordingDocument,
        contents: Sequence[ESbirkaOpenDataFragmentContent],
    ) -> list[ParsedLegalSection]:
        content_by_eli = {
            item.fragment_eli: item
            for item in contents
            if item.fragment_eli
        }
        if not content_by_eli:
            raise ValueError("Neočekávaný formát odpovědi.")

        structural = [
            fragment
            for fragment in wording.fragments
            if self._is_structural_fragment(fragment)
        ]
        if not structural:
            raise ValueError("Neočekávaný formát odpovědi.")
        if not any(
            fragment.fragment_eli in content_by_eli
            or any(
                child.fragment_eli.startswith(f"{fragment.fragment_eli}/")
                for child in wording.fragments
                if child.fragment_eli in content_by_eli
            )
            for fragment in structural
        ):
            raise ValueError("Neočekávaný formát odpovědi.")

        structural.sort(key=self._fragment_sort_key)
        path_to_fragment = {
            self._document_path(fragment): fragment for fragment in structural
        }
        parsed: list[ParsedLegalSection] = []
        path_to_sort: dict[str, int] = {}
        sort_order = 0
        for fragment in structural:
            sort_order += 1
            path = self._document_path(fragment)
            path_to_sort[path] = sort_order
            section_type = _STRUCTURAL_KINDS[fragment.section_kind]
            title, text = self._title_and_text(
                fragment,
                content_by_eli=content_by_eli,
                fragments=wording.fragments,
                structural_paths=path_to_fragment,
            )
            parsed.append(
                ParsedLegalSection(
                    section_type=section_type,
                    section_number=self._section_number(fragment, section_type),
                    paragraph=self._paragraph_number(fragment, section_type),
                    item_letter=self._item_letter(fragment, section_type),
                    title=title,
                    text=text,
                    sort_order=sort_order,
                    parent_sort_order=self._parent_sort_order(path, path_to_sort),
                )
            )
        return parsed

    def _is_structural_fragment(self, fragment: ESbirkaOpenDataFragmentRef) -> bool:
        if fragment.section_kind not in _STRUCTURAL_KINDS:
            return False
        if fragment.section_kind == "priloha":
            return fragment.document_part == "prilohy"
        return fragment.document_part == "norma"

    def _document_path(self, fragment: ESbirkaOpenDataFragmentRef) -> str:
        return "/".join(fragment.path_segments)

    def _parent_sort_order(self, path: str, path_to_sort: dict[str, int]) -> int | None:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        while parent:
            if parent in path_to_sort:
                return path_to_sort[parent]
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
        return None

    def _section_number(self, fragment: ESbirkaOpenDataFragmentRef, section_type: str) -> str:
        if section_type == SECTION_PARAGRAPH:
            return ""
        if section_type == SECTION_LETTER:
            return ""
        if section_type == SECTION_PART:
            return self._czech_ordinal(fragment.section_number)
        if section_type == SECTION_HEAD:
            return self._roman(fragment.section_number)
        if section_type == SECTION_ATTACHMENT and fragment.section_number in {"", "0"}:
            return ""
        return fragment.section_number

    def _paragraph_number(self, fragment: ESbirkaOpenDataFragmentRef, section_type: str) -> str:
        if section_type == SECTION_PARAGRAPH:
            return fragment.section_number
        return ""

    def _item_letter(self, fragment: ESbirkaOpenDataFragmentRef, section_type: str) -> str:
        if section_type == SECTION_LETTER:
            return fragment.section_number.casefold()
        return ""

    def _title_and_text(
        self,
        fragment: ESbirkaOpenDataFragmentRef,
        *,
        content_by_eli: dict[str, ESbirkaOpenDataFragmentContent],
        fragments: Sequence[ESbirkaOpenDataFragmentRef],
        structural_paths: dict[str, ESbirkaOpenDataFragmentRef],
    ) -> tuple[str, str]:
        own = content_by_eli.get(fragment.fragment_eli)
        headings: list[str] = []
        bodies: list[str] = []
        if own is not None:
            own_text = self._plain_text(own.html)
            if own.fragment_type in _HEADING_TYPES:
                if fragment.section_kind in {"cast", "hlava", "dil"}:
                    bodies.append(own_text)
                else:
                    headings.append(own_text)
            elif not self._is_label_only(fragment, own_text):
                bodies.append(self._strip_inline_marker(fragment, own_text))

        own_path = self._document_path(fragment)
        prefix = f"{own_path}/"
        for child in fragments:
            if child.fragment_eli == fragment.fragment_eli:
                continue
            child_path = self._document_path(child)
            if not child_path.startswith(prefix):
                continue
            if fragment.section_kind != "priloha":
                remainder = child_path[len(prefix) :]
                if "/" in remainder and remainder.split("/", 1)[0] != child.path_segments[-1]:
                    continue
                if child_path in structural_paths:
                    continue
                if child.section_kind not in {"frag", "bod"} and child.section_kind in _STRUCTURAL_KINDS:
                    continue
            content = content_by_eli.get(child.fragment_eli)
            if content is None:
                continue
            text = self._plain_text(content.html)
            if not text:
                continue
            if content.fragment_type in _HEADING_TYPES:
                if fragment.section_kind in {"cast", "hlava", "dil"}:
                    bodies.append(text)
                else:
                    headings.append(text)
            elif content.fragment_type in _BODY_TYPES or child.section_kind in {"frag", "bod"}:
                bodies.append(self._strip_inline_marker(fragment, text))
            elif fragment.section_kind == "priloha":
                bodies.append(text)

        title = self._join_parts(headings)
        body = self._join_parts(bodies)
        if fragment.section_kind == "priloha" and not title:
            number = fragment.section_number
            if number and number != "0":
                title = f"Příloha č. {number}"
        if fragment.section_kind == "par" and not title:
            title = body
            body = ""
        return title, body

    def _plain_text(self, html: str) -> str:
        content = _BR_RE.sub(" ", html or "")
        content = _VAR_RE.sub(r"\1", content)
        text = _TAG_RE.sub("", content)
        text = unescape(text)
        return _SPACE_RE.sub(" ", text).strip()

    def _is_label_only(self, fragment: ESbirkaOpenDataFragmentRef, text: str) -> bool:
        normalized = _SPACE_RE.sub(" ", text).strip()
        if not normalized:
            return True
        folded = normalized.casefold()
        number = fragment.section_number.casefold()
        if fragment.section_kind == "par":
            return folded in {f"§ {number}", f"§{number}"}
        if fragment.section_kind == "pism":
            return folded in {f"{number})", f"{number}."}
        if fragment.section_kind == "odst":
            return folded in {f"({number})", f"odst. {number}"}
        if fragment.section_kind == "cast":
            return folded.startswith("část ")
        if fragment.section_kind == "hlava":
            return folded.startswith("hlava ")
        if fragment.section_kind == "dil":
            return folded.startswith("díl ")
        if fragment.section_kind == "priloha":
            return folded.startswith("příloha") and len(normalized) < 40
        return False

    def _strip_inline_marker(self, fragment: ESbirkaOpenDataFragmentRef, text: str) -> str:
        if fragment.section_kind == "pism":
            return _LEADING_LETTER_RE.sub("", text).strip()
        if fragment.section_kind == "odst":
            return _LEADING_SUBSECTION_RE.sub("", text).strip()
        if fragment.section_kind == "par":
            return _LEADING_SUBSECTION_RE.sub("", text).strip()
        return text

    def _join_parts(self, parts: list[str]) -> str:
        cleaned = [item for item in parts if item]
        return "\n".join(cleaned)

    def _fragment_sort_key(self, fragment: ESbirkaOpenDataFragmentRef):
        part_rank = 0 if fragment.document_part == "norma" else 1
        keys = []
        for segment in fragment.path_segments:
            match = _PATH_SEGMENT_RE.fullmatch(segment)
            if match is None:
                keys.append((99, 0, segment))
                continue
            kind = match.group(1).casefold()
            raw = match.group(2) or ""
            number_match = _INT_RE.match(raw)
            number = int(number_match.group(1)) if number_match else 0
            keys.append((_kind_rank(kind), number, raw.casefold()))
        return (part_rank, tuple(keys))

    def _czech_ordinal(self, value: str) -> str:
        try:
            number = int(value)
        except ValueError:
            return value
        return _CZECH_ORDINALS.get(number, value)

    def _roman(self, value: str) -> str:
        try:
            number = int(value)
        except ValueError:
            return value
        if number <= 0:
            return value
        remaining = number
        parts: list[str] = []
        for amount, glyph in _ROMAN:
            while remaining >= amount:
                parts.append(glyph)
                remaining -= amount
        return "".join(parts) or value


def _kind_rank(kind: str) -> int:
    order = {
        "norma": 0,
        "prilohy": 0,
        "cast": 1,
        "priloha": 1,
        "hlava": 2,
        "dil": 3,
        "oddil": 4,
        "par": 5,
        "odst": 6,
        "pism": 7,
        "bod": 8,
        "frag": 9,
    }
    return order.get(kind, 50)


legal_document_esbirka_opendata_tree_builder = LegalDocumentESbirkaOpenDataTreeBuilder()
