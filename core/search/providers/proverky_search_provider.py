"""Poskytovatel globálního vyhledávání pro modul Prověrky BOZP."""

from __future__ import annotations

from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service

from core.search.constants import SOURCE_TYPE_INSPECTION
from core.search.search_provider import SearchProvider
from core.search.search_result import SearchResult
from core.search.search_utils import contains_query

_PRIORITY_TITLE_MATCH = 100
_PRIORITY_DESCRIPTION_MATCH = 50
_PRIORITY_OTHER_MATCH = 30


class ProverkySearchProvider(SearchProvider):
    provider_key = "inspections"
    module_key = "proverky"
    module_label = "Prověrky BOZP"

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []

        for inspection in bozp_inspection_service.get_all():
            number = inspection.number or ""
            name = inspection.title or ""
            title = number or name or f"Prověrka {inspection.id}"
            status = bozp_inspection_service.derive_status(
                inspection.started_at,
                inspection.finished_at,
            )
            conclusion = self._conclusion_text(inspection, status)

            priority = self._match_priority(
                query,
                title=number,
                title_name=name,
                description=conclusion,
                workplace_name=inspection.workplace_name,
                year=inspection.year,
                status=status,
                inspection_type=inspection.inspection_type,
            )
            if priority is None:
                continue

            subtitle = " | ".join(
                part
                for part in (
                    status,
                    inspection.workplace_name,
                    str(inspection.year) if inspection.year else "",
                )
                if part
            )
            description = name or conclusion

            results.append(
                SearchResult(
                    source_type=SOURCE_TYPE_INSPECTION,
                    source_id=inspection.id,
                    title=title,
                    subtitle=subtitle,
                    description=description[:120],
                    module_key=self.module_key,
                    module_label=self.module_label,
                    priority=priority,
                    metadata={"status": status},
                )
            )

        results.sort(
            key=lambda item: (-item.priority, item.title.casefold(), item.source_id)
        )
        return results[:limit]

    @staticmethod
    def _conclusion_text(inspection, status: str) -> str:
        summary = bozp_inspection_service.get_conclusion_summary(inspection.id)
        parts = [status]
        if summary["findings_open"]:
            parts.append(f"{summary['findings_open']} otevřených zjištění")
        if summary["tasks_active"]:
            parts.append(f"{summary['tasks_active']} aktivních úkolů")
        return " — ".join(parts)

    @staticmethod
    def _match_priority(query: str, **fields: object) -> int | None:
        number = str(fields.get("title") or "")
        name = str(fields.get("title_name") or "")
        description = str(fields.get("description") or "")

        if contains_query(query, number, name):
            return _PRIORITY_TITLE_MATCH
        if contains_query(query, description):
            return _PRIORITY_DESCRIPTION_MATCH

        year = fields.get("year")
        other_values = (
            fields.get("workplace_name"),
            str(year) if year is not None else "",
            fields.get("status"),
            fields.get("inspection_type"),
        )
        if contains_query(query, *other_values):
            return _PRIORITY_OTHER_MATCH

        return None
