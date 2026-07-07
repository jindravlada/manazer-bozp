from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
    LegalDocumentParseResult,
    ParsedLegalSection,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
)

_VALID_PARENT_TYPES: dict[str, frozenset[str]] = {
    SECTION_PART: frozenset(),
    SECTION_HEAD: frozenset({SECTION_PART}),
    SECTION_DIVISION: frozenset({SECTION_HEAD, SECTION_PART}),
    SECTION_PARAGRAPH: frozenset({SECTION_DIVISION, SECTION_HEAD, SECTION_PART}),
    SECTION_SUBSECTION: frozenset({SECTION_PARAGRAPH}),
    SECTION_LETTER: frozenset({SECTION_SUBSECTION}),
}

_ALL_SECTION_TYPES = (
    SECTION_PART,
    SECTION_HEAD,
    SECTION_DIVISION,
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
    SECTION_LETTER,
)


@dataclass
class HierarchyError:
    sort_order: int
    section_type: str
    section_number: str
    parent_sort_order: int | None
    message: str


@dataclass
class ParserDiagnosticsResult:
    total_sections: int
    counts_by_type: dict[str, int]
    missing_parent_count: int
    invalid_parent_count: int
    root_count: int
    max_depth: int
    hierarchy_ok: bool
    errors: list[HierarchyError] = field(default_factory=list)


class LegalDocumentParserDiagnostics:
    def analyze(self, parse_result: LegalDocumentParseResult) -> ParserDiagnosticsResult:
        sections = parse_result.sections
        by_sort_order = {section.sort_order: section for section in sections}
        counts_by_type = {section_type: 0 for section_type in _ALL_SECTION_TYPES}
        errors: list[HierarchyError] = []
        missing_parent_count = 0
        invalid_parent_count = 0
        root_count = 0

        for section in sections:
            counts_by_type[section.section_type] = counts_by_type.get(section.section_type, 0) + 1

            if section.parent_sort_order is None:
                root_count += 1
                if section.section_type != SECTION_PART:
                    missing_parent_count += 1
                    errors.append(
                        self._error(
                            section,
                            "Chybí rodič pro daný typ ustanovení.",
                        ),
                    )
                continue

            if section.section_type == SECTION_PART:
                invalid_parent_count += 1
                errors.append(
                    self._error(
                        section,
                        "ČÁST nesmí mít rodiče.",
                    ),
                )
                continue

            parent = by_sort_order.get(section.parent_sort_order)
            if parent is None:
                invalid_parent_count += 1
                errors.append(
                    self._error(
                        section,
                        f"Rodič se sort_order={section.parent_sort_order} neexistuje.",
                    ),
                )
                continue

            allowed_parents = _VALID_PARENT_TYPES.get(section.section_type, frozenset())
            if parent.section_type not in allowed_parents:
                invalid_parent_count += 1
                errors.append(
                    self._error(
                        section,
                        (
                            f"Neplatný rodič typu '{parent.section_type}' "
                            f"pro ustanovení typu '{section.section_type}'."
                        ),
                    ),
                )

        max_depth = self._compute_max_depth(sections, by_sort_order)

        return ParserDiagnosticsResult(
            total_sections=len(sections),
            counts_by_type=counts_by_type,
            missing_parent_count=missing_parent_count,
            invalid_parent_count=invalid_parent_count,
            root_count=root_count,
            max_depth=max_depth,
            hierarchy_ok=len(errors) == 0,
            errors=errors,
        )

    def export_tree(self, parse_result: LegalDocumentParseResult, path: str | Path) -> None:
        sections = parse_result.sections
        by_sort_order = {section.sort_order: section for section in sections}
        children_map: dict[int | None, list[ParsedLegalSection]] = {}
        for section in sections:
            children_map.setdefault(section.parent_sort_order, []).append(section)

        for child_list in children_map.values():
            child_list.sort(key=lambda item: item.sort_order)

        lines: list[str] = []

        def append_section(section: ParsedLegalSection, depth: int) -> None:
            indent = "  " * depth
            lines.append(f"{indent}{self._format_tree_line(section)}")
            for child in children_map.get(section.sort_order, []):
                append_section(child, depth + 1)

        for root in children_map.get(None, []):
            append_section(root, 0)

        file_path = Path(path)
        file_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _compute_max_depth(
        self,
        sections: list[ParsedLegalSection],
        by_sort_order: dict[int, ParsedLegalSection],
    ) -> int:
        if not sections:
            return 0

        depth_cache: dict[int, int] = {}

        def depth_for(sort_order: int) -> int:
            if sort_order in depth_cache:
                return depth_cache[sort_order]

            section = by_sort_order[sort_order]
            if section.parent_sort_order is None:
                depth_cache[sort_order] = 0
                return 0

            parent_depth = depth_for(section.parent_sort_order)
            node_depth = parent_depth + 1
            depth_cache[sort_order] = node_depth
            return node_depth

        return max(depth_for(section.sort_order) for section in sections)

    def _format_tree_line(self, section: ParsedLegalSection) -> str:
        if section.section_type == SECTION_PART:
            return f"ČÁST {section.section_number}".strip()
        if section.section_type == SECTION_HEAD:
            return f"HLAVA {section.section_number}".strip()
        if section.section_type == SECTION_DIVISION:
            return f"DÍL {section.section_number}".strip()
        if section.section_type == SECTION_PARAGRAPH:
            line = f"§ {section.paragraph}".strip()
            if section.title:
                return f"{line} {section.title}".strip()
            return line
        if section.section_type == SECTION_SUBSECTION:
            return f"odst. {section.section_number}".strip()
        if section.section_type == SECTION_LETTER:
            return f"písm. {section.item_letter})".strip()
        return section.section_number or section.section_type

    def _error(self, section: ParsedLegalSection, message: str) -> HierarchyError:
        return HierarchyError(
            sort_order=section.sort_order,
            section_type=section.section_type,
            section_number=self._section_identifier(section),
            parent_sort_order=section.parent_sort_order,
            message=message,
        )

    def _section_identifier(self, section: ParsedLegalSection) -> str:
        if section.section_type == SECTION_PARAGRAPH:
            return section.paragraph
        if section.section_type == SECTION_LETTER:
            return section.item_letter
        return section.section_number


legal_document_parser_diagnostics = LegalDocumentParserDiagnostics()
