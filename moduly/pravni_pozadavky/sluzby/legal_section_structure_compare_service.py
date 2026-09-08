import re
from dataclasses import dataclass, field, replace

from moduly.pravni_pozadavky.constants import (
    SECTION_ATTACHMENT,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
    SECTION_TYPE_LABELS,
    legal_document_regulation_number,
)
from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_section_compare_text(value: str | None) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u202f", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def section_own_compare_text(section) -> str:
    text = getattr(section, "text", "") or ""
    if text.strip():
        return text
    return getattr(section, "title", "") or ""


@dataclass(frozen=True)
class SectionStructureEntry:
    identity_key: str
    log_label: str
    fingerprint: str
    text: str = ""
    old_text: str | None = None
    new_text: str | None = None


@dataclass
class SectionStructureCompareResult:
    new: list[SectionStructureEntry] = field(default_factory=list)
    removed: list[SectionStructureEntry] = field(default_factory=list)
    changed: list[SectionStructureEntry] = field(default_factory=list)
    unchanged: list[SectionStructureEntry] = field(default_factory=list)

    @property
    def has_structural_changes(self) -> bool:
        return bool(self.new or self.removed or self.changed)

    @property
    def has_changes(self) -> bool:
        return self.has_structural_changes


class LegalSectionStructureCompareService:
    def compare(
        self,
        *,
        stored_sections: list,
        parsed_sections: list[ParsedLegalSection],
    ) -> SectionStructureCompareResult:
        stored_entries = self._build_stored_entries(stored_sections)
        parsed_entries = self._build_parsed_entries(parsed_sections)

        stored_by_key = {entry.identity_key: entry for entry in stored_entries}
        parsed_by_key = {entry.identity_key: entry for entry in parsed_entries}

        result = SectionStructureCompareResult()
        for key, parsed_entry in sorted(parsed_by_key.items()):
            stored_entry = stored_by_key.get(key)
            if stored_entry is None:
                result.new.append(parsed_entry)
            elif stored_entry.fingerprint != parsed_entry.fingerprint:
                result.changed.append(parsed_entry)
            else:
                result.unchanged.append(parsed_entry)

        for key, stored_entry in sorted(stored_by_key.items()):
            if key not in parsed_by_key:
                result.removed.append(stored_entry)

        return result

    def compare_version_sections(
        self,
        *,
        old_sections: list,
        new_sections: list,
    ) -> SectionStructureCompareResult:
        old_entries = self._build_stored_entries(old_sections)
        new_entries = self._build_stored_entries(new_sections)
        old_by_key = {entry.identity_key: entry for entry in old_entries}
        new_by_key = {entry.identity_key: entry for entry in new_entries}

        result = SectionStructureCompareResult()
        for key, new_entry in sorted(new_by_key.items()):
            old_entry = old_by_key.get(key)
            if old_entry is None:
                result.new.append(
                    replace(
                        new_entry,
                        old_text=None,
                        new_text=self._nullable_text(new_entry.text),
                    ),
                )
            elif (
                old_entry.fingerprint != new_entry.fingerprint
                or self._texts_differ(old_entry.text, new_entry.text)
            ):
                result.changed.append(
                    replace(
                        new_entry,
                        old_text=self._nullable_text(old_entry.text),
                        new_text=self._nullable_text(new_entry.text),
                    ),
                )
            else:
                result.unchanged.append(new_entry)

        for key, old_entry in sorted(old_by_key.items()):
            if key not in new_by_key:
                result.removed.append(
                    replace(
                        old_entry,
                        old_text=self._nullable_text(old_entry.text),
                        new_text=None,
                    ),
                )
        return result

    def build_section_key_index(self, sections: list) -> dict[str, int]:
        by_id = {section.id: section for section in sections}
        index: dict[str, int] = {}
        for section in sections:
            chain = self._stored_chain(section, by_id)
            identity_key = "/".join(self._identity_segment(item) for item in chain)
            index[identity_key] = section.id
        return index

    def build_section_log_label(self, section, *, sections_by_id: dict | None = None) -> str:
        by_id = sections_by_id or {section.id: section}
        chain = self._stored_chain(section, by_id)
        return self._log_label(chain)

    def format_check_run_summary(self, *, document, result: SectionStructureCompareResult) -> str:
        doc_number = legal_document_regulation_number(document)
        if not result.has_changes:
            return f"{doc_number} – novelizace bez změny ustanovení."

        parts: list[str] = []
        if result.changed:
            parts.append(f"{len(result.changed)} změněná")
        if result.new:
            parts.append(f"{len(result.new)} nová")
        if result.removed:
            parts.append(f"{len(result.removed)} zrušená")
        return f"{doc_number} – {', '.join(parts)} ustanovení."

    def format_check_run_log(self, *, document, result: SectionStructureCompareResult) -> str:
        lines = [legal_document_regulation_number(document), ""]
        if not result.has_changes:
            lines.append("Novelizace bez změny ustanovení.")
            return "\n".join(lines)

        if result.changed:
            lines.append("Změněná ustanovení:")
            lines.extend(entry.log_label for entry in self._sorted_entries(result.changed))
        if result.new:
            lines.append("Nová ustanovení:")
            lines.extend(entry.log_label for entry in self._sorted_entries(result.new))
        if result.removed:
            lines.append("Zrušená ustanovení:")
            lines.extend(entry.log_label for entry in self._sorted_entries(result.removed))
        return "\n".join(lines)

    def _build_stored_entries(self, sections: list) -> list[SectionStructureEntry]:
        by_id = {section.id: section for section in sections}
        entries: list[SectionStructureEntry] = []
        for section in sections:
            chain = self._stored_chain(section, by_id)
            entries.append(self._build_entry(chain))
        return entries

    def _build_parsed_entries(
        self,
        sections: list[ParsedLegalSection],
    ) -> list[SectionStructureEntry]:
        by_sort_order = {section.sort_order: section for section in sections}
        entries: list[SectionStructureEntry] = []
        for section in sections:
            chain = self._parsed_chain(section, by_sort_order)
            entries.append(self._build_entry(chain))
        return entries

    def _stored_chain(self, section, by_id: dict) -> list:
        chain: list = []
        current = section
        visited: set[int] = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            chain.append(current)
            parent_id = getattr(current, "parent_section_id", None)
            current = by_id.get(parent_id) if parent_id is not None else None
        chain.reverse()
        return chain

    def _parsed_chain(
        self,
        section: ParsedLegalSection,
        by_sort_order: dict[int, ParsedLegalSection],
    ) -> list[ParsedLegalSection]:
        chain: list[ParsedLegalSection] = []
        current: ParsedLegalSection | None = section
        visited: set[int] = set()
        while current is not None and current.sort_order not in visited:
            visited.add(current.sort_order)
            chain.append(current)
            parent_sort_order = current.parent_sort_order
            current = (
                by_sort_order.get(parent_sort_order)
                if parent_sort_order is not None
                else None
            )
        chain.reverse()
        return chain

    def _build_entry(self, chain: list) -> SectionStructureEntry:
        identity_key = "/".join(self._identity_segment(section) for section in chain)
        leaf = chain[-1]
        return SectionStructureEntry(
            identity_key=identity_key,
            log_label=self._log_label(chain),
            fingerprint=self._fingerprint(leaf),
            text=section_own_compare_text(leaf),
        )

    def _texts_differ(self, left: str, right: str) -> bool:
        return normalize_section_compare_text(left) != normalize_section_compare_text(right)

    def _nullable_text(self, value: str) -> str | None:
        return value if (value or "").strip() else None

    def _identity_segment(self, section) -> str:
        section_type = (getattr(section, "section_type", "") or "").strip()
        section_number = (getattr(section, "section_number", "") or "").strip()
        paragraph = (getattr(section, "paragraph", "") or "").strip()
        item_letter = (getattr(section, "item_letter", "") or "").strip()
        title = (getattr(section, "title", "") or "").strip()

        if section_type == SECTION_PART:
            return f"cast:{section_number or title}"
        if section_type == SECTION_HEAD:
            return f"hlava:{section_number or title}"
        if section_type == SECTION_DIVISION:
            return f"dil:{section_number or title}"
        if section_type == SECTION_PARAGRAPH:
            return f"§:{paragraph}"
        if section_type == SECTION_SUBSECTION:
            return f"odst:{section_number}"
        if section_type == SECTION_LETTER:
            return f"pism:{item_letter}"
        if section_type == SECTION_ATTACHMENT:
            return f"priloha:{section_number or title}"
        return f"{section_type}:{section_number or paragraph or item_letter or title}"

    def _fingerprint(self, section) -> str:
        return "|".join(
            [
                (getattr(section, "section_type", "") or "").strip(),
                (getattr(section, "section_number", "") or "").strip(),
                (getattr(section, "paragraph", "") or "").strip(),
                (getattr(section, "item_letter", "") or "").strip(),
                (getattr(section, "title", "") or "").strip(),
            ],
        )

    def _log_label(self, chain: list) -> str:
        paragraph = ""
        subsection = ""
        letter = ""
        attachment = ""
        hierarchy_labels: list[str] = []

        for section in chain:
            section_type = (getattr(section, "section_type", "") or "").strip()
            section_number = (getattr(section, "section_number", "") or "").strip()
            item_letter = (getattr(section, "item_letter", "") or "").strip()
            title = (getattr(section, "title", "") or "").strip()

            if section_type == SECTION_ATTACHMENT:
                if section_number:
                    attachment = f"Příloha č.{section_number}"
                elif title:
                    attachment = title
                else:
                    attachment = "Příloha"
            elif section_type == SECTION_PARAGRAPH:
                paragraph = (getattr(section, "paragraph", "") or "").strip()
            elif section_type == SECTION_SUBSECTION:
                subsection = section_number
            elif section_type == SECTION_LETTER:
                letter = item_letter
            elif section_type in {SECTION_PART, SECTION_HEAD, SECTION_DIVISION}:
                type_label = SECTION_TYPE_LABELS.get(section_type, section_type)
                if section_number:
                    hierarchy_labels.append(f"{type_label} {section_number}")
                elif title:
                    hierarchy_labels.append(title)

        if attachment:
            return attachment

        parts: list[str] = []
        if paragraph:
            parts.append(f"§{paragraph}")
        if subsection:
            parts.append(f"odst.{subsection}")
        if letter:
            parts.append(f"písm.{letter})")
        if parts:
            return " ".join(parts)
        if hierarchy_labels:
            return hierarchy_labels[-1]
        return self._identity_segment(chain[-1])

    def _sorted_entries(self, entries: list[SectionStructureEntry]) -> list[SectionStructureEntry]:
        return sorted(entries, key=lambda entry: entry.log_label.casefold())


legal_section_structure_compare_service = LegalSectionStructureCompareService()
