from datetime import date

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
    ESbirkaOpenDataParsedTree,
)
from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


def parsed_sections_from_version(version_id: int) -> list[ParsedLegalSection]:
    sections = legal_section_service.list_by_version(version_id, include_inactive=False)
    by_id = {item.id: item for item in sections}
    parsed: list[ParsedLegalSection] = []
    for item in sections:
        parent_sort = None
        if item.parent_section_id is not None:
            parent = by_id.get(item.parent_section_id)
            if parent is not None:
                parent_sort = parent.sort_order
        parsed.append(
            ParsedLegalSection(
                section_type=item.section_type,
                section_number=item.section_number or "",
                paragraph=item.paragraph or "",
                item_letter=item.item_letter or "",
                title=item.title or "",
                text=item.text or "",
                sort_order=item.sort_order,
                parent_sort_order=parent_sort,
            ),
        )
    return parsed


def fake_in_force_tree(
    source_eli: str,
    sections: list[ParsedLegalSection],
    *,
    effective_from: date | None = None,
    source_url: str = "",
) -> ESbirkaOpenDataParsedTree:
    wording_date = effective_from
    if wording_date is None:
        try:
            wording_date = date.fromisoformat(source_eli.rsplit("/", 1)[-1])
        except ValueError:
            wording_date = None
    if not source_url:
        act_eli = "/".join(source_eli.split("/")[:5])
        source_url = f"https://opendata.eselpoint.gov.cz/esel-esb/{act_eli}"
    return ESbirkaOpenDataParsedTree(
        source_eli=source_eli,
        source_url=source_url,
        effective_from=wording_date,
        version_label=f"e-Sbírka {source_eli}",
        sections=tuple(sections),
    )
